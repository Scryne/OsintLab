"""
Kuyruk tazeliği: değerlendirilmeden bekleyen gözlemlerin otomatik yaşlanması.

**Neden var (ölçüm, 2026-10-31).** Otomatik tarama günde ~94 gözlem getiriyor, yarısı yüksek
sinyalli. 2.611 bekleyen gözlemin 1.323'ü yüksek sinyal, en eskisi 50 günlük; kuyruk hiç
küçülmüyordu. Sıralama yanlış değil: Scryne'ın promote ettiği 261 gözlemin 119'u yalnız OpenAI,
Google gibi "yaygın" entity'lere değiyor, yani yaygın entity'yi zayıflatmak ilgiyi kaçırırdı.
Aynı hikâyeyi gruplamak kuyruğu yalnız ~%12 küçültüyor (1.323 → ~1.170). Eksik olan bir tazelik
kuralıydı: değerlendirilmeyen haber sonsuza dek bekliyordu.

**Kural.** Değerlendirilmeden belirli bir süre geçen gözlem otomatik ELENİR — silinmez (Q17),
gerekçesi yazılır ve Gözlemler sayfasından tek tıkla geri alınır. Promote bu modülde yok ve
olmayacak: bilgi grafına giren her şey insan kararıdır (Design Principle #7).

**Hiç yaşlanmayanlar.** Elle yüklenmiş belge, elle girilmiş gözlem, izlenen bir entity ya da açık
bir investigation'a değen gözlem. Bunlar kullanıcının bilerek önemsediği şeyler.
"""
import logging
import os
from datetime import datetime, timezone

from app.db import bump_data_version, graph_lock
from app.models import ObservationDismiss
from app import triage

logger = logging.getLogger(__name__)

# Gün cinsinden bekleme süreleri. Düşük sinyalli gözlem bir haftada bakılmadıysa bakılmayacak;
# yüksek sinyalli bir haber üç hafta sonra hâlâ okunmadıysa analiz değeri büyük ölçüde gitmiş olur.
# Kararlı durumda kuyruk ≈ (günlük düşük × 7) + (günlük yüksek × 21) ≈ 330 + 990 gözlem.
LOW_SIGNAL_DAYS = int(os.environ.get("OSINTLAB_AGE_LOW_DAYS", "7"))
HIGH_SIGNAL_DAYS = int(os.environ.get("OSINTLAB_AGE_HIGH_DAYS", "21"))

# Kapatmak için: `OSINTLAB_QUEUE_AGING=0`.
ENV_FLAG = "OSINTLAB_QUEUE_AGING"

EXEMPT_CODES = frozenset({"FROM_DOCUMENT", "MANUAL_ENTRY", "MONITORED_ENTITY", "ACTIVE_INVESTIGATION"})

REASON_PREFIX = "Otomatik yaşlanma"

_last_run: dict = {"at": None, "dismissed": 0, "low": 0, "high": 0}


def enabled() -> bool:
    return os.environ.get(ENV_FLAG, "1").strip().lower() not in ("0", "false", "off", "no")


def is_exempt(item) -> bool:
    return any(reason.code in EXEMPT_CODES for reason in item.signal_reasons)


def age_limit_days(item) -> int:
    return HIGH_SIGNAL_DAYS if item.signal_score >= triage.HIGH_SIGNAL_THRESHOLD else LOW_SIGNAL_DAYS


def reason_for(limit_days: int, high: bool) -> str:
    level = "yüksek" if high else "düşük"
    return f"{REASON_PREFIX}: {limit_days} gün içinde değerlendirilmedi ({level} sinyal). Geri alınabilir."


def due_for_aging(items, *, now: datetime) -> dict[str, list[str]]:
    """Yaşlanma süresini doldurmuş gözlemler, gerekçe metnine göre gruplu (id listeleri)."""
    groups: dict[str, list[str]] = {}
    for item in items:
        if is_exempt(item) or item.created_at is None:
            continue
        limit = age_limit_days(item)
        if (now - item.created_at).days >= limit:
            high = item.signal_score >= triage.HIGH_SIGNAL_THRESHOLD
            groups.setdefault(reason_for(limit, high), []).append(item.id)
    return groups


def age_out(conn, *, now: datetime | None = None) -> dict:
    """Süresi dolan bekleyen gözlemleri gerekçesiyle eler. Döndürür: {dismissed, low, high, at}."""
    now = now or datetime.now(timezone.utc)
    items, _ = triage._score_all(conn)
    groups = due_for_aging(items, now=now)

    result = {"at": now.isoformat(), "dismissed": 0, "low": 0, "high": 0}
    if groups:
        with graph_lock:
            for reason, ids in groups.items():
                done = triage._dismiss(conn, ids, ObservationDismiss(observation_ids=ids, reason=reason))
                result["dismissed"] += done.dismissed
                result["high" if "yüksek sinyal" in reason else "low"] += done.dismissed
        bump_data_version()
    _last_run.update(result)
    if result["dismissed"]:
        logger.info(
            "Kuyruk yaşlanması: %s gözlem elendi (%s düşük, %s yüksek sinyal)",
            result["dismissed"], result["low"], result["high"],
        )
    return result


def last_run() -> dict:
    return dict(_last_run)
