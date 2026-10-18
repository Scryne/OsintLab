from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app import docint
from app.collector import (
    CollectorFetchError,
    CollectorSecurityError,
    MAX_OBSERVATION_TEXT_LENGTH,
    _host_allowed,
    extract_article_from_html,
    load_allowlist,
    normalize_hostname,
    safe_fetch,
    save_allowlist,
)
from app.db import fetch_all, fetch_one, get_connection
from app.models import (
    SCAN_MODES,
    AllowlistAdd,
    CollectorFetchRequest,
    MonitorCreate,
    ReparseItem,
    ReparseRequest,
    ReparseResult,
    ScanSchedule,
    ScanScheduleCreate,
    ScanScheduleUpdate,
)
from app.monitoring import find_monitor
from app.routers.monitors import create_monitor
from app.scanning import (
    ScheduleBusyError,
    collect_from_url,
    create_schedule,
    get_schedule_row,
    list_schedule_rows,
    next_run_at,
    run_schedule,
)
from app.vault import safe_render_vault

router = APIRouter(prefix="/collectors", tags=["collectors"])


@router.get("/allowlist")
def get_allowlist() -> dict:
    return {"hostnames": sorted(load_allowlist())}


@router.post("/allowlist", status_code=201)
def add_to_allowlist(payload: AllowlistAdd) -> dict:
    hosts = load_allowlist()
    hostname = normalize_hostname(payload.hostname)
    if not hostname:
        raise HTTPException(status_code=422, detail="Geçerli bir hostname değil")
    hosts.add(hostname)
    save_allowlist(hosts)
    return {"hostnames": sorted(hosts)}


@router.delete("/allowlist/{hostname}", status_code=204)
def remove_from_allowlist(hostname: str) -> None:
    """Ekleme ile AYNI normalizasyon: `WWW.X.com` ya da `x.com.` eklenirken `x.com`a
    indirgeniyordu ama silinirken olduğu gibi aranıyordu — hiçbir şey silinmiyor, yine de
    204 dönüyordu. Listede olmayan bir host artık 404."""
    hosts = load_allowlist()
    normalized = normalize_hostname(hostname)
    target = normalized if normalized in hosts else hostname
    if target not in hosts:
        raise HTTPException(status_code=404, detail=f"{normalized or hostname} allowlist'te yok")
    hosts.discard(target)
    save_allowlist(hosts)


@router.post("/fetch")
def fetch(payload: CollectorFetchRequest) -> dict:
    """Q22: allowlist + SSRF doğrulamasından geçen bir URL'i güvenli şekilde çeker, her
    öğeyi (rss) veya sayfanın tamamını (web) bir Observation olarak sisteme sokar. Toplanan
    içerik hiçbir şekilde yorumlanmaz/çalıştırılmaz — düz metin olarak saklanır.

    Faz 12: toplama mantığı `app/scanning.py`'ye taşındı; elle tarama ile zamanlanmış tarama
    artık aynı çekirdeği kullanıyor (güvenlik ve dedup davranışı ikisinde de aynı olsun diye)."""
    if payload.mode not in SCAN_MODES:
        raise HTTPException(status_code=422, detail="mode must be 'rss' or 'web'")

    try:
        result = collect_from_url(
            payload.url, payload.mode, limit=payload.limit, since_days=payload.since_days
        )
    except CollectorSecurityError as exc:
        # 403: BİZ reddettik (allowlist/SSRF) — kullanıcının düzeltebileceği bir yapılandırma.
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CollectorFetchError as exc:
        # 502: KARŞI TARAF reddetti — bizim yapılandırmamızda bir sorun yok (F25).
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    observations = result.pop("observations")
    return {
        **result,
        "observations_created": len(observations),
        "observation_ids": [o.id for o in observations],
    }


# ---- Faz 25: saklanmış web metnini yeniden ayrıştırma --------------------
#
# Faz 25 ayrıştırıcıyı düzeltir, ama daha önce kaydedilmiş bozuk metinler grafta durmaya
# devam eder — ve `Claim.text` oradan kopyalandığı için hem başlık hem entity adayları hem
# metin karşılaştırması bozuk kalır. Bu uç o geçmişi onarır: sayfayı yeniden çeker, yeni
# ayrıştırıcıdan geçirir, gözlemi ve ondan doğmuş claim'i günceller.
#
# Ayrıştırıcı bir daha iyileştiğinde aynı yol tekrar kullanılabilir; bu yüzden tek seferlik
# bir migration script'i değil, bir uç.

# Onarımın İKİ koşulu var ve ikisi de bilerek muhafazakâr:
#
#   1. Saklanan metin yeni gövdeden belirgin biçimde UZUN olmalı. Bir RSS özeti zaten
#      temizdir; onu makale gövdesiyle değiştirmek "onarım" değil, kaynağı değiştirmektir.
#      Ölçüldü: CISA'nın RSS özetleri (20036 karakter) yeni gövdeyle neredeyse aynı boyda
#      (oran 1.06) — bu eşik onları dokunulmadan bırakır.
#   2. Yeni gövde saklanan metnin İÇİNDE olmalı. Bu, "aynı sayfanın daha dar hali" ile
#      "sayfa o zamandan beri değişmiş" arasındaki farkı ayırır. Sayfa değiştiyse onarım
#      sessizce yeni bir içerik yazmış olurdu — gözlem artık gözlemlenen şey olmazdı.
REPARSE_MIN_SHRINK = 1.5
REPARSE_MIN_CONTAINMENT = 0.8

# Kendi kendine aday seçerken uygulanan uzunluk tabanı. Gerekçesi nezaket ve maliyet:
# havuz filtresiz 375 gözlem, yani 375 dış istek — kaynakları boş yere dövmek. Bir sayfanın
# tamamının dökümü her zaman uzundur (ölçülen bozuk gözlem 9370 karakter; claim metni
# medyanı 221). Bu tabanın altındakiler taranmaz. Elle id verildiğinde taban UYGULANMAZ:
# kullanıcı hangi gözlemi kastettiğini biliyorsa tahmin etmemize gerek yok.
REPARSE_MIN_LENGTH = 2000


def _containment(new_body: str, stored: str) -> float:
    """Yeni gövdenin satırlarının ne kadarı saklanan metinde geçiyor (0..1)."""
    lines = [line for line in (l.strip() for l in new_body.splitlines()) if len(line) >= 25]
    if not lines:
        return 0.0
    blob = " ".join(stored.split())
    hit = sum(1 for line in lines if " ".join(line.split()) in blob)
    return hit / len(lines)


def _reparse_targets(conn, observation_ids: list[str] | None) -> list[dict]:
    if observation_ids:
        return fetch_all(conn.execute(
            "MATCH (o:Observation) WHERE o.id IN $ids "
            "RETURN o.id AS id, o.raw_content AS raw_content, o.source_url AS source_url, "
            "o.text_source AS text_source",
            {"ids": observation_ids},
        ))
    # Aday havuzu: URL'i olan ve DOCINT'ten gelmeyen gözlemler. `text_source` Faz 25'ten
    # ÖNCE collector tarafında hiç yazılmıyordu, o yüzden NULL da adaydır.
    #
    # NULL olanları web/rss diye ayıran şey `observed_at == created_at` eşitliği. Bu bir
    # sezgi değil, toplama yolunun yapısal izi: `mode=rss` yayın tarihini feed'den alır
    # (Faz 11/F1), `mode=web`in ise tarihi yoktur ve `observed_at` kayıt anına düşer.
    # Ölçüldü (2026-09-09): 375 gözlemin tam 3'ünde eşitlik var ve üçü de elle yapılmış
    # web toplamaları; 372 RSS gözleminin hiçbiri havuza girmiyor. Yanılabileceği tek yer
    # tarihsiz bir feed — o durumda da aşağıdaki iki koşul (küçülme + içerilme) tutar.
    return fetch_all(conn.execute(
        "MATCH (o:Observation) WHERE o.source_url IS NOT NULL "
        "AND (o.text_source = 'web' OR (o.text_source IS NULL AND o.observed_at = o.created_at)) "
        "AND size(o.raw_content) >= $floor "
        "RETURN o.id AS id, o.raw_content AS raw_content, o.source_url AS source_url, "
        "o.text_source AS text_source",
        {"floor": REPARSE_MIN_LENGTH},
    ))


@router.post("/reparse", response_model=ReparseResult)
def reparse_observations(payload: ReparseRequest) -> ReparseResult:
    """Saklanmış sayfa metnini yeni ayrıştırıcıyla (başlık + gövde) onarır.

    Varsayılan `dry_run=true`: ne yapılacağını söyler, hiçbir şey yazmaz."""
    conn = get_connection()
    allowlist = load_allowlist()
    rows = _reparse_targets(conn, payload.observation_ids)

    items: list[ReparseItem] = []
    repaired = repairable = 0
    for row in rows:
        stored = row["raw_content"] or ""
        item = ReparseItem(
            observation_id=row["id"], source_url=row["source_url"], action="atlandi",
            old_length=len(stored),
        )
        try:
            _, content, _ = safe_fetch(row["source_url"], allowlist)
        except (CollectorSecurityError, CollectorFetchError) as exc:
            item.reason = str(exc)
            items.append(item)
            continue

        title, body = extract_article_from_html(content)
        if not body:
            item.reason = "Sayfada makale gövdesi bulunamadı (makale olmayan bir sayfa olabilir)."
            items.append(item)
            continue

        new_text = f"{title}\n\n{body}".strip() if title else body
        # Gözlem metni tavanı toplama yolunda uygulanıyor; onarım yolu da aynı tavana uymalı,
        # yoksa onarılmış bir gözlem toplananlardan uzun olabilirdi.
        new_text = new_text[:MAX_OBSERVATION_TEXT_LENGTH]
        item.new_length = len(new_text)
        item.containment = round(_containment(body, stored), 3)
        item.new_headline = title or body.split("\n")[0][:160]

        if len(stored) < len(new_text) * REPARSE_MIN_SHRINK:
            item.reason = (
                f"Saklanan metin yeni gövdeden yeterince uzun değil "
                f"({len(stored)} / {len(new_text)} = {len(stored) / max(len(new_text), 1):.2f}); "
                "boilerplate sorunu görünmüyor."
            )
            items.append(item)
            continue
        if item.containment < REPARSE_MIN_CONTAINMENT:
            item.reason = (
                f"Yeni gövdenin yalnızca %{item.containment * 100:.0f}'i saklanan metinde var — "
                "sayfa toplandığından beri değişmiş olabilir, üzerine yazılmadı."
            )
            items.append(item)
            continue

        claim_rows = fetch_all(conn.execute(
            "MATCH (:Observation {id: $oid})-[:PRODUCED]->(c:Claim) RETURN c.id AS id",
            {"oid": row["id"]},
        ))
        item.claim_ids = [r["id"] for r in claim_rows]

        if payload.dry_run:
            item.action = "onarilabilir"
            repairable += 1
            items.append(item)
            continue

        # Q22: metin değişti, enjeksiyon taraması da yenilenmeli — eski uyarı yeni metne ait
        # değil. Tarama gözlemin yaratılışında da burada da aynı fonksiyondan geçiyor.
        hits = docint.find_instruction_like(new_text, where="gözlem metni")
        conn.execute(
            "MATCH (o:Observation {id: $oid}) SET o.raw_content = $text, "
            "o.injection_hits = $hits, o.text_source = 'web'",
            {"oid": row["id"], "text": new_text, "hits": docint.hits_to_json(hits)},
        )
        for claim_id in item.claim_ids:
            conn.execute(
                "MATCH (c:Claim {id: $cid}) SET c.text = $text, c.updated_at = $now",
                {"cid": claim_id, "text": new_text, "now": datetime.now(timezone.utc)},
            )
        item.action = "onarildi"
        repaired += 1
        items.append(item)

    if repaired:
        safe_render_vault(conn)

    return ReparseResult(
        dry_run=payload.dry_run, considered=len(rows), repaired=repaired,
        repairable=repairable, items=items,
    )


# ---- Zamanlanmış tarama (Faz 12) ----------------------------------------

def _to_model(conn, row: dict) -> ScanSchedule:
    return ScanSchedule(
        **{k: row[k] for k in (
            "id", "url", "mode", "interval_minutes", "item_limit", "since_days", "label",
            "active", "last_run_at", "last_status", "last_error", "last_new_count",
            "created_at", "source_id", "source_name",
        )},
        consecutive_failures=row["consecutive_failures"] or 0,
        next_run_at=next_run_at(row),
        # "İzleniyor mu" hesaplanan bir alan, saklanan değil: kullanıcı Monitor'ü bağımsız
        # olarak kapatabilir ve o an tarama sessizleşir. Bunu listede göstermezsek, çalışan
        # ama hiçbir şey söylemeyen bir tarama kurmuş olmak sessiz bir tuzağa dönerdi.
        monitored=find_monitor(conn, "Source", row["source_id"]) is not None,
    )


@router.post("/schedules", response_model=ScanSchedule, status_code=201)
def create_scan_schedule(payload: ScanScheduleCreate) -> ScanSchedule:
    """Bir kaynağı periyodik taramaya alır.

    Doğrulamalar bilerek kurulum anında yapılıyor, ilk koşuda değil: allowlist'te olmayan bir
    hostname ya da olmayan bir Source ile kurulan tarama, saatler sonra sessizce başarısız
    olurdu ve kullanıcı bunu ancak hiçbir şey gelmediğini fark edince anlardı."""
    if payload.mode not in SCAN_MODES:
        raise HTTPException(status_code=422, detail="mode must be 'rss' or 'web'")

    conn = get_connection()
    source = fetch_one(
        conn.execute(
            "MATCH (s:Source {id: $id}) RETURN s.id AS id, s.name AS name, s.url AS url",
            {"id": payload.source_id},
        )
    )
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source not found: {payload.source_id}")

    url = (payload.url or source["url"] or "").strip()
    if not url:
        raise HTTPException(
            status_code=422,
            detail="Taranacak bir adres yok: ya `url` ver ya da kaynağın kendi `url` alanını doldur.",
        )

    # Elle taramanın kullandığı kontrolün AYNISI (`_host_allowed`) — 'www.' toleransı dahil
    # (F4). Burada daha katı bir kontrol kullanmak, elle çalışan bir adresi zamanlanmışta
    # reddederdi.
    hostname = normalize_hostname(url)
    if not _host_allowed(hostname, load_allowlist()):
        raise HTTPException(
            status_code=403,
            detail=(
                f"{hostname or url} allowlist'te değil. Zamanlanmış tarama da elle tarama ile "
                "aynı güvenlik katmanından geçer (Q22) — önce hostname'i allowlist'e ekle."
            ),
        )

    existing = fetch_one(
        conn.execute(
            "MATCH (s:ScanSchedule {url: $url, active: true}) RETURN s.id AS id", {"url": url}
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Bu adres için zaten aktif bir tarama var")

    schedule_id = create_schedule(
        conn,
        source_id=payload.source_id,
        url=url,
        mode=payload.mode,
        interval_minutes=payload.interval_minutes,
        item_limit=payload.item_limit,
        since_days=payload.since_days,
        label=payload.label,
    )

    if payload.watch and find_monitor(conn, "Source", payload.source_id) is None:
        create_monitor(MonitorCreate(target_type="Source", target_id=payload.source_id, label=source["name"]))

    safe_render_vault(conn)
    return _to_model(conn, get_schedule_row(conn, schedule_id))


@router.get("/schedules", response_model=list[ScanSchedule])
def list_scan_schedules(active: bool | None = None) -> list[ScanSchedule]:
    conn = get_connection()
    return [_to_model(conn, row) for row in list_schedule_rows(conn, active=active)]


@router.patch("/schedules/{schedule_id}", response_model=ScanSchedule)
def update_scan_schedule(schedule_id: str, payload: ScanScheduleUpdate) -> ScanSchedule:
    conn = get_connection()
    if get_schedule_row(conn, schedule_id) is None:
        raise HTTPException(status_code=404, detail="Scan schedule not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Değiştirilecek bir alan verilmedi")
    # `exclude_unset` açıkça gönderilmiş `null`ları tutuyor. `since_days` ve `label` için null
    # anlamlı ("pencere yok", "etiket yok"), ama aralık/limit/durum için değil: NULL bir
    # `interval_minutes` zamanlayıcının her turunu TypeError'la düşürüyordu (2026-10-18 denetimi).
    nulled = [f for f in ("interval_minutes", "item_limit", "active") if f in updates and updates[f] is None]
    if nulled:
        raise HTTPException(status_code=422, detail=f"Bu alanlar boş bırakılamaz: {', '.join(nulled)}")

    if updates.get("active") is True:
        # Oluşturmadaki "adres başına tek aktif tarama" kuralı yeniden açmada da geçerli —
        # yoksa kapatılıp aynı adresle yenisi kurulmuş bir tarama geri açılınca ikisi birden
        # aynı feed'i tarardı.
        row = get_schedule_row(conn, schedule_id)
        other = fetch_one(
            conn.execute(
                "MATCH (s:ScanSchedule {url: $url, active: true}) WHERE s.id <> $id RETURN s.id AS id",
                {"url": row["url"], "id": schedule_id},
            )
        )
        if other is not None:
            raise HTTPException(status_code=409, detail="Bu adres için zaten aktif başka bir tarama var")

    sets = ", ".join(f"s.{field} = ${field}" for field in updates)
    if updates.get("active") is True:
        # Yeniden açılan bir tarama temiz sayfadan başlar: kapalıyken birikmiş hata sayacı
        # yüzünden 8 katlık geri çekilme aralığıyla uyanmasın.
        sets += ", s.consecutive_failures = 0"
    conn.execute(f"MATCH (s:ScanSchedule {{id: $id}}) SET {sets}", {"id": schedule_id, **updates})
    return _to_model(conn, get_schedule_row(conn, schedule_id))


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_scan_schedule(schedule_id: str) -> None:
    """Monitor'deki desenle aynı: fiziksel silme değil, active=false — geçmiş Inbox öğeleri
    hangi taramadan geldiğini göstermeye devam edebilsin (Q14/audit trail)."""
    conn = get_connection()
    if get_schedule_row(conn, schedule_id) is None:
        raise HTTPException(status_code=404, detail="Scan schedule not found")
    conn.execute("MATCH (s:ScanSchedule {id: $id}) SET s.active = false", {"id": schedule_id})


@router.post("/schedules/{schedule_id}/run")
def run_scan_schedule_now(schedule_id: str) -> dict:
    """Aralığı beklemeden şimdi çalıştır — kurulumu doğrulamanın en hızlı yolu.

    Zamanlayıcının çalıştırdığı kodun aynısını çağırır (`scanning.run_schedule`), yani burada
    çalışan bir tarama zamanlanmış olarak da çalışır. Tarama hatası burada da HTTP hatası
    DEĞİL: sonuç `status: "ERROR"` olarak döner, çünkü koşunun kendisi başarıyla kaydedildi."""
    conn = get_connection()
    try:
        return run_schedule(conn, schedule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Scan schedule not found") from exc
    except ScheduleBusyError as exc:
        raise HTTPException(status_code=409, detail="Bu tarama şu anda zaten çalışıyor") from exc
