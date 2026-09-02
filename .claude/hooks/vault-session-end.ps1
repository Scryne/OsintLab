#requires -Version 7.0
<#
    Faz 9 — Living Brain. Oturum kapanışında data/vault/'ı günceller: backend'in
    GET /intelligence/diff ucundan (Faz 7, zaten var — deterministik, LLM'den geçmiyor) o
    günün değişikliklerini alıp data/vault/daily/<bugün>.md'ye "### Oturum <saat>" bloğu
    olarak ekler, sonra POST /vault/render ile tüm notları (Dashboard dahil) tazeler.

    Genel proje-takip session-end.ps1'e EK olarak çalışır (settings.json'da aynı SessionEnd
    dizisinde ikinci hook) -- onun yerine değil. Backend (uvicorn) çalışmıyorsa ya da
    herhangi bir adım başarısız olursa sessizce çıkar; oturumun kapanmasını ASLA engellemez.
#>

Set-StrictMode -Version Latest
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false) } catch { }

# SessionEnd hook'una Claude Code stdin'den bir JSON payload veriyor -- kullanmasak da
# okuyup tüketmemiz gerekiyor (okunmazsa pipe bir sonraki hook'u bloklayabilir).
[void][Console]::In.ReadToEnd()

$projectDir = if (-not [string]::IsNullOrWhiteSpace($env:CLAUDE_PROJECT_DIR)) {
    $env:CLAUDE_PROJECT_DIR
}
else {
    (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}

$apiBase = 'http://127.0.0.1:8420'
$vaultDailyDir = Join-Path $projectDir 'data\vault\daily'
$stateDir = Join-Path $projectDir 'data\vault\.state'
$statePath = Join-Path $stateDir 'last-render.json'

try {
    Invoke-RestMethod -Uri "$apiBase/health" -Method Get -TimeoutSec 2 -ErrorAction Stop | Out-Null
}
catch {
    exit 0  # backend çalışmıyor -- vault güncellenemez, sessizce çık
}

# ?days=1 gibi sabit bir pencere yerine SON BAŞARILI hook çalışmasından beri geçen süreyi
# kullanıyoruz -- aksi halde her SessionEnd'de aynı değişiklikler tekrar tekrar daily/'ye
# eklenirdi (24 saatlik pencere her seferinde aynı şeyi kapsar). İlk çalıştırmada state
# dosyası yoksa son 1 güne bakılır.
$since = $null
if (Test-Path -LiteralPath $statePath -PathType Leaf) {
    try {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json -ErrorAction Stop
        # ConvertFrom-Json, ISO-8601 görünen string alanları OTOMATİK [datetime]'a çeviriyor
        # (PowerShell 7 davranışı) -- sonra "$($x)" ile string'e geri çevirince ISO formatı
        # kaybolup yerel kültürün tarih formatı (ör. "09/02/2026 11:10:28") geliyor, bu da
        # FastAPI'nin datetime parse'ını kırıyor. Tip [datetime] ise .ToString('o') ile
        # açıkça ISO 8601'e geri çevriliyor.
        $rawSince = $state.last_render_at
        $since = if ($rawSince -is [datetime]) { $rawSince.ToString('o') } else { "$rawSince" }
    }
    catch { }
}
$diffUrl = if ($since) { "$apiBase/intelligence/diff?since=$([Uri]::EscapeDataString($since))" } else { "$apiBase/intelligence/diff?days=1" }

try {
    $diff = Invoke-RestMethod -Uri $diffUrl -Method Get -TimeoutSec 15 -ErrorAction Stop
}
catch {
    exit 0
}

# Bir sonraki çalıştırma için "şimdi"yi kaydet -- değişiklik olsa da olmasa da, aksi halde
# değişikliksiz her SessionEnd penceriyi sıfırlamaz ve bir sonrakinde aynı aralık tekrar
# taranır (zararsız ama gereksiz).
try {
    New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
    @{ last_render_at = (Get-Date).ToUniversalTime().ToString('o') } |
        ConvertTo-Json -Compress | Set-Content -LiteralPath $statePath -Encoding utf8NoBOM
}
catch { }

function Count([object]$arr) {
    if ($null -eq $arr) { return 0 }
    return @($arr).Count
}

$hasChanges = (
    (Count $diff.new_entities) + (Count $diff.new_events) + (Count $diff.new_sources) +
    (Count $diff.new_investigations) + (Count $diff.new_claims) + (Count $diff.claims_changed) +
    (Count $diff.new_contradictions) + (Count $diff.investigation_updates)
) -gt 0

if (-not $hasChanges) { exit 0 }

try {
    New-Item -ItemType Directory -Force -Path $vaultDailyDir | Out-Null
    $today = Get-Date -Format 'yyyy-MM-dd'
    $time = Get-Date -Format 'HH:mm'
    $dailyPath = Join-Path $vaultDailyDir "$today.md"

    $lines = [System.Collections.Generic.List[string]]::new()
    if (-not (Test-Path -LiteralPath $dailyPath -PathType Leaf)) {
        $lines.Add("# $today")
        $lines.Add("")
    }
    $lines.Add("### Oturum $time")
    if ((Count $diff.new_entities) -gt 0) {
        $names = (@($diff.new_entities) | ForEach-Object { $_.name }) -join ', '
        $lines.Add("- Yeni entity: $names")
    }
    if ((Count $diff.new_events) -gt 0) {
        $titles = (@($diff.new_events) | ForEach-Object { $_.title }) -join ', '
        $lines.Add("- Yeni event: $titles")
    }
    if ((Count $diff.new_investigations) -gt 0) {
        $titles = (@($diff.new_investigations) | ForEach-Object { $_.title }) -join ', '
        $lines.Add("- Yeni investigation: $titles")
    }
    if ((Count $diff.new_claims) -gt 0) { $lines.Add("- Yeni claim sayısı: $(Count $diff.new_claims)") }
    if ((Count $diff.claims_changed) -gt 0) { $lines.Add("- Değişen claim sayısı: $(Count $diff.claims_changed)") }
    if ((Count $diff.new_contradictions) -gt 0) { $lines.Add("- **Çelişki tespit edildi:** $(Count $diff.new_contradictions)") }
    if ((Count $diff.investigation_updates) -gt 0) {
        $updates = (@($diff.investigation_updates) | ForEach-Object { "$($_.title) -> $($_.status)" }) -join ', '
        $lines.Add("- Investigation güncellemesi: $updates")
    }
    $lines.Add("")

    Add-Content -LiteralPath $dailyPath -Value $lines -Encoding utf8NoBOM
}
catch { }

try {
    Invoke-RestMethod -Uri "$apiBase/vault/render" -Method Post -TimeoutSec 30 -ErrorAction Stop | Out-Null
}
catch { }

exit 0
