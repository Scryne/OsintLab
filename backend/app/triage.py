"""
Faz 16 — Promote Kuyruğu (değerlendirme darboğazı).

**Neden var (ölçüm, 2026-09-05).** 224 gözlemin 223'ü promote edilmemişti. Bu bir bug değil:
promote, ham gözlemin Knowledge Graph'a gerçek olarak girdiği adım ve bilinçli olarak insan
kararı (Design Principle #7). Ama Faz 12 toplama tarafını otomatikleştirdi, değerlendirme
tarafı elle kaldı — sistem kendi kendine gözlem biriktiriyor, hiçbiri bilgiye dönüşmüyordu.

**Bu modülün aldığı karar: kararı insandan ALMAK değil, kararı ucuzlatmak.** Üç şey yapar:

1. `build_queue` — bekleyen gözlemleri sinyale göre sıralar. Sinyal, Faz 12'nin zaten
   kullandığı kuralın (`scanning.match_entities_in_text`) aynısı: gözlem bildiğimiz bir
   şeye değiyor mu. Deterministik, LLM'siz, ve her puan bir gerekçe listesiyle birlikte
   dönüyor — 180 kaydı toplu elerken kullanıcının neye güvendiğini bilmesi gerekiyor.
2. `dismiss` — ilgisiz gözlemleri toplu eler. Elenen gözlem SİLİNMEZ, "değerlendirildi,
   bilgiye dönüştürülmedi" olarak işaretlenir (Q17: yükselmeyen şey de kaybolmaz). İşaret
   ayrıca elenmiş gözlemin ertesi gün kuyruğa geri düşmemesi için gerekli.
3. `undismiss` — eleme geri alınabilir. Toplu bir işlemin geri dönüşü yoksa kullanıcı onu
   kullanmaz; kuyruğu eritmenin önündeki engel tam da bu tereddüt olurdu.

**Otomatik promote kuralı bu modülde YOK ve bu bilinçli.** Roadmap'in Faz 16 maddesi: önce
kuyruk kurulur, gerçek kuyruk bir kez elle eritilir, hangi kuralın güvenli olduğu ancak o
deneyimden sonra bilinir. Kuralı deneyimden önce yazmak, Faz 12'de yapılan hatanın
(roadmap'in "otomatik geçer" varsayımının yanlış çıkması) aynısı olurdu.
"""
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.db import fetch_all, fetch_one
from app.models import (
    ObservationDismiss,
    ObservationDismissResult,
    ObservationQueue,
    QueueHostBucket,
    QueueItem,
    QueueStats,
    SignalReason,
)
from app.monitoring import _ACTIVE_INVESTIGATION_STATUSES
from app.scanning import load_entity_rows, match_entities_in_text

logger = logging.getLogger(__name__)

# Sinyal ağırlıkları. Toplam bir olasılık değil, bir SIRALAMA aracı — confidence.py'nin
# formülüyle karıştırılmamalı: orada bir iddianın ne kadar doğru olduğu hesaplanıyor, burada
# bir gözlemin insan bakışını ne kadar hak ettiği. Değerler tek bir kurala göre seçildi:
# "bildiğimiz bir entity'ye değmek" tek başına eşiği geçirmeli, geri kalan her şey ancak onu
# kuvvetlendirmeli. Kaynak güvenilirliği kendi başına eşiği geçiremez — güvenilir bir feed'in
# ilgisiz haberi hâlâ ilgisizdir.
SIGNAL_WEIGHTS = {
    "KNOWN_ENTITY": 0.40,
    "ACTIVE_INVESTIGATION": 0.25,
    "MONITORED_ENTITY": 0.15,
    "FROM_DOCUMENT": 0.20,
    "MANUAL_ENTRY": 0.15,
    "SOURCE_RELIABILITY": 0.10,
    # --- Faz 27: graf'ın Faz 12'den sonra kazandığı eksenler ---
    #
    # Ölçüm (2026-09-09, 142 bekleyen gözlem): skor dağılımı iki noktaya çökmüştü — 114 öğe
    # 0.07'de, 26 öğe 0.47'de. Ateşleyen tek gerçek ölçüt KNOWN_ENTITY'ydi; graf o günden
    # beri 58 entity, 80 ilişki, 6 olay ve 100 değme kazandı ve HİÇBİRİ skora girmiyordu.
    #
    # Aşağıdaki ağırlıkların hepsi, eklemeden ÖNCE gerçek kuyrukta kaç kez ateş ettiği
    # ölçülerek seçildi (Faz 20'nin dersi: gürültü maliyeti tahmin edilmez, ölçülür):
    #   EVENT_MATCH 5, RELATED_PAIR 5, MULTI_ENTITY 9, PENDING_CANDIDATE 26,
    #   DISMISSED_CANDIDATE 3.
    #
    # Ölçülüp ELENEN İKİ aday var, ikisi de "ateş ediyor ama ayırt etmiyor" diye:
    #   - **Doğrulama benzerliği** ("bu gözlem var olan bir claim'i doğruluyor olabilir",
    #     başlık token'larının Jaccard'ı): 142 öğenin yalnızca 1'i 0.20'yi geçti, 80'i 0.1
    #     bandında yığıldı.
    #   - **THIN_ENTITY** ("hakkında az şey bildiğimiz entity'ye değiyor"): kuyrukta 23 kez
    #     ateşledi ve iyi görünüyordu, ama grafın kendisi ölçülünce çöktü — 58 entity'nin
    #     56'sının HİÇ claim'i yok, 1'inin 28'i var. Yani "ince entity" pratikte tüm
    #     entity'ler demek: KNOWN_ENTITY'nin sabit bir yol arkadaşı, ayrı bir bilgi değil.
    #     (Asıl bulgu bu değil zaten: claim-entity bağının bu kadar seyrek olması Faz 21'in
    #     alanına giren ayrı bir sorun.)
    #
    # Hiçbiri tek başına eşiği geçirmiyor: "bak" demenin yolu hâlâ bildiğimiz bir şeye
    # değmek. Bunlar sıralamayı ayrıştırır, kapıyı açmaz.
    "EVENT_MATCH": 0.20,
    "RELATED_PAIR": 0.15,
    "MULTI_ENTITY": 0.10,
    "PENDING_CANDIDATE": 0.15,
    "DISMISSED_CANDIDATE": -0.10,
    "HOST_HISTORY": 0.15,
}

# Bu eşiğin ÜSTÜ "bak", altı "toplu elenebilir". Tam olarak KNOWN_ENTITY ağırlığına eşit:
# eşiği geçmenin tek yolu bildiğimiz bir şeye değmek. Faz 27'nin eklediği pozitif sinyallerin
# hiçbiri tek başına buraya ulaşmıyor (en büyüğü 0.20) — bu bilinçli: yeni eksenler sıralamayı
# ayrıştırsın diye eklendi, "insan baksın" kararının tanımını genişletsin diye değil.
HIGH_SIGNAL_THRESHOLD = 0.40

# Faz 27 — Q14'ün v1 kararının gözden geçirilmesi.
#
# Sinyalin İŞARETİ de ölçümle seçildi. İlk hali negatifti ("çok elediğin kaynağı aşağı çek",
# -0.15 × oran) ve dağılımı BOZDU: entity eşleşmesi olmayan bir gözlemin tabanı yalnızca
# SOURCE_RELIABILITY (0.07) olduğu için ceza tabanı eziyor, 59 öğe 0.0'da yeni bir yığın
# oluşturuyordu — kırmaya çalıştığımız problemin aynısı, sadece başka bir noktada. Aynı bilgi
# pozitif yazıldığında (az elediğin kaynak PUAN KAZANIR) sıralama monoton biçimde yayılıyor
# ve taban hiç görünmüyor. Bilgi aynı, davranış farklı.
#
# Q13/Q14: "kullanıcının davranışı loglanır ama v1'de prioritization'ı otomatik ETKİLEMEZ."
# Gerekçesi opak bir geri besleme döngüsü kurmamaktı ve v1'de doğruydu: elde karar yoktu.
# Bugün 377 gözlemin 180'i elle elenmiş durumda ve ölçüm şunu söylüyor — host bazında eleme
# oranı, graf'taki HERHANGİ bir sinyalden daha ayırt edici:
#     theregister %0, arstechnica %0, wired %0, theverge %42, securityaffairs %44,
#     openai %46, techcrunch %53, krebsonsecurity %81, cisa.gov %88, bleepingcomputer %93
# Bu, kullanıcının kendi açıklanmış tercihidir ve onu yok saymak kuyruğu her gün yeniden
# aynı elle temizletmek demekti.
#
# **Payda "karar verilmiş" olmalı, "toplanmış" değil.** İlk ölçümde oran elenmiş/TOPLAM
# alınmıştı ve yanıltıcıydı: arstechnica ve wired "%0 eleniyor" görünüyordu, oysa o 30
# gözlemin hiçbirine daha bakılmamıştı (Faz 24'te eklenen taze kaynaklar). Doğru payda
# elenmiş + claim üretmiş; o hesapla tablo tamamen değişiyor:
#     openai %51 (58 karar), securityaffairs %69 (23), theverge %82 (45), techcrunch %82 (52),
#     krebsonsecurity %90 (10), bleepingcomputer %93 (15), cisa.gov %100 (30).
# Kararı olmayan kaynak (arstechnica, wired, theregister) bu sinyali HİÇ almaz — "bilinmiyor"
# ile "hep eleniyor" aynı şey değildir ve bilinmeyene uydurma bir değer atamak, ölçmediğimiz
# şeyi ölçmüş gibi göstermek olurdu.
#
# Döngü riski üç şekilde sınırlandı: (1) ağırlık küçük ve yalnızca NEGATİF — hiçbir şeyi
# kuyruktan çıkarmaz, sadece aşağı sıralar; (2) yeterli kanıt şartı var (aşağıdaki eşik) —
# üç kayıtlık bir host'un oranı istatistik değil gürültüdür; (3) gerekçe listesinde AÇIKÇA
# yazılır ("bu kaynağın %88'ini eledin"), yani kullanıcı skorun neden düştüğünü görür ve
# host filtresiyle o kaynağın tamamını her an tam olarak görebilir.
HOST_RATE_MIN_DECIDED = 10

# Aday adı eşleşmesinin asgari uzunluğu — `scanning.MIN_ENTITY_MATCH_LENGTH` ile aynı
# gerekçe: kısa desen her metinde tutar.
MIN_CANDIDATE_MATCH_LENGTH = 4


def normalize_host(url: str | None) -> str | None:
    """`www.` kırpılmış host. Kaynak eşleştirmesi ve kuyruk gruplaması aynı normalizasyonu
    kullanmalı; ayrı ayrı yazılsaydı "theverge.com" ve "www.theverge.com" iki farklı kova
    olurdu ve toplu eleme yarım iş yapardı."""
    if not url:
        return None
    try:
        host = (urlparse(url).netloc or "").lower().strip()
    except ValueError:
        return None
    if not host:
        return None
    host = host.split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _name_in(text_low: str, name: str) -> bool:
    """Kelime sınırlı ad araması. `scanning.match_entities_in_text` ile AYNI disiplin:
    düz `in` kontrolü "Meta"yı "metadata" içinde bulurdu."""
    needle = (name or "").strip().lower()
    if len(needle) < MIN_CANDIDATE_MATCH_LENGTH:
        return False
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", text_low) is not None


# ---- Bağlam yükleme (kuyruk başına BİR kez) ------------------------------

def _load_context(conn) -> dict:
    """Skorlama için gereken graf bilgisi, gözlem başına değil kuyruk başına okunur.

    F58'de collector tarafında öğrenilen ders: 223 satırlık bir listede satır başına sorgu
    atmak kuyruğu kullanılamaz hale getirir."""
    entity_rows = load_entity_rows(conn)

    monitored = {
        row["target_id"]
        for row in fetch_all(
            conn.execute(
                "MATCH (m:Monitor) WHERE m.active = true AND m.target_type = 'Entity' "
                "RETURN m.target_id AS target_id"
            )
        )
    }
    investigated = {
        row["id"]
        for row in fetch_all(
            conn.execute(
                "MATCH (i:Investigation)-[:INCLUDES]->(e:Entity) WHERE i.status IN $statuses "
                "RETURN e.id AS id",
                {"statuses": list(_ACTIVE_INVESTIGATION_STATUSES)},
            )
        )
    }

    # Kaynak önerisi host üzerinden: gözlem bir Source'a bağlı DEĞİL (bağ promote anında
    # kuruluyor), ama zamanlanmış tarama onu bir Source'un feed'inden çekti. Host eşleşmesi
    # bu kaybolan bağı geri kurmanın deterministik yolu — ve yalnızca ÖNERİ, kararı kullanıcı
    # veriyor.
    source_by_host: dict[str, dict] = {}
    for row in fetch_all(
        conn.execute(
            "MATCH (s:Source) RETURN s.id AS id, s.name AS name, s.url AS url, "
            "s.reliability AS reliability"
        )
    ):
        host = normalize_host(row["url"])
        # İlk gelen kazanır: aynı host'ta iki kaynak varsa hangisinin önerileceği keyfi
        # olurdu; öneriyi kullanıcı zaten değiştirebiliyor.
        if host and host not in source_by_host:
            source_by_host[host] = row

    # --- Faz 27: graf'ın yeni eksenleri ---
    # Hepsi kuyruk başına BİR kez okunuyor; gözlem başına sorgu 142 satırlık bir listede
    # N+1 olurdu (F58'in dersi, bu modülün en başındaki gerekçenin aynısı).
    entity_to_event: dict[str, set[str]] = {}
    for row in fetch_all(
        conn.execute("MATCH (e:Entity)-[:INVOLVED_IN]->(ev:Event) "
                     "RETURN e.id AS entity_id, ev.id AS event_id, ev.title AS title")
    ):
        entity_to_event.setdefault(row["entity_id"], set()).add(row["title"] or row["event_id"])

    related_pairs = {
        frozenset((row["a"], row["b"]))
        for row in fetch_all(
            conn.execute(
                "MATCH (a:Entity)-[r:ENTITY_RELATION]->(b:Entity) WHERE r.status = 'ACTIVE' "
                "RETURN a.id AS a, b.id AS b"
            )
        )
    }

    # Entity adayları: claim metinlerinden çıkarılmış ama henüz karara bağlanmamış adlar.
    # Ölçümün en beklenmedik sonucu buydu — kuyruğun 142 öğesinin 116'sında hiçbir entity
    # eşleşmiyor ve o yığını kırabilen tek pozitif sinyal bu: 23 öğe, bilinen bir entity'ye
    # değmediği halde, claim'lerde tekrar eden bir adı içeriyor.
    #
    # `entity_candidates` adayları her çağrıda claim metinlerinden yeniden çıkarıyor
    # (deterministik, saklanmıyor — bkz. app/entityextract.py). Kuyruk başına bir kez.
    from app.entityextract import entity_candidates

    pending_candidate_names: list[str] = []
    dismissed_candidate_names: list[str] = []
    try:
        for cand in entity_candidates(conn, include_decided=True):
            if cand["status"] == "PENDING":
                pending_candidate_names.append(cand["name"])
            elif cand["status"] == "DISMISSED":
                dismissed_candidate_names.append(cand["name"])
    except Exception:  # noqa: BLE001 - aday çıkarma kuyruğu ASLA düşürmemeli
        logger.exception("Entity adayları çıkarılamadı; kuyruk bu sinyal olmadan kuruluyor")

    # Host bazında eleme oranı (Q14 revizyonu, ağırlığın başındaki nota bak).
    host_totals: dict[str, dict] = {}
    for row in fetch_all(
        conn.execute(
            "MATCH (o:Observation) WHERE o.source_url IS NOT NULL "
            "OPTIONAL MATCH (o)-[:PRODUCED]->(c:Claim) "
            "RETURN o.source_url AS url, o.dismissed AS dismissed, c.id AS claim_id"
        )
    ):
        host = normalize_host(row["url"])
        if not host:
            continue
        bucket = host_totals.setdefault(host, {"decided": 0, "dismissed": 0})
        # "Karar verilmiş" = elenmiş YA DA claim üretmiş. Bekleyenler paydaya girmiyor:
        # girseydi taze toplanmış bir feed, henüz bakılmadığı için "az eleniyor" görünürdü —
        # ilk ölçümde tam olarak bu oldu (yukarıdaki nota bak).
        #
        # `promoted` alanı TEK BAŞINA yetmiyor: eşiği geçmeyen bir promote de gerçek bir
        # karardır ama `promoted` false kalır (F32). Claim üretmiş olmak doğru ölçüt.
        if row["dismissed"] or row["claim_id"]:
            bucket["decided"] += 1
            if row["dismissed"]:
                bucket["dismissed"] += 1
    host_dismiss_rate = {
        host: b["dismissed"] / b["decided"]
        for host, b in host_totals.items()
        if b["decided"] >= HOST_RATE_MIN_DECIDED
    }

    return {
        "entity_rows": entity_rows,
        "monitored": monitored,
        "investigated": investigated,
        "source_by_host": source_by_host,
        "entity_to_event": entity_to_event,
        "related_pairs": related_pairs,
        "pending_candidate_names": pending_candidate_names,
        "dismissed_candidate_names": dismissed_candidate_names,
        "host_dismiss_rate": host_dismiss_rate,
        "host_totals": host_totals,
    }


# ---- Skorlama ------------------------------------------------------------

def score_observation(observation, ctx: dict) -> tuple[float, list[SignalReason], list[dict], dict]:
    """Bir gözlemin sinyal puanı, gerekçeleri, eşleşen entity'leri ve önerileri.

    Puan tek bir sayı olarak dönseydi kuyruk bir kara kutu olurdu. Her gerekçe kendi
    ağırlığını taşıyor; toplam bunların toplamı (1.0'da kırpılmış) — kullanıcı bir satırın
    neden üstte olduğunu açıp görebiliyor (Auditability)."""
    reasons: list[SignalReason] = []
    matched = match_entities_in_text(ctx["entity_rows"], observation.raw_content)

    if matched:
        names = list(dict.fromkeys(m["name"] for m in matched))
        reasons.append(
            SignalReason(
                code="KNOWN_ENTITY",
                text=f"Bildiğimiz entity'ye değiyor: {', '.join(names)}",
                weight=SIGNAL_WEIGHTS["KNOWN_ENTITY"],
            )
        )
        in_investigation = [m for m in matched if m["id"] in ctx["investigated"]]
        if in_investigation:
            reasons.append(
                SignalReason(
                    code="ACTIVE_INVESTIGATION",
                    text=(
                        "Açık bir investigation'ın kapsamındaki entity: "
                        + ", ".join(dict.fromkeys(m["name"] for m in in_investigation))
                    ),
                    weight=SIGNAL_WEIGHTS["ACTIVE_INVESTIGATION"],
                )
            )
        monitored = [m for m in matched if m["id"] in ctx["monitored"]]
        if monitored:
            reasons.append(
                SignalReason(
                    code="MONITORED_ENTITY",
                    text="İzlemeye alınmış entity: "
                    + ", ".join(dict.fromkeys(m["name"] for m in monitored)),
                    weight=SIGNAL_WEIGHTS["MONITORED_ENTITY"],
                )
            )

        # --- Faz 27: graf'ın eksenleri ---
        event_titles: list[str] = []
        for m in matched:
            event_titles.extend(ctx["entity_to_event"].get(m["id"], ()))
        event_titles = list(dict.fromkeys(event_titles))
        if event_titles:
            reasons.append(
                SignalReason(
                    code="EVENT_MATCH",
                    text="Bilinen bir olayın tarafı: " + ", ".join(event_titles),
                    weight=SIGNAL_WEIGHTS["EVENT_MATCH"],
                )
            )

        unique_ids = list(dict.fromkeys(m["id"] for m in matched))
        if len(unique_ids) >= 2:
            reasons.append(
                SignalReason(
                    code="MULTI_ENTITY",
                    text=f"Aynı gözlemde {len(unique_ids)} bilinen entity birlikte geçiyor",
                    weight=SIGNAL_WEIGHTS["MULTI_ENTITY"],
                )
            )
            by_id = {m["id"]: m["name"] for m in matched}
            pairs = [
                (by_id[a], by_id[b])
                for i, a in enumerate(unique_ids)
                for b in unique_ids[i + 1:]
                if frozenset((a, b)) in ctx["related_pairs"]
            ]
            if pairs:
                reasons.append(
                    SignalReason(
                        code="RELATED_PAIR",
                        text="Aralarında zaten kurulmuş bir ilişki olan entity'ler: "
                        + ", ".join(f"{a} ↔ {b}" for a, b in pairs),
                        weight=SIGNAL_WEIGHTS["RELATED_PAIR"],
                    )
                )


    if observation.from_evidence:
        # Belge kuyruğa kendi kendine düşmedi; kullanıcı onu bilerek yükledi. Pasif bir
        # feed öğesiyle aynı sırada bekletmek yanlış olurdu.
        reasons.append(
            SignalReason(
                code="FROM_DOCUMENT",
                text=(
                    "Elle yüklenmiş bir belgeden çıkarıldı"
                    + (f" ({observation.from_evidence.file_name})" if observation.from_evidence.file_name else "")
                ),
                weight=SIGNAL_WEIGHTS["FROM_DOCUMENT"],
            )
        )
    elif not observation.source_url:
        reasons.append(
            SignalReason(
                code="MANUAL_ENTRY",
                text="Elle girilmiş gözlem — otomatik toplanmadı",
                weight=SIGNAL_WEIGHTS["MANUAL_ENTRY"],
            )
        )

    host = normalize_host(observation.source_url)
    source = ctx["source_by_host"].get(host) if host else None
    if source:
        weight = round(SIGNAL_WEIGHTS["SOURCE_RELIABILITY"] * (source["reliability"] or 0.0), 3)
        reasons.append(
            SignalReason(
                code="SOURCE_RELIABILITY",
                text=f"Tanınan kaynak: {source['name']} (güvenilirlik {source['reliability']:.2f})",
                weight=weight,
            )
        )

    # Entity adayı eşleşmesi — `matched` bloğunun DIŞINDA, bilerek: bu sinyalin bütün değeri
    # bilinen hiçbir entity'ye değmeyen gözlemlerde. Ölçüm: 26 öğede ateşliyor, 23'ünde
    # başka hiçbir pozitif sinyal yok.
    low = (observation.raw_content or "").lower()
    pending_hits = [n for n in ctx["pending_candidate_names"] if _name_in(low, n)]
    if pending_hits:
        reasons.append(
            SignalReason(
                code="PENDING_CANDIDATE",
                text="Claim'lerde tekrar eden, henüz karara bağlanmamış ad: "
                + ", ".join(pending_hits[:5]),
                weight=SIGNAL_WEIGHTS["PENDING_CANDIDATE"],
            )
        )
    dismissed_hits = [n for n in ctx["dismissed_candidate_names"] if _name_in(low, n)]
    if dismissed_hits:
        reasons.append(
            SignalReason(
                code="DISMISSED_CANDIDATE",
                text="Entity olmadığına karar verdiğin ad(lar) geçiyor: "
                + ", ".join(dismissed_hits[:5]),
                weight=SIGNAL_WEIGHTS["DISMISSED_CANDIDATE"],
            )
        )

    # Q14 revizyonu (ağırlık tablosundaki uzun nota bak): kullanıcının bu kaynakta verdiği
    # kararlar. Ağırlık TUTMA oranıyla ölçekleniyor — çok elediğin bir kaynak ceza almaz,
    # yalnızca bu puanı kazanamaz. Hiçbir şeyi gizlemez, yalnızca sıralar.
    rate = ctx["host_dismiss_rate"].get(host) if host else None
    if rate is not None:
        totals = ctx["host_totals"].get(host, {})
        decided = totals.get("decided", 0)
        kept = decided - totals.get("dismissed", 0)
        reasons.append(
            SignalReason(
                code="HOST_HISTORY",
                text=(
                    f"Bu kaynakta karar verdiğin {decided} gözlemin {kept}'ini tutmuşsun "
                    f"(%{(1 - rate) * 100:.0f})"
                ),
                weight=round(SIGNAL_WEIGHTS["HOST_HISTORY"] * (1 - rate), 3),
            )
        )

    if observation.injection_hits:
        # Ağırlığı bilerek 0: bu bir sinyal değil, bir UYARI. Puanı yükseltseydi bir prompt
        # injection denemesi kendini kuyruğun tepesine taşıyabilirdi — Q22'nin tam tersi.
        reasons.append(
            SignalReason(
                code="INJECTION_WARNING",
                text=f"Metinde talimat-görünümlü {len(observation.injection_hits)} ifade var — puana etkisi yok, dikkat gerektirir",
                weight=0.0,
            )
        )

    if observation.text_source == "ocr":
        reasons.append(
            SignalReason(
                code="OCR_TEXT",
                text="Metin OCR ile tahmin edildi, belgenin kendi metin katmanı değil",
                weight=0.0,
            )
        )

    # Faz 27 ile negatif ağırlıklar da var; alt sınır 0 — eksi bir sıralama puanı
    # "eleme kararı" gibi okunurdu, oysa bu modül karar vermiyor, sıralıyor.
    score = round(max(0.0, min(1.0, sum(r.weight for r in reasons))), 3)
    suggestion = {
        "suggested_source_id": source["id"] if source else None,
        "suggested_source_name": source["name"] if source else None,
        # Birden fazla entity eşleşirse ilki önerilir; kullanıcı diyalogda değiştirebilir.
        # Faz 11'in F15/F16 dersi: entity bağı atlanabiliyorsa sonradan onarılabilir olmalı.
        "suggested_entity_id": matched[0]["id"] if matched else None,
        "host": host,
    }
    return score, reasons, matched, suggestion


# ---- Kuyruk --------------------------------------------------------------

_PENDING_WHERE = (
    "o.promoted = false AND (o.dismissed IS NULL OR o.dismissed = false)"
)


def _pending_observations(conn) -> list:
    """Bekleyen gözlemler: promote edilmemiş, elenmemiş ve HİÇ claim üretmemiş.

    Üçüncü koşul şart: eşiği geçmeyen bir promote de bir Claim üretir ve `promoted` false
    kalır (F32). O gözlem değerlendirilmiştir — kuyrukta durursa kullanıcı aynı kararı ikinci
    kez vermeye çalışır ve 409 alır."""
    # Geç import: routers.observations bu modülü kendisi import ediyor (döngüyü kırar).
    # scanning.py'nin `collect_from_url` içindeki aynı deseni izliyor.
    from app.routers.observations import _FIELDS_FULL, _FROM_EVIDENCE, _PRODUCED, _observation_from_row

    rows = fetch_all(
        conn.execute(
            f"MATCH (o:Observation) WHERE {_PENDING_WHERE} {_PRODUCED}{_FROM_EVIDENCE}"
            f"RETURN {_FIELDS_FULL} ORDER BY o.created_at DESC"
        )
    )
    return [_observation_from_row(row) for row in rows if not row.get("produced_claim_id")]


def _counts(conn) -> dict:
    """Kuyruk sağlığı sayaçları. Roadmap: '221 rakamı ancak API'ye elle sorulunca çıktı.'"""
    total = fetch_one(conn.execute("MATCH (o:Observation) RETURN count(o) AS n"))["n"]
    dismissed = fetch_one(
        conn.execute("MATCH (o:Observation) WHERE o.dismissed = true RETURN count(o) AS n")
    )["n"]
    return {"total": total, "dismissed": dismissed}


def build_queue(
    conn,
    *,
    limit: int = 200,
    offset: int = 0,
    host: str | None = None,
    max_score: float | None = None,
    min_score: float | None = None,
) -> ObservationQueue:
    """Bekleyen gözlemler, sinyale göre sıralı, kuyruk sağlığıyla birlikte.

    `stats` her zaman kuyruğun TAMAMI üzerinden hesaplanır, sayfalanmış `items` üzerinden
    değil — yoksa "kaç gözlem bekliyor" sorusu sayfa boyutuna göre farklı cevap verirdi.
    `host`/`max_score` filtreleri toplu eleme içindir: "bu feed'in tamamı" ya da "sinyalsiz
    olanların tamamı" tek seferde seçilebilsin diye."""
    ctx = _load_context(conn)
    pending = _pending_observations(conn)

    scored: list[QueueItem] = []
    now = datetime.now(timezone.utc)
    for observation in pending:
        score, reasons, matched, suggestion = score_observation(observation, ctx)
        created = observation.created_at
        age_days = max(0, (now - created).days) if created else 0
        scored.append(
            QueueItem(
                **observation.model_dump(),
                signal_score=score,
                signal_reasons=reasons,
                matched_entities=matched,
                age_days=age_days,
                **suggestion,
            )
        )

    # İstatistikler filtreden ÖNCE, kuyruğun tamamı üzerinden.
    counts = _counts(conn)
    high = sum(1 for item in scored if item.signal_score >= HIGH_SIGNAL_THRESHOLD)
    buckets: dict[str, dict] = {}
    for item in scored:
        key = item.host or "(adres yok)"
        bucket = buckets.setdefault(key, {"count": 0, "high_signal": 0})
        bucket["count"] += 1
        if item.signal_score >= HIGH_SIGNAL_THRESHOLD:
            bucket["high_signal"] += 1
    oldest = min((item.created_at for item in scored), default=None)

    stats = QueueStats(
        pending=len(scored),
        dismissed=counts["dismissed"],
        # "Değerlendirilmiş" = kuyruktan çıkmış her şey: promote edilmiş, eşik altı claim
        # üretmiş ya da elenmiş.
        evaluated=counts["total"] - len(scored) - counts["dismissed"],
        total=counts["total"],
        high_signal=high,
        noise=len(scored) - high,
        oldest_pending_at=oldest,
        oldest_pending_age_days=max(0, (now - oldest).days) if oldest else None,
        hosts=sorted(
            (QueueHostBucket(host=k, **v) for k, v in buckets.items()),
            key=lambda b: (-b.count, b.host),
        ),
    )

    filtered = scored
    if host:
        wanted = normalize_host(f"//{host}") or host.lower()
        filtered = [i for i in filtered if (i.host or "(adres yok)") in (wanted, host)]
    # `min_score` KAPSAYICI (>=), `max_score` DIŞLAYICI (<). Simetrik olmamaları bilinçli:
    # kuyruğun iki yakası tam olarak HIGH_SIGNAL_THRESHOLD'da ayrılıyor ve ikisi de kapsayıcı
    # olsaydı eşiğe tam oturan bir gözlem hem "yüksek sinyal" hem "gürültü" listesinde
    # çıkardı — toplu elemede bu, bakılması gereken bir kaydın yanlışlıkla elenmesi demek.
    if max_score is not None:
        filtered = [i for i in filtered if i.signal_score < max_score]
    if min_score is not None:
        filtered = [i for i in filtered if i.signal_score >= min_score]

    # Eşit puanda yeni olan üstte: aynı derecede ilgili iki haberden taze olanı üzerine iş
    # yapılabilir olandır.
    filtered.sort(key=lambda i: (-i.signal_score, -(i.created_at.timestamp() if i.created_at else 0)))

    return ObservationQueue(
        stats=stats,
        items=filtered[offset : offset + limit],
        matched=len(filtered),
        high_signal_threshold=HIGH_SIGNAL_THRESHOLD,
    )


def suggestions_for(conn, observations: list) -> dict[str, dict]:
    """Verilen gözlemler için kaynak/entity önerileri — bağlam bir kez yüklenerek.

    Toplu promote'un ihtiyacı: kullanıcı kümeye tek bir kaynak dayatmak yerine "her kayıt
    kendi önerisini kullansın" diyebiliyor (kuyrukta gördüğü öneriler zaten bunlar)."""
    ctx = _load_context(conn)
    return {o.id: score_observation(o, ctx)[3] for o in observations}


# ---- Eleme ---------------------------------------------------------------

def dismiss(conn, payload: ObservationDismiss) -> ObservationDismissResult:
    """Gözlemleri "değerlendirildi, bilgiye dönüştürülmedi" olarak işaretler — SİLMEZ.

    Claim üretmiş bir gözlem elenmez: o zaten değerlendirilmiş ve grafta bir karşılığı var;
    onu "elendi" diye işaretlemek kaydın geçmişini yanlış anlatırdı. Bulunamayan/atlanan
    id'ler sessizce yutulmuyor, `skipped` içinde dönüyor."""
    ids = [i for i in dict.fromkeys(payload.observation_ids) if i]
    if not ids:
        return ObservationDismissResult(dismissed=0, skipped=[])

    rows = fetch_all(
        conn.execute(
            "MATCH (o:Observation) WHERE o.id IN $ids "
            "OPTIONAL MATCH (o)-[:PRODUCED]->(c:Claim) "
            "RETURN o.id AS id, o.promoted AS promoted, c.id AS claim_id",
            {"ids": ids},
        )
    )
    found = {row["id"]: row for row in rows}
    eligible = [i for i in ids if i in found and not found[i]["claim_id"] and not found[i]["promoted"]]
    skipped = [i for i in ids if i not in eligible]

    if eligible:
        conn.execute(
            "MATCH (o:Observation) WHERE o.id IN $ids "
            "SET o.dismissed = true, o.dismissed_at = $now, o.dismiss_reason = $reason",
            {
                "ids": eligible,
                "now": datetime.now(timezone.utc),
                "reason": (payload.reason or "").strip() or None,
            },
        )
    return ObservationDismissResult(dismissed=len(eligible), skipped=skipped)


def undismiss(conn, observation_ids: list[str]) -> ObservationDismissResult:
    """Elemeyi geri alır — gözlem kuyruğa döner.

    Geri dönüşü olmayan bir toplu işlem kullanılmaz; kuyruğu eritmenin önündeki asıl engel
    "yanlış seçersem ne olur" tereddüdü olurdu."""
    ids = [i for i in dict.fromkeys(observation_ids) if i]
    if not ids:
        return ObservationDismissResult(dismissed=0, skipped=[])
    rows = fetch_all(
        conn.execute(
            "MATCH (o:Observation) WHERE o.id IN $ids AND o.dismissed = true RETURN o.id AS id",
            {"ids": ids},
        )
    )
    eligible = [row["id"] for row in rows]
    if eligible:
        conn.execute(
            "MATCH (o:Observation) WHERE o.id IN $ids "
            "SET o.dismissed = false, o.dismissed_at = NULL, o.dismiss_reason = NULL",
            {"ids": eligible},
        )
    return ObservationDismissResult(
        dismissed=len(eligible), skipped=[i for i in ids if i not in eligible]
    )
