<#
.SYNOPSIS
    OsintLab verisinin tutarlı bir yedeğini alır: graf + kanıt + arşiv + yapılandırma + günlük.

.DESCRIPTION
    Neden bir script: 2026-10-18 denetimine kadar projenin hiçbir yedeği yoktu ve gömülü
    KùzuDB dosyası backend çalışırken KİLİTLİ — elle kopyalamak "Device or resource busy" ile
    yarıda kalıyor ya da WAL'ı ana dosyayla tutarsız bir anda yakalıyor. Tek tutarlı yol,
    backend'i kısa süreliğine durdurup kopyalamak. Bu script bunu yapar ve backend'i (çalışıyorsa)
    geri başlatır; otomatik tarama en fazla birkaç saniye durur.

    Yedeklenen: data\graph, data\evidence, data\archive, data\config, data\daily, data\enrichment
    (zenginleştirme koşularının ham yanıtları — her EnrichmentRun'ın SHA-256'sı bunlara işaret eder).
    Yedeklenmeyen: data\vault (grafın türetilmiş görünümü — POST /vault/render yeniden üretir),
    data\logs, data\tessdata (proje dışından indirilebilir dil verisi), data\datasets ve
    data\cache (KEV/ATT&CK/OFAC listeleri ve RDAP bootstrap; Zenginleştirme sayfasından yeniden indirilir).

    Çıktı: data\backups\osintlab-YYYYMMDD-HHMMSS.zip. En yeni -Keep adet tutulur.

.PARAMETER Keep
    Saklanacak en yeni yedek sayısı (varsayılan 10). Daha eskileri silinir.

.EXAMPLE
    .\scripts\yedek.ps1
    .\scripts\yedek.ps1 -Keep 30
#>
[CmdletBinding()]
param(
    [int]$Keep = 10
)

$ErrorActionPreference = 'Stop'

$root      = Split-Path -Parent $PSScriptRoot
$data      = Join-Path $root 'data'
$backups   = Join-Path $data 'backups'
$TASK_NAME = 'OsintLab Backend'
$API_PORT  = 8420

function Get-ApiOwner {
    try {
        $conn = Get-NetTCPConnection -LocalPort $API_PORT -State Listen -ErrorAction Stop | Select-Object -First 1
        return Get-Process -Id $conn.OwningProcess -ErrorAction Stop
    } catch { return $null }
}

$task = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
$owner = Get-ApiOwner
$restartTask = $false

if ($owner) {
    if ($task -and $task.State -eq 'Running') {
        # Görevi düzgün durdur: process'i öldürmek görevi "başarısız" bitirir ve yeniden
        # başlatma ayarı backend'i 5 dk sonra kendiliğinden geri getirirdi (bkz. start.ps1 -Stop).
        Write-Host "  backend durduruluyor (autostart görevi)..." -ForegroundColor DarkGray
        Stop-ScheduledTask -TaskName $TASK_NAME
        $restartTask = $true
    } else {
        # start.ps1 ile elle açılmış bir backend: onu kapatmak kullanıcının penceresini
        # bozar. Durup söylemek daha doğru.
        Write-Host "  ! Backend elle başlatılmış (PID $($owner.Id)). Önce .\start.ps1 -Stop, sonra bu script." -ForegroundColor Yellow
        exit 1
    }
    foreach ($i in 1..20) {
        if (-not (Get-ApiOwner)) { break }
        Start-Sleep -Milliseconds 500
    }
    if (Get-ApiOwner) { throw "Backend 10 sn içinde kapanmadı — yedek alınmadı." }
}

$stamp   = Get-Date -Format 'yyyyMMdd-HHmmss'
$staging = Join-Path ([System.IO.Path]::GetTempPath()) "osintlab-yedek-$stamp"
$target  = Join-Path $backups "osintlab-$stamp.zip"

try {
    New-Item -ItemType Directory -Force $staging | Out-Null
    foreach ($part in 'graph', 'evidence', 'archive', 'config', 'daily', 'enrichment') {
        $src = Join-Path $data $part
        if (Test-Path $src) { Copy-Item -Recurse -Force $src (Join-Path $staging $part) }
    }
} finally {
    # Backend kopyalama biter bitmez geri gelir; sıkıştırma ona dokunmayan kopya üzerinde.
    if ($restartTask) {
        Start-ScheduledTask -TaskName $TASK_NAME
        Write-Host "  backend yeniden başlatıldı" -ForegroundColor DarkGray
    }
}

New-Item -ItemType Directory -Force $backups | Out-Null
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $target -CompressionLevel Optimal
Remove-Item -Recurse -Force $staging

$size = [math]::Round((Get-Item $target).Length / 1MB, 1)
Write-Host "  yedek: $target ($size MB)" -ForegroundColor Green

$old = Get-ChildItem $backups -Filter 'osintlab-*.zip' | Sort-Object Name -Descending | Select-Object -Skip $Keep
foreach ($f in $old) {
    Remove-Item -Force $f.FullName
    Write-Host "  eski yedek silindi: $($f.Name)" -ForegroundColor DarkGray
}
Write-Host ""
Write-Host "  Geri yüklemek için: backend'i durdur (.\start.ps1 -Stop), zip'i data\ altına aç (graph\, evidence\ ...), başlat." -ForegroundColor DarkGray
