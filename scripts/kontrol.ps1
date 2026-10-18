<#
.SYNOPSIS
    Kod tabanının taban çizgisini tek komutla doğrular: backend testleri + statik kontrol,
    frontend tip denetimi + lint.

.DESCRIPTION
    Taban çizgisi (2026-10-18 denetimi): backend testleri yeşil, ruff (F/E9/B) temiz,
    `tsc --noEmit` temiz, `eslint` 0 uyarı. Yeni iş bu çizgiyi kirletmemeli.

    Testler kendi geçici veri kökünde çalışır (OSINTLAB_DATA_DIR) — gerçek data\ klasörüne
    ve çalışan backend'e dokunmaz; backend ayaktayken de güvenle koşturulabilir.

    ruff venv'e kurulu değil; `uvx` varsa onunla çalışır, yoksa atlanır (atlandığı söylenir).

.EXAMPLE
    .\scripts\kontrol.ps1
#>
[CmdletBinding()]
param()

$root     = Split-Path -Parent $PSScriptRoot
$backend  = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python   = Join-Path $backend '.venv\Scripts\python.exe'
$failed   = @()

function Step([string]$name, [scriptblock]$body) {
    Write-Host ""
    Write-Host "== $name" -ForegroundColor Cyan
    & $body
    if ($LASTEXITCODE -ne 0) { $script:failed += $name }
}

if (-not (Test-Path $python)) { throw "Backend venv yok: $python" }
& $python -c "import pytest, httpx" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  test bağımlılıkları kuruluyor (requirements-dev.txt)..." -ForegroundColor DarkGray
    & $python -m pip install -q -r (Join-Path $backend 'requirements-dev.txt')
}

Push-Location $backend
try {
    Step 'backend: pytest' { & $python -m pytest }
    if (Get-Command uvx -ErrorAction SilentlyContinue) {
        Step 'backend: ruff' { uvx ruff check app tests run_service.py --select F,E9,B }
    } else {
        Write-Host "`n== backend: ruff — ATLANDI (uvx bulunamadı)" -ForegroundColor DarkYellow
    }
} finally { Pop-Location }

Push-Location $frontend
try {
    Step 'frontend: tsc' { npx tsc --noEmit }
    Step 'frontend: eslint' { npm run lint --silent -- --max-warnings 0 }
} finally { Pop-Location }

Write-Host ""
if ($failed.Count) {
    Write-Host "BAŞARISIZ: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "Hepsi temiz." -ForegroundColor Green
