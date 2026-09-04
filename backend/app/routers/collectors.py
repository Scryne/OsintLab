from fastapi import APIRouter, HTTPException

from app.collector import (
    CollectorFetchError,
    CollectorSecurityError,
    _host_allowed,
    load_allowlist,
    normalize_hostname,
    save_allowlist,
)
from app.db import fetch_one, get_connection
from app.models import (
    SCAN_MODES,
    AllowlistAdd,
    CollectorFetchRequest,
    MonitorCreate,
    ScanSchedule,
    ScanScheduleCreate,
    ScanScheduleUpdate,
)
from app.monitoring import find_monitor
from app.routers.monitors import create_monitor
from app.scanning import (
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
    hosts = load_allowlist()
    hosts.discard(hostname)
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
