"""
Continuous Monitoring + Change Detection + Intelligence Inbox (Faz 7, madde 22-27).

Observe -> Detect -> Evaluate -> Compare With Memory -> Update -> Notify döngüsü, ayrı bir
arka plan zamanlayıcı OLMADAN, mevcut yazma noktalarına (claim oluşturma, çelişki tespiti,
investigation geçişi, entity-event ilişkilendirme) kanca atılarak REAKTİF şekilde
gerçekleştirilir — Observe zaten o yazma işleminin kendisi, Detect ise "bu Entity/Event/
Investigation izleniyor mu?" kontrolü.

Faz 12 güncellemesi: yukarıdaki "zamanlayıcı olmadan" cümlesi artık tek başına doğru değil.
Reaktif kancalar hâlâ esas yol, ama zamanlanmış tarama (`app/scheduler.py`) bir yazma
işlemine bağlı OLMAYAN tek Observe kaynağı — bu yüzden bildirimi de kendisi tetiklemek
zorunda (`app/scanning.py::_notify_new_observations`, Monitor target_type='Source').

Q24 (Intelligence Prioritization): önem değerlendirmesi confidence, çelişki, independence
(Faz 6), aktif investigation ilişkisi ve novelty (ilk kez mi görülüyor) faktörlerine
dayanıyor — hepsi zaten grafta hesaplı/hesaplanabilir durumda, ekstra bir sinyal
(geographic/temporal significance, entity importance gibi) v1'de yok (bilinçli sınırlama,
YAGNI — bkz. Roadmap.md Faz 7 notları).

Q13: bildirim eşiği sabit + kullanıcı manuel ayarlıyor — bkz. `data/config/inbox_settings.json`
(collector_allowlist.json ile aynı dosya-tabanlı desen).
Q14: Ignore/Confirm/Reject/Investigate/Follow davranışı InboxItem.status'a loglanır, v1'de
prioritization algoritmasını otomatik ETKİLEMEZ.
"""
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.confidence import CORROBORATED_THRESHOLD, HIGH_CONFIDENCE_THRESHOLD, SUPPORTED_THRESHOLD
from app.db import DATA_ROOT, atomic_write_text, fetch_all, fetch_one
from app.models import PRIORITY_ORDER

INBOX_SETTINGS_PATH = DATA_ROOT / "config" / "inbox_settings.json"
DEFAULT_INBOX_SETTINGS = {"min_priority": "INFO"}

_ACTIVE_INVESTIGATION_STATUSES = ("OPEN", "ACTIVE", "PAUSED")


def load_inbox_settings() -> dict:
    if not INBOX_SETTINGS_PATH.is_file():
        return dict(DEFAULT_INBOX_SETTINGS)
    try:
        settings = json.loads(INBOX_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Bozuk ayar dosyası her claim yazımını (bildirim adımı) düşürmemeli.
        return dict(DEFAULT_INBOX_SETTINGS)
    if not isinstance(settings, dict) or settings.get("min_priority") not in PRIORITY_ORDER:
        return dict(DEFAULT_INBOX_SETTINGS)
    return settings


def save_inbox_settings(settings: dict) -> None:
    atomic_write_text(INBOX_SETTINGS_PATH, json.dumps(settings, ensure_ascii=False, indent=2))


def find_monitor(conn, target_type: str, target_id: str) -> dict | None:
    return fetch_one(
        conn.execute(
            "MATCH (m:Monitor {target_type: $tt, target_id: $tid, active: true}) "
            "RETURN m.id AS id, m.label AS label",
            {"tt": target_type, "tid": target_id},
        )
    )


def has_active_investigation(conn, target_type: str, target_id: str) -> bool:
    if target_type == "Entity":
        rel = "INCLUDES"
    elif target_type == "Event":
        rel = "INVESTIGATES"
    else:
        return False
    rows = fetch_all(
        conn.execute(
            f"MATCH (i:Investigation)-[:{rel}]->(t {{id: $id}}) "
            "WHERE i.status IN $statuses RETURN i.id AS id",
            {"id": target_id, "statuses": list(_ACTIVE_INVESTIGATION_STATUSES)},
        )
    )
    return bool(rows)


@dataclass
class PriorityInputs:
    item_type: str
    confidence: float | None = None
    has_contradiction: bool = False
    active_investigation: bool = False
    independence: float | None = None
    is_novel: bool = False
    # Faz 12: ham gözlemde (henüz claim değil) confidence yoktur — bu yüzden önemin tek
    # ölçülebilir girdisi, içeriğin zaten bildiğimiz bir entity'ye değip değmediğidir.
    mentions_known_entity: bool = False


def claim_headline(text: str, limit: int = 90) -> str:
    """Claim metninin başlık gibi okunan ilk satırı.

    Faz 11 (dogfooding F46): `Claim.text` bileşik bir alan — RSS'ten gelen içerik "başlık

özet"
    biçiminde tek bir string olarak saklanıyor, ayrı bir başlık alanı yok. Bu yüzden her
    render eden yer ilk satırı KENDİ çıkarmak zorunda, ve unutan her yer bozuk çıktı üretiyor.
    Aynı hata üç ayrı yerde çıktı: F19 (entity vault notu), F43 (investigation vault notu) ve
    burada (Inbox bildirim başlığı — `text[:80]` boş satırın ötesine taşıp cümleyi ortasından
    kesiyordu). Ortak yardımcı, dördüncüsünü önlemek için.

    Kalıcı çözüm (Faz 13): `Claim`e ayrı bir `title` alanı, ya da tüm render yollarının tek
    bir noktadan geçmesi."""
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:limit] + ("…" if len(line) > limit else "")
    return "(boş claim)"


def compute_priority(inputs: PriorityInputs) -> str:
    """Deterministik, açıklanabilir kural tablosu (Auditability — confidence.py ile aynı
    disiplin). Çelişkiler her zaman en az HIGH; aktif bir investigation'daki bir çelişki
    CRITICAL (kullanıcının o an üzerinde çalıştığı bir şey aniden çelişiyor demektir)."""
    if inputs.has_contradiction:
        return "CRITICAL" if inputs.active_investigation else "HIGH"

    # Faz 12 — zamanlanmış taramadan gelen yeni içerik. Confidence yok (bu henüz bir claim
    # değil, ham gözlem), dolayısıyla kural tamamen "bildiğimiz bir şeye değiyor mu"ya
    # dayanıyor: aktif bir investigation'daki entity'den bahseden bir haber, kullanıcının o
    # an üzerinde çalıştığı şeye dokunuyor demektir.
    if inputs.item_type == "NEW_OBSERVATION":
        if inputs.active_investigation:
            return "HIGH"
        if inputs.mentions_known_entity:
            return "MEDIUM"
        return "LOW"

    # Bozuk bir toplayıcı, sessiz kalması en pahalı olan şeydir (kullanıcı sistemin izlediğini
    # sanmaya devam eder) ama acil de değildir — sabit MEDIUM.
    if inputs.item_type == "SCAN_FAILED":
        return "MEDIUM"

    # Investigation durum geçişleri confidence-tabanlı değil — kullanıcı bilinçli olarak
    # izlediği bir investigation'ın OPEN/ACTIVE/PAUSED/RESOLVED/CLOSED/ARCHIVED arasında
    # geçmesi kendi başına dikkate değer bir olaydır, sabit MEDIUM.
    if inputs.item_type == "INVESTIGATION_UPDATE":
        return "MEDIUM"

    # Faz 36 — izlenen altyapıdaki değişiklik. "Sömürülmeye başladı" ve "yaptırım listesine
    # girdi" eyleme dönük olgular (HIGH; aktif bir investigation'daysa CRITICAL); DNS, sertifika,
    # kayıt değişikliği dikkat ister ama acil değildir (MEDIUM).
    if inputs.item_type == "SELECTOR_ALERT":
        return "CRITICAL" if inputs.active_investigation else "HIGH"
    if inputs.item_type == "SELECTOR_CHANGE":
        return "MEDIUM"

    confidence = inputs.confidence or 0.0

    if inputs.active_investigation and confidence >= HIGH_CONFIDENCE_THRESHOLD:
        return "CRITICAL"
    if inputs.active_investigation and confidence >= SUPPORTED_THRESHOLD:
        return "HIGH"
    if inputs.active_investigation:
        return "MEDIUM"

    if confidence >= CORROBORATED_THRESHOLD:
        return "MEDIUM"
    if inputs.is_novel or confidence >= SUPPORTED_THRESHOLD:
        return "LOW"
    return "INFO"


def create_inbox_item(
    conn,
    *,
    item_type: str,
    priority: str,
    title: str,
    detail: dict,
    target_type: str,
    target_id: str,
    monitor_id: str | None,
) -> dict:
    item_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    conn.execute(
        "CREATE (:InboxItem {id: $id, item_type: $item_type, priority: $priority, "
        "title: $title, detail: $detail, target_type: $target_type, target_id: $target_id, "
        "monitor_id: $monitor_id, status: 'NEW', created_at: $now, actioned_at: NULL})",
        {
            "id": item_id,
            "item_type": item_type,
            "priority": priority,
            "title": title,
            "detail": json.dumps(detail, ensure_ascii=False),
            "target_type": target_type,
            "target_id": target_id,
            "monitor_id": monitor_id,
            "now": now,
        },
    )
    return {"id": item_id, "created_at": now}


def _subject_id(detail: dict) -> str:
    """Bildirimin KONUSU olan nesnenin id'si — dedup anahtarının ikinci yarısı.

    Hedef (`target_id`) tek başına yetmiyor: aynı entity hakkında iki farklı claim değişirse
    ikisi de bildirilmeli. Konu, detayda taşınan claim/event/investigation id'sidir."""
    for key in ("claim_id", "event_id", "investigation_id", "schedule_id", "subject_id"):
        value = detail.get(key)
        if value:
            return str(value)
    return ""


def _pending_item_for(conn, target_type: str, target_id: str, item_type: str, subject_id: str) -> dict | None:
    rows = fetch_all(
        conn.execute(
            "MATCH (n:InboxItem) WHERE n.status = 'NEW' AND n.target_type = $tt AND n.target_id = $tid "
            "AND n.item_type = $it RETURN n.id AS id, n.detail AS detail",
            {"tt": target_type, "tid": target_id, "it": item_type},
        )
    )
    for row in rows:
        try:
            detail = json.loads(row["detail"] or "{}")
        except (TypeError, ValueError):
            detail = {}
        if _subject_id(detail) == subject_id:
            return row
    return None


def notify_if_monitored(
    conn,
    *,
    target_type: str,
    target_id: str,
    item_type: str,
    title: str,
    detail: dict,
    confidence: float | None = None,
    has_contradiction: bool = False,
    independence: float | None = None,
    is_novel: bool = False,
    mentions_known_entity: bool = False,
    active_investigation: bool | None = None,
) -> dict | None:
    """Change Detection'ın 'Detect -> Evaluate -> Notify' kısmı: hedef izleniyor mu diye
    bakar (Compare With Memory zaten çağıranın confidence/contradiction hesaplamasında
    yapılmış oluyor), izleniyorsa önceliği hesaplayıp Inbox'a bir öğe düşürür. İzlenmiyorsa
    hiçbir şey yapmaz — 'more signal, less noise' (madde 25)."""
    monitor = find_monitor(conn, target_type, target_id)
    if monitor is None:
        return None

    # Faz 12: hedef bir Source olduğunda "aktif investigation" o kaynağın kendisinden değil,
    # topladığı içerikte geçen entity'lerden gelir — çağıran bunu hesaplayıp geçirir.
    if active_investigation is None:
        active_investigation = has_active_investigation(conn, target_type, target_id)
    priority = compute_priority(
        PriorityInputs(
            item_type=item_type,
            confidence=confidence,
            has_contradiction=has_contradiction,
            active_investigation=active_investigation,
            independence=independence,
            is_novel=is_novel,
            mentions_known_entity=mentions_known_entity,
        )
    )
    detail = {
        **detail,
        "confidence": confidence,
        "independence": independence,
        "active_investigation": active_investigation,
    }
    # Faz 23: aynı olgu birden çok kez bildirilmez.
    #
    # Ölçüm (2026-09-08): Inbox'taki 17 "sinyal" öğesi aslında ~7 ayrı olguydu — bir
    # claim'in confidence'ı her yeniden hesaplandığında (yeni doğrulama bağı, yeni kanıt)
    # YENİ bir Inbox öğesi yaratılıyordu. Tek bir claim 4 kez, bir diğeri 3 kez düşmüştü.
    # Kullanıcının henüz karar vermediği (NEW) bir öğe varsa, ikincisini yaratmak yerine onu
    # güncelliyoruz: bildirilen şey aynı olgunun GÜNCEL hâli, ikinci bir haber değil.
    #
    # Karara bağlanmış (IGNORED/CONFIRMED/...) bir öğe engel değil — kullanıcı ona baktıktan
    # sonra durum yeniden değiştiyse bu gerçekten yeni bir haberdir.
    existing = _pending_item_for(conn, target_type, target_id, item_type, _subject_id(detail))
    if existing is not None:
        conn.execute(
            "MATCH (n:InboxItem {id: $id}) SET n.priority = $priority, n.title = $title, "
            "n.detail = $detail, n.created_at = $now",
            {
                "id": existing["id"],
                "priority": priority,
                "title": title,
                "detail": json.dumps(detail, ensure_ascii=False),
                "now": datetime.now(timezone.utc),
            },
        )
        return {"id": existing["id"], "priority": priority, "monitor_id": monitor["id"], "deduped": True}

    item = create_inbox_item(
        conn,
        item_type=item_type,
        priority=priority,
        title=title,
        detail=detail,
        target_type=target_type,
        target_id=target_id,
        monitor_id=monitor["id"],
    )
    return {**item, "priority": priority, "monitor_id": monitor["id"]}


def priority_at_least(priority: str, min_priority: str) -> bool:
    return PRIORITY_ORDER.get(priority, 0) <= PRIORITY_ORDER.get(min_priority, 0)
