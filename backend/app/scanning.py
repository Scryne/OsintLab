"""
Faz 12 — Zamanlanmış Otomatik Tarama.

Bu modül "bir tarama ne yapar" sorusunun cevabı; "ne zaman çalışır" sorusu `app/scheduler.py`
içinde. `POST /collectors/fetch` (elle tarama, Faz 5/10) ve zamanlanmış koşu aynı çekirdeği
(`collect_from_url`) kullanır — güvenlik katmanı (allowlist + SSRF, `app/collector.py`) ve
dedup mantığı iki yol için de birebir aynı.

**Faz 12'nin planında yanlış olan varsayım.** Roadmap "yeni Observation'lar mevcut promote/
notify pipeline'ından otomatik geçer, ek bir entegrasyon gerekmiyor" diyordu. Gerçek bunun
tersi: Faz 7'nin bildirim boru hattı `create_claim`/`promote` üzerine kancalı, promote ise
elle atılan bir adım (Design Principle #7 — kaynağı, entity'yi ve confidence girdilerini
insan seçer). Yani zamanlanmış tarama tek başına HİÇBİR bildirim üretmezdi: gözlemler
sessizce birikir, kullanıcı bakmayı akıl edene kadar hiçbir şey söylenmezdi — otomatik
taramanın tek varlık nedeni tam da bunu ortadan kaldırmak. Eksik halka bu dosyadaki
`_notify_new_observations`: Monitor'ün 'Source' hedefi (Faz 12'de eklendi) üzerinden,
promote'u BEKLEMEDEN Inbox'a bir öğe düşürür.

Öncelik, ham gözlemde henüz confidence olmadığı için (o daha claim değil) içeriğin
bildiğimiz bir şeye değip değmediğinden türetilir — bkz. `_matching_entities`.
"""
import logging
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from app.collector import (
    CollectorFetchError,
    CollectorSecurityError,
    extract_content_from_html,
    load_allowlist,
    parse_rss,
    parse_telegram,
    safe_fetch,
    telegram_preview_url,
)
from app.db import fetch_all, fetch_one, get_connection, graph_lock
from app.models import Observation
from app.monitoring import claim_headline, has_active_investigation, notify_if_monitored
from app.vault import safe_render_vault

logger = logging.getLogger(__name__)

# Bir entity adının/alias'ının metinde aranması için asgari uzunluk. Çok kısa adlar
# ("AB", "IT", "X") gündelik metinde her yerde geçer; eşleşme sinyal değil gürültü olurdu.
#
# Faz 21'de 4'ten 3'e indirildi. Sebep: 4, OSINT'te en sık kullanılan kısaltma boyunu —
# üç harfli akronimleri (AWS, NYT, AFP, FBI) — TAMAMEN dışarıda bırakıyordu; "AWS" adında
# bir entity yaratılabiliyor ve hiçbir metinde asla eşleşemiyordu (Faz 21 ölçümünde geriye
# kalan TEK izole entity buydu). Gürültü maliyeti tahmin edilmedi, ölçüldü: eşiği 3'e
# indirmek 68 bekleyen gözlemde HİÇBİR yeni eşleşme üretmedi, 54 claim'de yalnızca 1 doğru
# eşleşme ekledi (AWS). 2 harfe inmek ölçülmedi ve inilmedi — "AB"/"IT" riski orada gerçek.
MIN_ENTITY_MATCH_LENGTH = 3

# Üst üste bu kadar başarısızlıktan SONRA (tam olarak bu koşuda, bir kez) Inbox'a düşer.
# Faz 11'in tekrar eden dersi: sessizce ölen bir mekanizma, hiç kurulmamış olmaktan kötüdür —
# çünkü kullanıcı kurulduğunu sanır.
FAILURE_NOTIFY_THRESHOLD = 3

# Başarısız taramada aralık katlanarak uzar (1 hata → 2x, 2 → 4x, 3+ → 8x). Kalıcı olarak
# ölmüş bir feed'i her 3 saatte bir yeniden denemek ne bize ne karşı tarafa bir şey kazandırır;
# ama tamamen durdurmuyoruz da — geçici kesintiler kendiliğinden toparlansın.
MAX_BACKOFF_FACTOR = 8

_SCHEDULE_FIELDS = (
    "s.id AS id, s.url AS url, s.mode AS mode, s.interval_minutes AS interval_minutes, "
    "s.item_limit AS item_limit, s.since_days AS since_days, s.label AS label, "
    "s.active AS active, s.last_run_at AS last_run_at, s.last_status AS last_status, "
    "s.last_error AS last_error, s.last_new_count AS last_new_count, "
    "s.consecutive_failures AS consecutive_failures, s.created_at AS created_at, "
    "src.id AS source_id, src.name AS source_name"
)
_SCHEDULE_MATCH = "MATCH (s:ScanSchedule)-[:SCANS_SOURCE]->(src:Source) "


# ---- Toplama çekirdeği ---------------------------------------------------

def _select_items(items: list[dict], *, limit: int, since_days: int | None) -> list[dict]:
    """Faz 11 (F2): feed'in tamamı yerine en yeni `limit` item, opsiyonel zaman penceresiyle.

    Yayın tarihi olmayan item'lar pencere filtresinde ELENMEZ (tarihsiz diye bilgi kaybetmeyi
    tarih uydurmaya tercih ediyoruz), ama sıralamada en sona düşerler."""
    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        items = [i for i in items if i["published"] is None or i["published"] >= cutoff]
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    items = sorted(items, key=lambda i: i["published"] or oldest, reverse=True)
    return items[:limit]


def _existing_pairs(urls: list[str]) -> set[tuple[str, str]]:
    """Faz 11 (F3): daha önce aynı URL'den aynı içerikle gelmiş observation'ların kümesi.

    Dedup anahtarı bilerek (source_url, raw_content) — sadece URL olsaydı Faz 7'nin change
    detection'ı kırılırdı: aynı sayfa değişmiş içerikle yeniden tarandığında yeni bir
    observation oluşması GEREKİYOR. Değişmemişse oluşmamalı.

    Faz 12'de bu kural zamanlanmış taramanın da temeli: aynı feed her 3 saatte bir yeniden
    okunuyor, gözlem yalnızca gerçekten yeni olan öğeler için üretiliyor."""
    unique = sorted({u for u in urls if u})
    if not unique:
        return set()
    rows = fetch_all(
        get_connection().execute(
            "MATCH (o:Observation) WHERE o.source_url IN $urls "
            "RETURN o.source_url AS source_url, o.raw_content AS raw_content",
            {"urls": unique},
        )
    )
    return {(r["source_url"], r["raw_content"]) for r in rows}


def collect_from_url(url: str, mode: str, *, limit: int, since_days: int | None) -> dict:
    """Bir adresi güvenli şekilde çeker ve yeni içerikleri Observation'a çevirir.

    `CollectorSecurityError` (biz reddettik: allowlist/SSRF) ve `CollectorFetchError` (karşı
    taraf reddetti) ayrı ayrı yükselir — çağıran katman bu ayrımı korumalı (F25)."""
    # Geç import: routers.observations -> routers.claims -> ... zincirini modül yüklenirken
    # değil, çağrı anında kurar (döngüsel import'u önler).
    from app.routers.observations import create_observation_record

    allowlist = load_allowlist()
    if mode == "telegram":
        # `@kanal`, `t.me/kanal` ya da tam önizleme adresi kabul edilir; istek hep önizlemeye gider.
        preview = telegram_preview_url(url)
        if preview is None:
            raise CollectorFetchError(f"Telegram kanal adı tanınamadı: {url!r} (ör. @kanal ya da https://t.me/s/kanal)")
        url = preview
    final_url, content, content_type = safe_fetch(url, allowlist)

    if mode == "rss":
        parsed_items = parse_rss(content, final_url)
        available = len(parsed_items)
        # Faz 11 (F25, ikinci savunma): 200 döndüren ama feed olmayan bir yanıt da sessiz
        # sıfıra yol açar (ör. giriş/onay sayfası, "moved" HTML'i). Gerçekten boş bir feed
        # XML content-type'la gelir; HTML gelip 0 item çıkıyorsa bu boşluk değil, yanlış
        # içeriktir — ayırt edip söylüyoruz.
        if available == 0 and "xml" not in content_type.lower():
            raise CollectorFetchError(
                f"Yanıt bir feed değil: {content_type or 'tür belirtilmemiş'} döndü ve hiç "
                f"öğe ayrıştırılamadı ({final_url}). Adres bir RSS/Atom feed'i mi, yoksa "
                "normal bir sayfa mı? Sayfaysa 'web' modunu dene."
            )
        selected = _select_items(parsed_items, limit=limit, since_days=since_days)
        candidates = [
            {"text": i["text"], "url": i["link"] or final_url, "published": i["published"]}
            for i in selected
        ]
    elif mode == "telegram":
        parsed_items = parse_telegram(content)
        available = len(parsed_items)
        if available == 0 and "tgme_channel_info" not in content.decode("utf-8", errors="replace"):
            raise CollectorFetchError(
                f"Telegram kanal önizlemesi bulunamadı ({final_url}). Kanal özel olabilir ya da "
                "herkese açık önizlemesi kapalı olabilir."
            )
        # En yeni mesajlar sayfanın sonunda; seçim yayın tarihine göre (RSS ile aynı kural).
        selected = _select_items(parsed_items, limit=limit, since_days=since_days)
        candidates = [{"text": i["text"], "url": i["link"], "published": i["published"]} for i in selected]
    else:
        available = 1
        candidates = [{"text": extract_content_from_html(content), "url": final_url, "published": None}]

    created: list[Observation] = []
    skipped = 0
    # Dedup kontrolü ile yazma arasına başka bir yazma girmemeli: aynı feed elle "şimdi tara"
    # ile zamanlayıcının turuna denk gelirse ikisi de "yok" görüp her öğeyi iki kez yazıyordu.
    # Ağ beklemesi (safe_fetch) kilidin DIŞINDA kaldı — yalnızca bu kısa bölüm kilitli.
    with graph_lock:
        seen = _existing_pairs([c["url"] for c in candidates])
        for c in candidates:
            key = (c["url"], c["text"])
            if key in seen:
                skipped += 1
                continue
            created.append(
                create_observation_record(
                    raw_content=c["text"], observed_at=c["published"], source_url=c["url"],
                    # Faz 25: gözlemin metninin HANGİ yoldan çıktığı kayda geçiyor. Bu alan
                    # DOCINT'te ("ocr"/"extracted") zaten aynı işi görüyordu; collector tarafı
                    # boş bırakıyordu ve sonuç şuydu: elimizde bozuk bir metin varken onun
                    # RSS özeti mi yoksa web sayfası dökümü mü olduğunu ancak tahmin
                    # edebiliyorduk. Yeniden ayrıştırma (`POST /collectors/reparse`) yalnızca
                    # "web" olanları hedefleyebilsin diye yazılıyor.
                    text_source=mode,
                )
            )
            seen.add(key)

    return {
        "final_url": final_url,
        "content_type": content_type,
        "items_available": available,
        "items_considered": len(candidates),
        "observations": created,
        "duplicates_skipped": skipped,
    }


# ---- Bildirim (Faz 7 boru hattına zamanlanmış taramanın bağlanması) -------

def load_entity_rows(conn) -> list[dict]:
    """Eşleştirme için gereken minimum entity alanları. Faz 16'da ayrıldı: kuyruk 200+
    gözlemi tek tek eşleştiriyor, her biri için entity tablosunu yeniden okumak N+1 olurdu."""
    return fetch_all(
        conn.execute("MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.aliases AS aliases")
    )


@lru_cache(maxsize=16384)
def _word_pattern(needle: str) -> re.Pattern:
    return re.compile(rf"(?<!\w){re.escape(needle)}(?!\w)")


def contains_word(blob_low: str, needle_low: str) -> bool:
    """`needle_low`, `blob_low` içinde kelime sınırlarıyla geçiyor mu (ikisi de küçük harf).

    2026-10-18 denetiminde ölçüldü: kuyruk (3.363 gözlem × 582 aday adı) her çağrıda deseni
    yeniden derliyordu — `re` modülünün 512'lik önbelleği bu kadar adı tutamadığı için her
    arama bir derleme demekti ve `/observations/queue` 292 sn sürüyordu. Düz alt-dize kontrolü
    kelime-sınırlı eşleşmenin gerekli koşulu: önce o (C hızında) eleniyor, regex yalnızca
    adayın metinde gerçekten geçtiği nadir durumda ve önbellekten derlenmiş desenle çalışıyor.
    Sonuç kümesi birebir aynı."""
    if needle_low not in blob_low:
        return False
    return _word_pattern(needle_low).search(blob_low) is not None


def match_entities_in_text(entity_rows: list[dict], text: str) -> list[dict]:
    """Bir metinde adı/alias'ı geçen, halihazırda bildiğimiz entity'ler.

    Bu, Faz 7'nin "Compare With Memory" adımının ham gözlem için yapılabilen halidir: gözlemin
    henüz confidence'ı yok (claim değil), dolayısıyla önemi ancak "bildiğimiz bir şeye
    değiyor mu" sorusundan türetilebilir. Deterministik ve açıklanabilir — LLM yok, eşik yok,
    sadece isim eşleşmesi; hangi ad üzerinden eşleştiği Inbox öğesinin detayında saklanıyor
    (Auditability). Faz 16'da kuyruğun sinyal skoru da aynı fonksiyonu kullanıyor — iki farklı
    "bu önemli mi" tanımı olsaydı Inbox ile kuyruk aynı gözleme ters cevap verirdi."""
    blob = text.lower()
    matched: list[dict] = []
    for row in entity_rows:
        for name in [row["name"], *(row["aliases"] or [])]:
            needle = (name or "").strip().lower()
            if len(needle) < MIN_ENTITY_MATCH_LENGTH:
                continue
            # Kelime sınırı şart: düz `in` kontrolü "Meta"yı "metadata" içinde bulur ve her
            # teknoloji haberini o entity'yle ilgili sanardı. Sınır olarak \w kullanılıyor
            # (harf/rakam/alt çizgi) — "Meta's", "(Meta)", "Meta." eşleşmeye devam eder,
            # "metadata" etmez.
            if contains_word(blob, needle):
                matched.append({"id": row["id"], "name": row["name"], "matched_on": name})
                break
    return matched


def _matching_entities(conn, texts: list[str]) -> list[dict]:
    """Bir tarama koşusunun TÜM metinlerinde geçen entity'ler (bildirim başlığı için)."""
    return match_entities_in_text(load_entity_rows(conn), "\n".join(texts))


def _notify_new_observations(conn, schedule: dict, observations: list[Observation]) -> dict | None:
    """Faz 23: bu bildirim ARTIK ÜRETİLMİYOR.

    Ölçüm (2026-09-08): Inbox'taki 59 öğenin **38'i** (%64) buydu — "TechCrunch: 17 yeni
    içerik" gibi. Faz 12'de bu doğru bir karardı: yeni içeriğin geldiğini söyleyen TEK yer
    Inbox'tı. Faz 16 Promote Kuyruğu'nu ve nav'daki canlı sayaç rozetini getirince bu
    bildirim gereksizleşti — üstelik kuyruk daha iyisini söylüyor: hangi gözlem, hangi
    sinyalle, hangi entity'ye değerek. Inbox'ın %64'ü, daha zayıf bir kopyaydı ve kimse fark
    etmedi (iki ölçümde de 0 öğe işlenmişti).

    Kaybolan bir şey yok: koşunun sonucu `ScanSchedule.last_new_count` alanında ve
    Toplayıcılar ekranında duruyor, bekleyen gözlem sayısı nav rozetinde.

    Fonksiyon SİLİNMEDİ, gerekçe burada dursun diye; çağrı noktası da korunuyor ki bir gün
    kaynak-bazlı bildirim gerçekten gerekirse yeri belli olsun."""
    return None


def _notify_new_observations_disabled(conn, schedule: dict, observations: list[Observation]) -> dict | None:
    if not observations:
        return None
    entities = _matching_entities(conn, [o.raw_content for o in observations])
    active_investigation = any(
        has_active_investigation(conn, "Entity", e["id"]) for e in entities
    )
    label = schedule.get("label") or schedule.get("source_name") or schedule["url"]
    return notify_if_monitored(
        conn,
        target_type="Source",
        target_id=schedule["source_id"],
        item_type="NEW_OBSERVATION",
        title=f"{label}: {len(observations)} yeni içerik",
        detail={
            "schedule_id": schedule["id"],
            "url": schedule["url"],
            "observation_ids": [o.id for o in observations],
            # İlk beş başlık: Inbox'ta öğeyi açmadan "bu benim işime yarar mı" kararı
            # verilebilsin diye. claim_headline (F46) bileşik metnin ilk satırını alır.
            "headlines": [claim_headline(o.raw_content) for o in observations[:5]],
            "matched_entities": entities,
        },
        mentions_known_entity=bool(entities),
        active_investigation=active_investigation,
    )


def _notify_scan_failure(conn, schedule: dict, error: str, failures: int) -> dict | None:
    label = schedule.get("label") or schedule.get("source_name") or schedule["url"]
    return notify_if_monitored(
        conn,
        target_type="Source",
        target_id=schedule["source_id"],
        item_type="SCAN_FAILED",
        title=f"{label}: otomatik tarama {failures} kez üst üste başarısız",
        detail={"schedule_id": schedule["id"], "url": schedule["url"], "error": error},
        active_investigation=False,
    )


# ---- Zamanlama durumu ----------------------------------------------------

def get_schedule_row(conn, schedule_id: str) -> dict | None:
    return fetch_one(
        conn.execute(
            f"{_SCHEDULE_MATCH}WHERE s.id = $id RETURN {_SCHEDULE_FIELDS}", {"id": schedule_id}
        )
    )


def list_schedule_rows(conn, *, active: bool | None = None) -> list[dict]:
    if active is None:
        return fetch_all(
            conn.execute(f"{_SCHEDULE_MATCH}RETURN {_SCHEDULE_FIELDS} ORDER BY s.created_at")
        )
    return fetch_all(
        conn.execute(
            f"{_SCHEDULE_MATCH}WHERE s.active = $active RETURN {_SCHEDULE_FIELDS} ORDER BY s.created_at",
            {"active": active},
        )
    )


def effective_interval_minutes(row: dict) -> int:
    """Ardışık hatalarda katlanan gerçek aralık (bkz. MAX_BACKOFF_FACTOR)."""
    failures = row.get("consecutive_failures") or 0
    factor = min(2**failures, MAX_BACKOFF_FACTOR) if failures else 1
    return row["interval_minutes"] * factor


def next_run_at(row: dict) -> datetime | None:
    if not row["active"]:
        return None
    last = row["last_run_at"]
    if last is None:
        # Hiç çalışmamış bir tarama ilk turda çalışır — kullanıcı kurduktan sonra sonucu
        # bir sonraki aralığı beklemeden görsün.
        return row["created_at"]
    return last + timedelta(minutes=effective_interval_minutes(row))


def is_due(row: dict, now: datetime) -> bool:
    # Zaman damgaları db.py'de UTC'ye etiketlenerek okunuyor (F47), burada ek bir
    # normalizasyon gerekmiyor.
    due_at = next_run_at(row)
    return due_at is not None and due_at <= now


def _record_success(conn, schedule_id: str, now: datetime, new_count: int) -> None:
    conn.execute(
        "MATCH (s:ScanSchedule {id: $id}) SET s.last_run_at = $now, s.last_status = 'OK', "
        "s.last_error = NULL, s.last_new_count = $count, s.consecutive_failures = 0",
        {"id": schedule_id, "now": now, "count": new_count},
    )


def _record_failure(conn, schedule_id: str, now: datetime, error: str, failures: int) -> None:
    conn.execute(
        "MATCH (s:ScanSchedule {id: $id}) SET s.last_run_at = $now, s.last_status = 'ERROR', "
        "s.last_error = $error, s.consecutive_failures = $failures",
        {"id": schedule_id, "now": now, "error": error[:1000], "failures": failures},
    )


# ---- Koşu ----------------------------------------------------------------

# Aynı taramanın iki koşusu üst üste binmesin (elle "şimdi tara" + zamanlayıcı turu).
_running: set[str] = set()
_running_lock = threading.Lock()


class ScheduleBusyError(RuntimeError):
    """Bu tarama şu anda zaten çalışıyor."""


def run_schedule(conn, schedule_id: str) -> dict:
    """Tek bir zamanlanmış taramayı ŞİMDİ çalıştırır (aralığa bakmadan).

    Hata yükseltmez — koşu sonucu (OK/ERROR) hem dönüş değerine hem de ScanSchedule'ın
    durumuna yazılır. Zamanlayıcının bir feed'in 502'si yüzünden durmaması gerekiyor.
    Tek istisna: tarama zaten çalışıyorsa `ScheduleBusyError` (ikinci koşu beklemez, düşer)."""
    with _running_lock:
        if schedule_id in _running:
            raise ScheduleBusyError(schedule_id)
        _running.add(schedule_id)
    try:
        return _run_schedule(conn, schedule_id)
    finally:
        with _running_lock:
            _running.discard(schedule_id)


def _run_schedule(conn, schedule_id: str) -> dict:
    schedule = get_schedule_row(conn, schedule_id)
    if schedule is None:
        raise KeyError(schedule_id)

    now = datetime.now(timezone.utc)
    try:
        result = collect_from_url(
            schedule["url"],
            schedule["mode"],
            limit=schedule["item_limit"],
            since_days=schedule["since_days"],
        )
    except Exception as exc:  # noqa: BLE001 — her hata KAYDA geçmeli (aşağıdaki not)
        # Beklenmeyen bir istisna da (bozuk feed'de ayrıştırıcı hatası, DB hatası) başarısız
        # koşu olarak yazılıyor. Yalnızca iki collector hatası yakalandığında geri kalanı
        # `last_run_at`ı ilerletmeden kaçıyor ve tarama her dakika yeniden deneniyordu —
        # backoff da bildirim de devreye girmiyordu (2026-10-18 denetimi, gerçek logda görüldü).
        if not isinstance(exc, (CollectorSecurityError, CollectorFetchError)):
            logger.exception("Zamanlanmış tarama beklenmedik hata verdi: %s", schedule["url"])
            exc = RuntimeError(f"Beklenmeyen hata ({type(exc).__name__}): {exc}")
        failures = (schedule["consecutive_failures"] or 0) + 1
        _record_failure(conn, schedule_id, now, str(exc), failures)
        notified = None
        # Yalnızca eşiğe DEĞDİĞİ koşuda bir kez — her başarısız koşuda bildirmek, bozuk bir
        # feed'i Inbox'ı dolduran bir gürültü kaynağına çevirirdi.
        if failures == FAILURE_NOTIFY_THRESHOLD:
            notified = _notify_scan_failure(conn, schedule, str(exc), failures)
        logger.warning("Zamanlanmış tarama başarısız (%s): %s", schedule["url"], exc)
        return {
            "schedule_id": schedule_id,
            "status": "ERROR",
            "error": str(exc),
            "consecutive_failures": failures,
            "observations_created": 0,
            "notified": notified,
        }

    observations = result["observations"]
    _record_success(conn, schedule_id, now, len(observations))
    notified = _notify_new_observations(conn, schedule, observations)
    if observations:
        # Yeni gözlemler kaynak notunda/dashboard'da görünsün. Gözlem yoksa render etmiyoruz:
        # boşta dönen bir zamanlayıcının her turda tüm vault'u yeniden yazmasına gerek yok.
        safe_render_vault(conn)

    return {
        "schedule_id": schedule_id,
        "status": "OK",
        "final_url": result["final_url"],
        "items_available": result["items_available"],
        "items_considered": result["items_considered"],
        "observations_created": len(observations),
        "observation_ids": [o.id for o in observations],
        "duplicates_skipped": result["duplicates_skipped"],
        "notified": notified,
    }


def run_due_schedules() -> list[dict]:
    """Zamanı gelmiş tüm taramaları sırayla çalıştırır — zamanlayıcının her turda çağırdığı
    tek giriş noktası. Sıralı, çünkü gömülü KùzuDB'ye paralel yazmanın kazandıracağı bir şey
    yok; bir feed'in yavaşlığı en fazla diğerini bir tur geciktirir."""
    conn = get_connection()
    now = datetime.now(timezone.utc)
    due = []
    for row in list_schedule_rows(conn, active=True):
        # Satır başına ayrı try: tek bir bozuk satır (ör. aralığı NULL kalmış eski bir kayıt)
        # bütün taramaların zamanlamasını düşürmemeli.
        try:
            if is_due(row, now):
                due.append(row)
        except Exception:  # noqa: BLE001
            logger.exception("Tarama zamanlaması hesaplanamadı: %s", row.get("id"))
    results = []
    for row in due:
        try:
            results.append(run_schedule(conn, row["id"]))
        except ScheduleBusyError:
            logger.info("Tarama zaten çalışıyor, bu tur atlandı: %s", row["id"][:8])
        except Exception:  # noqa: BLE001 — bir taramanın çökmesi diğerlerini durdurmamalı
            logger.exception("Zamanlanmış tarama beklenmedik şekilde çöktü: %s", row["id"])
    return results


# ---- CRUD ----------------------------------------------------------------

def create_schedule(
    conn,
    *,
    source_id: str,
    url: str,
    mode: str,
    interval_minutes: int,
    item_limit: int,
    since_days: int | None,
    label: str | None,
) -> str:
    schedule_id = str(uuid.uuid4())
    conn.execute(
        "CREATE (:ScanSchedule {id: $id, url: $url, mode: $mode, "
        "interval_minutes: $interval, item_limit: $item_limit, since_days: $since_days, "
        "label: $label, active: true, last_run_at: NULL, last_status: NULL, "
        "last_error: NULL, last_new_count: NULL, consecutive_failures: 0, created_at: $now})",
        {
            "id": schedule_id,
            "url": url,
            "mode": mode,
            "interval": interval_minutes,
            "item_limit": item_limit,
            "since_days": since_days,
            "label": label,
            "now": datetime.now(timezone.utc),
        },
    )
    conn.execute(
        "MATCH (s:ScanSchedule {id: $sid}), (src:Source {id: $src}) CREATE (s)-[:SCANS_SOURCE]->(src)",
        {"sid": schedule_id, "src": source_id},
    )
    return schedule_id
