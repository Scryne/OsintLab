<#
.SYNOPSIS
    OsintLab'ı yerel geliştirme/kullanım için ayağa kaldırır (backend + frontend).

.DESCRIPTION
    Backend'i 127.0.0.1:8420, frontend'i localhost:3000 üzerinde başlatır. Bu portlar
    keyfi değil, sabit:
      - frontend/.env.local        -> NEXT_PUBLIC_API_BASE=http://127.0.0.1:8420
      - .claude/hooks/vault-session-end.ps1 -> $apiBase = 'http://127.0.0.1:8420'
      - backend/app/main.py CORS   -> sadece localhost:3000 / 127.0.0.1:3000
    Yani backend varsayılan 8000'de başlatılırsa hem arayüz hem oturum-sonu vault
    senkronu sessizce kırılır. Script portu her zaman açıkça verir.

    Her servis kendi penceresinde açılır — dogfooding sırasında bir şey patlarsa
    logu orada görürsün.

.PARAMETER Stop
    8420 ve 3000'i dinleyen OsintLab process'lerini kapatır.

.PARAMETER Reload
    Backend'i --reload ile başlatır. Varsayılan KAPALI: reload, gömülü KùzuDB
    bağlantısını oturum ortasında yeniden açar. Kod düzeltirken aç, kullanırken açma.

.PARAMETER NoBrowser
    Tarayıcıyı otomatik açma.

.PARAMETER InstallAutostart
    Backend'i her oturum açılışında kendiliğinden başlatan bir Windows zamanlanmış görevi
    kurar — yalnızca backend, dashboard'ı ihtiyaç oldukça sen açarsın. Faz 12'nin
    zamanlanmış taraması yalnızca backend ayaktayken çalıştığı için, bu görev olmadan
    otomatik tarama fiilen "sen zaten uygulamanın başındayken tarayan" bir özelliğe düşer.
    Görev pythonw ile çalışır (pencere açmaz), logu data\logs\backend.log'a yazar.

.PARAMETER RemoveAutostart
    Yukarıdaki görevi kaldırır.

.EXAMPLE
    .\start.ps1
    .\start.ps1 -Reload      # Faz 11'de bulunan bir bug'ı düzeltirken
    .\start.ps1 -Stop
    .\start.ps1 -InstallAutostart   # backend oturum açılışında kendiliğinden kalksın
#>
[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$Reload,
    [switch]$NoBrowser,
    [switch]$InstallAutostart,
    [switch]$RemoveAutostart
)

$ErrorActionPreference = 'Stop'

$root        = $PSScriptRoot
$backendDir  = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$uvicorn     = Join-Path $backendDir '.venv\Scripts\uvicorn.exe'

$pythonw   = Join-Path $backendDir '.venv\Scripts\pythonw.exe'
$service   = Join-Path $backendDir 'run_service.py'

$API_PORT  = 8420
$WEB_PORT  = 3000
$TASK_NAME = 'OsintLab Backend'

function Get-PortOwner {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
                Select-Object -First 1
    } catch { return $null }
    if (-not $conn) { return $null }
    try { return Get-Process -Id $conn.OwningProcess -ErrorAction Stop } catch { return $null }
}

function Get-DescendantIds {
    # Faz 11 (dogfooding F14): uvicorn --reload iki process acar (izleyici + isci). -Stop
    # yalnizca portu DINLEYENI oldurdugu icin geride kalan isci KuzuDB lock'unu tutuyordu:
    # port bosalmis gorunuyor ama backend/harici script veritabanina baglanamiyordu.
    # Cocuklari ONCE toplamak sart — ebeveyn oldurulunce cocuk agacta gorunmez oluyor.
    param([int]$Id)
    $ids = @()
    foreach ($child in (Get-CimInstance Win32_Process -Filter "ParentProcessId=$Id" -ErrorAction SilentlyContinue)) {
        $ids += Get-DescendantIds -Id $child.ProcessId
        $ids += [int]$child.ProcessId
    }
    return $ids
}

function Get-AutostartTask {
    try { return Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction Stop } catch { return $null }
}

function Show-AutostartHint {
    # Faz 12: backend'i kapatmak/baslatmak ile "otomatik tarama calisiyor mu" ayni sey. Bu
    # baglantiyi kullaniciya soylemeyen bir script, sessizce durmus bir tarayiciya yol acar.
    $task = Get-AutostartTask
    if (-not $task) {
        Write-Host "  ! Otomatik tarama yalnizca backend ayaktayken calisir." -ForegroundColor DarkYellow
        Write-Host "    Oturum acilisinda kendiliginden kalksin:  .\start.ps1 -InstallAutostart" -ForegroundColor DarkGray
    } elseif ($task.State -eq 'Disabled') {
        Write-Host "  ! Autostart gorevi KAPALI - backend oturum acilisinda kalkmayacak." -ForegroundColor DarkYellow
    }
}

function Wait-Endpoint {
    param([string]$Url, [int]$TimeoutSec = 45, [string]$Label)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing | Out-Null
            return $true
        } catch { Start-Sleep -Milliseconds 700 }
    }
    Write-Host "  ! $Label $TimeoutSec sn icinde yanit vermedi - kendi penceresindeki loga bak." -ForegroundColor Yellow
    return $false
}

# --- Autostart kurulum/kaldirma ----------------------------------------------
if ($RemoveAutostart) {
    if (Get-AutostartTask) {
        Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false
        Write-Host "  Autostart gorevi kaldirildi: '$TASK_NAME'" -ForegroundColor Green
        Write-Host "  Backend artik yalnizca .\start.ps1 ile kalkar - otomatik tarama da o sirada calisir."
    } else {
        Write-Host "  Boyle bir gorev zaten yok: '$TASK_NAME'"
    }
    return
}

if ($InstallAutostart) {
    if (-not (Test-Path $pythonw)) {
        throw "pythonw bulunamadi: $pythonw`nKurulum: cd backend; py -3.12 -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
    }
    if (-not (Test-Path $service)) { throw "run_service.py bulunamadi: $service" }

    # pythonw = konsolsuz yorumlayici: oturum acilisinda ekranda hicbir pencere belirmez.
    # Log kaybolmasin diye run_service.py logu data\logs\backend.log'a bagliyor.
    $action  = New-ScheduledTaskAction -Execute $pythonw `
                   -Argument "`"$service`" --port $API_PORT" -WorkingDirectory $backendDir
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    # Oturum acilisinin en yogun anina denk gelmesin; 1 dk sonra kalksin.
    $trigger.Delay = 'PT1M'
    # ExecutionTimeLimit SIFIR olmali: varsayilan 3 gun, yani gorev backend'i uc gun sonra
    # oldururdu - haftalarca ayakta kalmasi gereken bir servis icin sessiz bir olum.
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                   -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
                   -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) -Hidden
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
                   -LogonType Interactive -RunLevel Limited

    Register-ScheduledTask -TaskName $TASK_NAME -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force `
        -Description 'OsintLab backend (Faz 12 zamanlanmis tarama icin surekli ayakta olmali).' | Out-Null

    Write-Host "  Autostart gorevi kuruldu: '$TASK_NAME'" -ForegroundColor Green
    Write-Host "    tetikleyici : oturum acilisi + 1 dk"
    Write-Host "    komut       : pythonw run_service.py --port $API_PORT  (pencere acmaz)"
    Write-Host "    log         : data\logs\backend.log"
    Write-Host "    kaldirmak   : .\start.ps1 -RemoveAutostart"
    Write-Host ""
    if (Get-PortOwner -Port $API_PORT) {
        Write-Host "  Backend zaten ayakta - gorev bir sonraki oturum acilisinda devralir." -ForegroundColor DarkGray
    } else {
        Start-ScheduledTask -TaskName $TASK_NAME
        Write-Host "  Gorev simdi de baslatildi..." -ForegroundColor DarkGray
        if (Wait-Endpoint -Url "http://127.0.0.1:$API_PORT/health" -Label 'Backend') {
            Write-Host "  /health ok - backend ayakta." -ForegroundColor Green
        }
    }
    return
}

# --- Durdurma modu -----------------------------------------------------------
if ($Stop) {
    $stopped = 0
    # Autostart gorevi calisiyorsa ONCE onu duzgun durdur. Process'i dogrudan oldurursek
    # gorev "basarisiz" biter ve -RestartCount 3 devreye girer: kullanicinin bilerek
    # kapattigi backend 5 dk sonra kendiliginden geri gelir (ve -Reload ile acmaya
    # calisirsa port/KuzuDB kilidi cakisir). Stop-ScheduledTask bunu "kullanici durdurdu"
    # olarak isaretler, yeniden baslatma tetiklenmez.
    $task = Get-AutostartTask
    if ($task -and $task.State -eq 'Running') {
        Stop-ScheduledTask -TaskName $TASK_NAME
        Write-Host "  autostart gorevi durduruldu ('$TASK_NAME')" -ForegroundColor Green
        Start-Sleep -Milliseconds 800
    }
    foreach ($port in @($API_PORT, $WEB_PORT)) {
        $proc = Get-PortOwner -Port $port
        if (-not $proc) {
            Write-Host "  port $port : zaten bos"
            continue
        }
        # Yanlislikla alakasiz bir process'i oldurmemek icin isim kontrolu.
        if ($proc.ProcessName -notmatch '^(python|pythonw|uvicorn|node|pwsh|powershell)$') {
            Write-Host "  port $port : '$($proc.ProcessName)' (PID $($proc.Id)) - OsintLab'a benzemiyor, DOKUNULMADI." -ForegroundColor Yellow
            continue
        }
        # Cocuklari ebeveynden ONCE topla (bkz. Get-DescendantIds).
        $kids = @(Get-DescendantIds -Id $proc.Id)
        Stop-Process -Id $proc.Id -Force
        Write-Host "  port $port : $($proc.ProcessName) (PID $($proc.Id)) durduruldu" -ForegroundColor Green
        $stopped++
        foreach ($kid in $kids) {
            try {
                $kp = Get-Process -Id $kid -ErrorAction Stop
                Stop-Process -Id $kid -Force
                Write-Host "            + alt process $($kp.ProcessName) (PID $kid) durduruldu" -ForegroundColor DarkGray
                $stopped++
            } catch { }
        }
    }
    # Son kontrol: bu proje yolundan calisan, artakalmis python/node var mi? Ebeveyni zaten
    # olmus bir oksuz process agac yuruyusuyle bulunamaz, ama KuzuDB lock'unu tutmaya devam
    # eder — bu yuzden komut satirindan da taraniyor.
    $rootPattern = [regex]::Escape($root)
    $leftovers = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe' OR Name='node.exe'" -ErrorAction SilentlyContinue |
                 Where-Object { $_.CommandLine -and $_.CommandLine -match $rootPattern }
    foreach ($lo in $leftovers) {
        Stop-Process -Id $lo.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "  artakalan $($lo.Name) (PID $($lo.ProcessId)) durduruldu" -ForegroundColor DarkGray
        $stopped++
    }

    Write-Host ""
    Write-Host "$stopped process durduruldu. Servis pencereleri aciksa elle kapatabilirsin."
    # Faz 12: backend'i kapatmak = otomatik taramayi da kapatmak. Kullanicinin bunu
    # bilmeden yapmasi, "neden hicbir sey gelmiyor"un en olasi sebebi olurdu.
    if (Get-AutostartTask) {
        Write-Host "  Otomatik tarama da durdu. Bir sonraki oturum acilisinda autostart gorevi geri getirir;" -ForegroundColor DarkGray
        Write-Host "  simdi geri getirmek icin:  Start-ScheduledTask -TaskName '$TASK_NAME'" -ForegroundColor DarkGray
    }
    return
}

# --- On kontroller -----------------------------------------------------------
Write-Host ""
Write-Host "OsintLab baslatiliyor..." -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $uvicorn)) {
    throw "Backend venv bulunamadi: $uvicorn`nKurulum: cd backend; py -3.12 -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}
if (-not (Test-Path (Join-Path $frontendDir 'node_modules'))) {
    throw "frontend/node_modules yok.`nKurulum: cd frontend; npm install"
}

# Faz 12 (autostart): eskiden portlardan BIRI dolu olsa script tumden cikiyordu. Backend
# artik oturum acilisinda kendiliginden kalkabildigi icin bu, "dashboard'i acmak istedim,
# hicbir sey olmadi" demek olurdu. Dolu port artik durdurmuyor: o servis atlaniyor,
# eksik olan baslatiliyor. Yabanci bir process portu tutuyorsa (isim eslesmiyorsa) hala
# uyarip duruyoruz - onu ezmek dogru olmaz.
$ownName = '^(python|pythonw|uvicorn|node|pwsh|powershell)$'
$apiOwner = Get-PortOwner -Port $API_PORT
$webOwner = Get-PortOwner -Port $WEB_PORT
foreach ($p in @(@{Owner=$apiOwner; Port=$API_PORT; Ad='backend'}, @{Owner=$webOwner; Port=$WEB_PORT; Ad='frontend'})) {
    if ($p.Owner -and $p.Owner.ProcessName -notmatch $ownName) {
        Write-Host "  ! port $($p.Port) ($($p.Ad)) OsintLab'a benzemeyen bir process'te: $($p.Owner.ProcessName) PID $($p.Owner.Id)" -ForegroundColor Yellow
        Write-Host "    Once onu kapat, sonra tekrar dene." -ForegroundColor Yellow
        return
    }
}

# --- Backend -----------------------------------------------------------------
if ($apiOwner) {
    Write-Host "  backend  -> http://127.0.0.1:$API_PORT (zaten ayakta: $($apiOwner.ProcessName) PID $($apiOwner.Id))"
    if ($Reload) {
        Write-Host "  ! -Reload istendi ama backend zaten calisiyor; yeniden baslatmadim." -ForegroundColor Yellow
        Write-Host "    Reload ile acmak icin:  .\start.ps1 -Stop; .\start.ps1 -Reload" -ForegroundColor DarkGray
    }
    $apiUp = $true
} else {
    $uvArgs = "app.main:app --host 127.0.0.1 --port $API_PORT"
    if ($Reload) { $uvArgs += ' --reload' }

    Start-Process pwsh -ArgumentList @(
        '-NoExit', '-NoProfile', '-Command',
        "`$Host.UI.RawUI.WindowTitle = 'OsintLab API :$API_PORT'; Set-Location '$backendDir'; & '$uvicorn' $uvArgs"
    ) | Out-Null

    Write-Host "  backend  -> http://127.0.0.1:$API_PORT $(if ($Reload) { '(--reload ACIK)' })"
    $apiUp = Wait-Endpoint -Url "http://127.0.0.1:$API_PORT/health" -Label 'Backend'
    if ($apiUp) { Write-Host "           /health ok" -ForegroundColor Green }
}

# --- Frontend ----------------------------------------------------------------
if ($webOwner) {
    Write-Host "  frontend -> http://localhost:$WEB_PORT (zaten ayakta: $($webOwner.ProcessName) PID $($webOwner.Id))"
    $webUp = $true
} else {
    Start-Process pwsh -ArgumentList @(
        '-NoExit', '-NoProfile', '-Command',
        "`$Host.UI.RawUI.WindowTitle = 'OsintLab Web :$WEB_PORT'; Set-Location '$frontendDir'; npm run dev"
    ) | Out-Null

    Write-Host "  frontend -> http://localhost:$WEB_PORT"
    $webUp = Wait-Endpoint -Url "http://localhost:$WEB_PORT" -TimeoutSec 90 -Label 'Frontend'
    if ($webUp) { Write-Host "           hazir" -ForegroundColor Green }
}

# --- Ozet --------------------------------------------------------------------
Write-Host ""
if ($apiUp -and $webUp) {
    Write-Host "Ayakta." -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process "http://localhost:$WEB_PORT" }
} else {
    Write-Host "Kismen ayakta - yukaridaki uyariya ve servis pencerelerine bak." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "  Dashboard : http://localhost:$WEB_PORT"
Write-Host "  API dokum : http://127.0.0.1:$API_PORT/docs"
Write-Host "  Obsidian  : data\vault\  (Open folder as vault)"
Write-Host "  Kapat     : .\start.ps1 -Stop"
Write-Host ""
Show-AutostartHint
Write-Host ""
