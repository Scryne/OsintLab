"""
Continuous Monitoring + Change Detection + Intelligence Inbox (Faz 7, madde 22-27).

Observe -> Detect -> Evaluate -> Compare With Memory -> Update -> Notify döngüsü, ayrı bir
arka plan zamanlayıcı OLMADAN, mevcut yazma noktalarına (claim oluşturma, çelişki tespiti,
investigation geçişi, entity-event ilişkilendirme) kanca atılarak REAKTİF şekilde
gerçekleştirilir — Observe zaten o yazma işleminin kendisi, Detect ise "bu Entity/Event/
Investigation izleniyor mu?" kontrolü.

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
from pathlib import Path

from app.confidence import CORROBORATED_THRESHOLD, HIGH_CONFIDENCE_THRESHOLD, SUPPORTED_THRESHOLD
from app.db import fetch_all, fetch_one
from app.models import PRIORITY_LEVELS, PRIORITY_ORDER

INBOX_SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "config" / "inbox_settings.json"

_ACTIVE_INVESTIGATION_STATUSES = ("OPEN", "ACTIVE", "PAUSED")


def load_inbox_settings() -> dict:
    if not INBOX_SETTINGS_PATH.is_file():
        return {"min_priority": "INFO"}
    return json.loads(INBOX_SETTINGS_PATH.read_text(encoding="utf-8"))


def save_inbox_settings(settings: dict) -> None:
    INBOX_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    INBOX_SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


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

    # Investigation durum geçişleri confidence-tabanlı değil — kullanıcı bilinçli olarak
    # izlediği bir investigation'ın OPEN/ACTIVE/PAUSED/RESOLVED/CLOSED/ARCHIVED arasında
    # geçmesi kendi başına dikkate değer bir olaydır, sabit MEDIUM.
    if inputs.item_type == "INVESTIGATION_UPDATE":
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
) -> dict | None:
    """Change Detection'ın 'Detect -> Evaluate -> Notify' kısmı: hedef izleniyor mu diye
    bakar (Compare With Memory zaten çağıranın confidence/contradiction hesaplamasında
    yapılmış oluyor), izleniyorsa önceliği hesaplayıp Inbox'a bir öğe düşürür. İzlenmiyorsa
    hiçbir şey yapmaz — 'more signal, less noise' (madde 25)."""
    monitor = find_monitor(conn, target_type, target_id)
    if monitor is None:
        return None

    active_investigation = has_active_investigation(conn, target_type, target_id)
    priority = compute_priority(
        PriorityInputs(
            item_type=item_type,
            confidence=confidence,
            has_contradiction=has_contradiction,
            active_investigation=active_investigation,
            independence=independence,
            is_novel=is_novel,
        )
    )
    detail = {
        **detail,
        "confidence": confidence,
        "independence": independence,
        "active_investigation": active_investigation,
    }
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
