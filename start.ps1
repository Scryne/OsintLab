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

.EXAMPLE
    .\start.ps1
    .\start.ps1 -Reload      # Faz 11'de bulunan bir bug'ı düzeltirken
    .\start.ps1 -Stop
#>
[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$Reload,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$root        = $PSScriptRoot
$backendDir  = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$uvicorn     = Join-Path $backendDir '.venv\Scripts\uvicorn.exe'

$API_PORT = 8420
$WEB_PORT = 3000

function Get-PortOwner {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
                Select-Object -First 1
    } catch { return $null }
    if (-not $conn) { return $null }
    try { return Get-Process -Id $conn.OwningProcess -ErrorAction Stop } catch { return $null }
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

# --- Durdurma modu -----------------------------------------------------------
if ($Stop) {
    $stopped = 0
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
        Stop-Process -Id $proc.Id -Force
        Write-Host "  port $port : $($proc.ProcessName) (PID $($proc.Id)) durduruldu" -ForegroundColor Green
        $stopped++
    }
    Write-Host ""
    Write-Host "$stopped process durduruldu. Servis pencereleri aciksa elle kapatabilirsin."
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

$busy = $false
foreach ($p in @(@{Port=$API_PORT; Ad='backend'}, @{Port=$WEB_PORT; Ad='frontend'})) {
    $owner = Get-PortOwner -Port $p.Port
    if ($owner) {
        Write-Host "  ! port $($p.Port) ($($p.Ad)) zaten dolu: $($owner.ProcessName) PID $($owner.Id)" -ForegroundColor Yellow
        $busy = $true
    }
}
if ($busy) {
    Write-Host ""
    Write-Host "Once kapat:  .\start.ps1 -Stop" -ForegroundColor Yellow
    return
}

# --- Backend -----------------------------------------------------------------
$uvArgs = "app.main:app --host 127.0.0.1 --port $API_PORT"
if ($Reload) { $uvArgs += ' --reload' }

Start-Process pwsh -ArgumentList @(
    '-NoExit', '-NoProfile', '-Command',
    "`$Host.UI.RawUI.WindowTitle = 'OsintLab API :$API_PORT'; Set-Location '$backendDir'; & '$uvicorn' $uvArgs"
) | Out-Null

Write-Host "  backend  -> http://127.0.0.1:$API_PORT $(if ($Reload) { '(--reload ACIK)' })"
$apiUp = Wait-Endpoint -Url "http://127.0.0.1:$API_PORT/health" -Label 'Backend'
if ($apiUp) { Write-Host "           /health ok" -ForegroundColor Green }

# --- Frontend ----------------------------------------------------------------
Start-Process pwsh -ArgumentList @(
    '-NoExit', '-NoProfile', '-Command',
    "`$Host.UI.RawUI.WindowTitle = 'OsintLab Web :$WEB_PORT'; Set-Location '$frontendDir'; npm run dev"
) | Out-Null

Write-Host "  frontend -> http://localhost:$WEB_PORT"
$webUp = Wait-Endpoint -Url "http://localhost:$WEB_PORT" -TimeoutSec 90 -Label 'Frontend'
if ($webUp) { Write-Host "           hazir" -ForegroundColor Green }

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
