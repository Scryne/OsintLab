"""
Faz 17 — Corroboration Çalışma Ekranı: "bu iki claim aynı olayı anlatıyor" adayları.

**Neden var (ölçüm, 2026-09-05).** Faz 16 kuyruğu eritti; sonuçta 44 claim'in 43'ü `REPORTED`
kaldı, confidence 0.28–0.30'da toplandı. Sebep bir bug değil: `confidence.py`'de tek kaynaklı
bir claim `SOURCE_QUALITY_WEIGHT (0.40) × güvenilirlik` alıyor, yani `SUPPORTED` eşiği (0.45)
tek kaynakla yapısal olarak erişilemez. Confidence'ın kalan %60'ı (independence 0.25 +
evidence 0.20 + corroboration 0.15) 44 claim'de **sıfır kez** açıldı — mekanizma var
(`CORROBORATES` kenarı, Faz 6 lineage indirgemesi), onu tetikleyecek iş akışı yok. Faz 2'nin
çelişki motorunun Faz 11'e kadar hiç çalışmamış olmasıyla (F26) aynı desen.

**Faz 6'nın ölçüsü bu iş için aday BULUCU değil, DİSKALİFİYE edici.** `lineage.py`'nin
containment'ı TÜRETME (near-duplicate) arıyor ve tam sayfa metni için kalibre edilmişti;
buradaki girdi 143–892 karakterlik RSS başlık+özeti ve aranan şey BAĞIMSIZ aynı-olay raporu,
yani metinler bilerek farklı. Ölçüldü: farklı kaynaklı 601 çiftin hiçbirinde 5-shingle
containment 0.000'ın üstüne çıkmadı. Ama yüksek containment çıksaydı bu, bağımsız doğrulama
DEĞİL, tespit edilmemiş bir syndication olurdu — o yüzden aynı ölçü burada uyarı olarak
kullanılıyor.

**Bulucu sinyal: IDF ağırlıklı nadir terim ortaklığı + zamansal yakınlık.** Gerekçesi ve
eşiklerin nereden geldiği aşağıdaki sabitlerde; tam kalibrasyon Roadmap.md Faz 17 notlarında.
LLM yok — Faz 16'nın sinyal puanındaki disiplinin aynısı: her aday, neden aday olduğunu
gerekçesiyle taşır.
"""
import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.db import fetch_all
from app.lineage import containment_similarity, resolve_independent_root, shingles

logger = logging.getLogger(__name__)

# Nadir terim ortaklığı eşiği. Gerçek veriden seçildi (44 claim, 601 farklı-kaynaklı çift):
# dağılımın medyanı 0.003, p95'i 0.103; gerçek çiftler 0.142–0.418 aralığında. 0.12, üst
# ~%4'ü alıyor — uydurulmuş bir sayı değil, doğru pozitiflerin tabanı ile gürültünün tavanı
# arasındaki boşluk (Faz 6 spike disiplininin aynısı).
RARE_OVERLAP_THRESHOLD = 0.12

# Zamansal pencere. Tek başına nadir terim ortaklığı yetmiyor: eşiği geçen iki yanlış pozitif
# yalnızca genel sözlük paylaşıyordu ve 24 / 14,9 gün arayla yayınlanmışlardı. Gerçek
# çiftlerin tamamı ≤ 2,9 gün. 7 gün marj bırakıyor — bir olay birkaç gün sonra da
# raporlanabilir, ama iki hafta sonrası artık aynı olay değil.
MAX_DAYS_APART = 7

# Bu eşiğin ÜSTÜNDEKİ metin benzerliği, farklı kaynaklar arasında bile, bağımsız doğrulama
# değil TÜRETME işaretidir (Faz 6'nın kendi eşiği). Aday listeden atılmıyor — kullanıcıya
# "bunlar bağımsız olmayabilir, önce kaynak türetmesini işaretle" diye gösteriliyor.
DERIVED_SUSPECT_THRESHOLD = 0.35

# Aynı olayın aynı kaynaktan iki kez kaydedilmiş hali (collector aynı haberi iki farklı
# başlıkla almış). Gerçek veride bir örnek var: containment 0.836.
DUPLICATE_THRESHOLD = 0.50

# Skorlanan gösterilecek ortak terim sayısı — gerekçe okunabilir kalmalı.
TOP_TERMS = 6

# Nadir terim ortaklığına giren metnin ilk N karakteri. Faz 28'de bulundu ve Faz 17'yi de
# ONARIYOR.
#
# `_rare_overlap`ın paydası min() — iki metnin uzunluğu çok farklı olduğunda KISA olanın
# sözlüğü payda oluyor ve uzun metin, kısa metnin terimlerini rastlantıyla kapsayarak yüksek
# skor alıyor. Faz 17'de bu görünmüyordu çünkü tüm claim'ler 143–892 karakterlik RSS
# başlık+özetiydi; iki şey bunu bozdu:
#   - Faz 25 bir claim'i 4801 karaktere onardı (öncesinde 9370'ti) ve o tek claim, canlı aday
#     listesindeki 7 "CORROBORATION" adayının 7'sinde birden taraf oldu — hepsi yanlış.
#   - Faz 28'in havuzuna 20.036 karakterlik CISA advisory'leri girdi; ilk çalıştırmada
#     "Cursor'ın SpaceX tarafından satın alınması" claim'i bir Schneider Electric güvenlik
#     bülteniyle eşleşti.
# Ölçüldü (55 claim × 328 gözlem, 3041 zaman-penceresi içi çift): sınır uygulanınca dağılım
# medyan 0.037 / p99 0.139'a oturuyor ve gerçek çiftler (0.373, 0.447) gürültüden temiz bir
# boşlukla ayrılıyor. Sınırsız halde aynı liste tamamen yanlış pozitiflerle doluydu.
#
# 600 karakter, claim metni medyanının (221) iki katından fazlası: kısa metinlerin hiçbirini
# kırpmıyor, yalnızca rejim değiştiren uzun belgeleri hizaya sokuyor.
RARE_TEXT_CAP = 600

# Claim ↔ GÖZLEM için ayrı ve DAHA YÜKSEK eşik. Gerekçe havuz büyüklüğü: claim tarafında 55
# metin var, gözlem havuzunda 328 — tesadüfi eşleşme şansı bir mertebe fazla. Ölçülen boşluk
# nettir: gerçek çiftler 0.373 ve 0.447, en yüksek yanlış pozitif 0.217. 0.30 tam ortasında.
OBSERVATION_RARE_THRESHOLD = 0.30

_WORD = re.compile(r"[\w']+", re.UNICODE)

# Terim frekansı gürültüsünü azaltan asgari uzunluk + durak kelimeler. Liste bilinçli olarak
# kısa ve İngilizce/Türkçe karışık: IDF zaten yaygın terimleri baskılıyor, durak listesi
# yalnızca 3 harfli gürültüyü eliyor.
_STOP = set(
    """the and for with that this from are was were has have had will would can could not but
    its their they them then than out about after over into more most new news said say says
    ile ama veya için gibi olan olarak daha çok bir bu şu ancak ise ki de da mi mı""".split()
)


def _tokens(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 2 and w not in _STOP}


@dataclass
class CandidatePair:
    # Claim satırlarının kendisi taşınıyor, sadece id'ler değil: çağıran katman aday listesini
    # göstermek için metin/kaynak/confidence'a ihtiyaç duyuyor ve bunları yeniden sorgulamak
    # çift başına N+1 olurdu (Faz 16'da kuyrukta öğrenilen ders).
    a: dict
    b: dict
    # CORROBORATION | DERIVED_SUSPECT | SHARED_ROOT | SAME_SOURCE_DUPLICATE
    kind: str
    rare_overlap: float
    text_similarity: float
    days_apart: float
    shared_terms: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    # Bağlanınca confidence'ın nereye gideceği — bu fazın var olma sebebi tam olarak bu
    # hareket, görünmezse kullanıcı neden uğraştığını bilmez.
    projected_a: float | None = None
    projected_b: float | None = None


def _load_claims(conn) -> list[dict]:
    """Aday aramasına giren claim'ler. `valid_to` dolu olanlar (supersede edilmiş) dışarıda:
    yerini almış bir bilgiyi doğrulamak grafı geriye doğru sağlamlaştırırdı."""
    return fetch_all(
        conn.execute(
            "MATCH (s:Source)-[:ASSERTS]->(c:Claim) WHERE c.valid_to IS NULL "
            "OPTIONAL MATCH (c)-[:ABOUT_ENTITY]->(e:Entity) "
            "OPTIONAL MATCH (c)-[:ABOUT_EVENT]->(ev:Event) "
            "RETURN c.id AS id, c.text AS text, c.valid_from AS valid_from, "
            "c.confidence AS confidence, c.knowledge_state AS knowledge_state, "
            "s.id AS source_id, s.name AS source_name, s.reliability AS reliability, "
            # Faz 28: doğrulayan gözlem promote edilirken aynı hedefe bağlanmalı.
            "e.id AS about_entity_id, ev.id AS about_event_id"
        )
    )


def _existing_links(conn) -> set[frozenset]:
    """Halihazırda bağlı çiftler — aday listede tekrar gösterilmemeli."""
    pairs: set[frozenset] = set()
    for row in fetch_all(
        conn.execute("MATCH (a:Claim)-[:CORROBORATES]->(b:Claim) RETURN a.id AS a, b.id AS b")
    ):
        pairs.add(frozenset((row["a"], row["b"])))
    for row in fetch_all(
        conn.execute("MATCH (a:Claim)-[:CLAIM_CONTRADICTS]->(b:Claim) RETURN a.id AS a, b.id AS b")
    ):
        pairs.add(frozenset((row["a"], row["b"])))
    return pairs


def _idf(claims: list[dict]) -> tuple[list[set[str]], dict[str, float]]:
    docs = [_tokens(c["text"][:RARE_TEXT_CAP]) for c in claims]
    n = len(docs) or 1
    df: Counter = Counter()
    for d in docs:
        df.update(d)
    return docs, {t: math.log(n / count) for t, count in df.items()}


def _rare_overlap(a: set[str], b: set[str], idf: dict[str, float]) -> tuple[float, list[str]]:
    """Ortak terimlerin IDF ağırlıklı oranı.

    Nadir bir terimi paylaşmak ("preparedness", "commandeered", "outage") yaygın bir terimi
    paylaşmaktan çok daha güçlü bir "aynı olay" sinyali. Payda min() — Faz 6'daki containment
    tercihinin aynı gerekçesi: iki metnin uzunluğu çok farklıysa (resmi duyuru vs kısa haber
    özeti) simetrik bir oran haksız yere düşük çıkar."""
    shared = a & b
    if not shared:
        return 0.0, []
    denom = min(sum(idf.get(t, 0.0) for t in a), sum(idf.get(t, 0.0) for t in b))
    if denom <= 0:
        return 0.0, []
    score = sum(idf.get(t, 0.0) for t in shared) / denom
    top = sorted(shared, key=lambda t: -idf.get(t, 0.0))[:TOP_TERMS]
    return round(min(score, 1.0), 4), top


def _days_apart(a, b) -> float:
    if a is None or b is None:
        return 0.0
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    return abs((a - b).total_seconds()) / 86400


def _projected_confidence(claim: dict, corroborator_count: int, independent: bool) -> float:
    """Bağlantı kurulunca confidence'ın nereye gideceğinin ÖNİZLEMESİ.

    `confidence.py`'nin formülü burada tekrar edilmiyor — gerçek hesap bağlantı kurulduğunda
    `_gather_confidence_inputs` üzerinden yapılıyor. Bu yalnızca kullanıcıya "buna değer mi"
    dedirtecek kadarını gösteren bir tahmin ve claim'in mevcut kanıt/çelişki durumunu
    bilmediği için ihtiyatlı: yalnızca corroboration'ın EKLEYECEĞİ katkıyı ekliyor."""
    from app.confidence import (
        CORROBORATION_SATURATION,
        CORROBORATION_WEIGHT,
        INDEPENDENCE_SATURATION,
        INDEPENDENCE_WEIGHT,
    )

    added = CORROBORATION_WEIGHT * min(corroborator_count / CORROBORATION_SATURATION, 1.0)
    if independent:
        added += INDEPENDENCE_WEIGHT * min(corroborator_count / INDEPENDENCE_SATURATION, 1.0)
    return round(min((claim["confidence"] or 0.0) + added, 1.0), 4)


def find_candidates(
    conn,
    *,
    claim_id: str | None = None,
    include_linked: bool = False,
    limit: int = 200,
) -> list[CandidatePair]:
    """Aynı olayı anlatıyor olabilecek claim çiftleri, gerekçeleriyle ve sınıflandırılmış.

    `claim_id` verilirse yalnızca o claim'i içeren çiftler döner (claim detay sayfası için)."""
    claims = _load_claims(conn)
    if len(claims) < 2:
        return []

    docs, idf = _idf(claims)
    linked = set() if include_linked else _existing_links(conn)
    # Bağımsız kök çözümü claim başına bir kez — çift başına çözmek O(n²) graf sorgusu olurdu.
    roots = {c["source_id"]: resolve_independent_root(conn, c["source_id"]) for c in claims}
    shingle_cache: dict[str, set[str]] = {}

    def _shingles(claim: dict) -> set[str]:
        if claim["id"] not in shingle_cache:
            shingle_cache[claim["id"]] = shingles(claim["text"])
        return shingle_cache[claim["id"]]

    out: list[CandidatePair] = []
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            a, b = claims[i], claims[j]
            if claim_id and claim_id not in (a["id"], b["id"]):
                continue
            if frozenset((a["id"], b["id"])) in linked:
                continue

            rare, terms = _rare_overlap(docs[i], docs[j], idf)
            if rare < RARE_OVERLAP_THRESHOLD:
                continue
            days = _days_apart(a["valid_from"], b["valid_from"])
            similarity = containment_similarity(_shingles(a), _shingles(b))
            same_source = a["source_id"] == b["source_id"]
            same_root = roots[a["source_id"]] == roots[b["source_id"]]

            # Sınıflandırma. Sıra önemli: bağımsızlık İLK bakılan şey, çünkü aynı köke inen
            # iki claim ne kadar benzer olursa olsun birbirini DOĞRULAYAMAZ — `independence`
            # skoru ham Source sayısını değil bağımsız kök sayısını kullanıyor (Q6).
            if same_source:
                if similarity < DUPLICATE_THRESHOLD:
                    # Aynı kaynağın aynı konudaki iki AYRI haberi. Ne doğrulama ne yineleme —
                    # gösterilecek bir şey yok, listeyi şişirir.
                    continue
                kind = "SAME_SOURCE_DUPLICATE"
                reasons = [
                    f"Aynı kaynak ({a['source_name']}) — bağımsız doğrulama olamaz",
                    f"Metinler neredeyse aynı (benzerlik {similarity:.2f}): aynı haber iki kez kaydedilmiş görünüyor",
                ]
            elif same_root:
                # Faz 6'nın tam konusu: Source'lar FARKLI ama DERIVED_FROM zinciri ikisini de
                # aynı köke indiriyor. Kullanıcının "iki farklı site, demek ki iki kaynak"
                # diye okuması en olası yer burası — ve bu okuma confidence'ı sahte
                # yükseltirdi. Yineleme eşiğine takılmıyor: türetilmiş bir kopya yeniden
                # yazılmış olabilir, benzerlik düşük olsa bile bağımsız DEĞİL.
                if days > MAX_DAYS_APART and similarity < DERIVED_SUSPECT_THRESHOLD:
                    continue
                kind = "SHARED_ROOT"
                root_name = next(
                    (c["source_name"] for c in claims if c["source_id"] == roots[a["source_id"]]),
                    "ortak kök",
                )
                reasons = [
                    f"Kaynaklar farklı ({a['source_name']} / {b['source_name']}) ama ikisi de "
                    f"aynı bağımsız köke iniyor: {root_name}",
                    "Türetilmiş kaynaklar bağımsız doğrulama SAYILMAZ — bağlanırsa confidence "
                    "sahte yükselirdi (Q6, Faz 6 lineage indirgemesi)",
                ]
            elif similarity >= DERIVED_SUSPECT_THRESHOLD:
                kind = "DERIVED_SUSPECT"
                reasons = [
                    f"Kaynaklar farklı ({a['source_name']} / {b['source_name']}) ama metin benzerliği çok yüksek ({similarity:.2f})",
                    "Bu bağımsız doğrulama DEĞİL, tespit edilmemiş bir türetme olabilir — önce kaynak lineage'ını işaretle",
                ]
            elif days > MAX_DAYS_APART:
                continue
            else:
                kind = "CORROBORATION"
                reasons = [
                    f"Ortak nadir terimler: {', '.join(terms)}",
                    f"Bağımsız kaynaklar: {a['source_name']} / {b['source_name']}",
                    f"{days:.1f} gün arayla yayınlandı" if days >= 0.05 else "Aynı gün yayınlandı",
                ]
                if similarity > 0:
                    reasons.append(
                        f"Metin benzerliği düşük ({similarity:.2f}) — aynı olay, bağımsız yazım"
                    )

            pair = CandidatePair(
                a=a,
                b=b,
                kind=kind,
                rare_overlap=rare,
                text_similarity=round(similarity, 4),
                days_apart=round(days, 2),
                shared_terms=terms,
                reasons=reasons,
            )
            if kind == "CORROBORATION":
                pair.projected_a = _projected_confidence(a, 1, independent=True)
                pair.projected_b = _projected_confidence(b, 1, independent=True)
            out.append(pair)

    # Sıralama: önce gerçek doğrulama adayları (asıl iş), sonra uyarı kategorileri; her grup
    # kendi içinde sinyal gücüne göre.
    order = {"CORROBORATION": 0, "DERIVED_SUSPECT": 1, "SHARED_ROOT": 2, "SAME_SOURCE_DUPLICATE": 3}
    out.sort(key=lambda p: (order[p.kind], -p.rare_overlap))
    return out[:limit]


# ---- Faz 28: claim ↔ GÖZLEM adayları ------------------------------------
#
# **Neden ayrı bir arama.** Faz 17'nin ekranı claim ↔ claim çalışıyor ve doğrulayacak ikinci
# claim'in ZATEN var olmasını gerektiriyor. Ölçüm (2026-09-08) bunun neden yetmediğini
# gösterdi: 55 claim'in 28'i tek bir kaynaktan (OpenAI resmi duyuru) ve 30 claim'in hiç
# doğrulayanı yok. Faz 24 kaynak tabanını 6'dan 10'a çıkardı ama yeni dört kaynak toplam
# 1 claim üretti — yani sorun "doğrulayacak ikinci kaynak yok" değil, "ikinci kaynak var ama
# onu bulmanın yolu yok"tu. Aranan bağ claim ↔ gözlem: *bu doğrulanmamış iddiayı, sistemde
# duran hangi ham gözlem doğrulayabilir?*
#
# Ölçü YENİDEN İCAT EDİLMİYOR: Faz 17'nin IDF ağırlıklı nadir terim ortaklığı ve zaman
# penceresi aynen kullanılıyor, aynı eşiklerle. Tek fark tarafların biri henüz claim değil.
#
# **Elenmiş gözlemler de havuzda ve bu bilinçli.** Ölçüm: yalnızca bekleyenlerle 30 claim'in
# 7'si aday buluyor, elenmişler dahil edilince 18'i. Eleme kararı gözlemin KENDİ başına
# bilgiye değip değmediğiydi ("değerlendirildi, bilgiye dönüştürülmedi"); doğrulama bambaşka
# bir soru — bir gözlem tek başına önemsiz olup yine de var olan bir iddiayı bağımsız olarak
# rapor ediyor olabilir. Q17 zaten "elenen kaybolmaz, işaretlenir" diyor. Aday listesinde
# hangisinin elenmiş olduğu AÇIKÇA yazılıyor ve promote onu kendiliğinden geri alıyor.

# Havuza giren gözlemin asgari uzunluğu: birkaç kelimelik bir gözlem nadir terim ortaklığında
# tesadüfen yüksek skor alır (payda min() olduğu için).
OBSERVATION_MIN_LENGTH = 60


@dataclass
class ObservationCandidate:
    claim: dict
    observation: dict
    kind: str  # CORROBORATION | SAME_SOURCE | SHARED_ROOT | DERIVED_SUSPECT
    rare_overlap: float
    text_similarity: float
    days_apart: float
    shared_terms: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    suggested_source_id: str | None = None
    suggested_source_name: str | None = None
    projected_confidence: float | None = None


def _claims_without_corroborator(conn) -> set[str]:
    """Hiç CORROBORATES bağı olmayan claim'ler — bu fazın hedef kümesi."""
    linked: set[str] = set()
    for row in fetch_all(
        conn.execute("MATCH (a:Claim)-[:CORROBORATES]->(b:Claim) RETURN a.id AS a, b.id AS b")
    ):
        linked.add(row["a"])
        linked.add(row["b"])
    all_ids = {r["id"] for r in fetch_all(conn.execute("MATCH (c:Claim) RETURN c.id AS id"))}
    return all_ids - linked


def _candidate_observations(conn) -> list[dict]:
    """Havuz: claim üretmemiş gözlemler (bekleyen + elenmiş), önerilen kaynaklarıyla."""
    from app.triage import normalize_host

    source_by_host: dict[str, dict] = {}
    for row in fetch_all(
        conn.execute("MATCH (s:Source) RETURN s.id AS id, s.name AS name, s.url AS url")
    ):
        host = normalize_host(row["url"])
        if host and host not in source_by_host:
            source_by_host[host] = row

    rows = fetch_all(
        conn.execute(
            "MATCH (o:Observation) OPTIONAL MATCH (o)-[:PRODUCED]->(c:Claim) "
            "RETURN o.id AS id, o.raw_content AS raw_content, o.observed_at AS observed_at, "
            "o.source_url AS source_url, o.dismissed AS dismissed, "
            "o.dismiss_reason AS dismiss_reason, c.id AS claim_id"
        )
    )
    out = []
    for row in rows:
        if row["claim_id"]:
            continue
        text = row["raw_content"] or ""
        if len(text) < OBSERVATION_MIN_LENGTH:
            continue
        host = normalize_host(row["source_url"])
        source = source_by_host.get(host) if host else None
        out.append({
            "id": row["id"], "raw_content": text, "observed_at": row["observed_at"],
            "source_url": row["source_url"], "dismissed": bool(row["dismissed"]),
            "dismiss_reason": row["dismiss_reason"], "host": host,
            "source_id": source["id"] if source else None,
            "source_name": source["name"] if source else None,
        })
    return out


def find_observation_candidates(
    conn,
    *,
    claim_id: str | None = None,
    include_corroborated: bool = False,
    include_dismissed: bool = True,
    limit: int = 200,
) -> list[ObservationCandidate]:
    """Doğrulayanı olmayan claim'leri doğrulayabilecek ham gözlemler.

    Faz 17'nin ölçüsü ve eşikleri aynen kullanılıyor; tek fark tarafların biri gözlem."""
    claims = _load_claims(conn)
    if not claims:
        return []
    target_ids = None if include_corroborated else _claims_without_corroborator(conn)
    if claim_id:
        claims = [c for c in claims if c["id"] == claim_id]
    elif target_ids is not None:
        claims = [c for c in claims if c["id"] in target_ids]
    if not claims:
        return []

    pool = _candidate_observations(conn)
    if not include_dismissed:
        pool = [o for o in pool if not o["dismissed"]]
    if not pool:
        return []

    # IDF claim VE gözlem metinlerinin üzerinden: nadirlik bu havuzda ne kadar nadir olduğuna
    # göre ölçülmeli; yalnızca claim'lere bakan bir IDF havuzun kelime dağılımını görmezdi.
    claim_docs = [_tokens(c["text"][:RARE_TEXT_CAP]) for c in claims]
    obs_docs = [_tokens(o["raw_content"][:RARE_TEXT_CAP]) for o in pool]
    n = len(claim_docs) + len(obs_docs) or 1
    df: Counter = Counter()
    for d in claim_docs + obs_docs:
        df.update(d)
    idf = {t: math.log(n / count) for t, count in df.items()}

    roots = {c["source_id"]: resolve_independent_root(conn, c["source_id"]) for c in claims}
    for o in pool:
        if o["source_id"] and o["source_id"] not in roots:
            roots[o["source_id"]] = resolve_independent_root(conn, o["source_id"])

    out: list[ObservationCandidate] = []
    for ci, claim in enumerate(claims):
        claim_shingles = shingles(claim["text"])
        for oi, obs in enumerate(pool):
            rare, terms = _rare_overlap(claim_docs[ci], obs_docs[oi], idf)
            if rare < OBSERVATION_RARE_THRESHOLD:
                continue
            days = _days_apart(claim["valid_from"], obs["observed_at"])
            if days > MAX_DAYS_APART:
                continue
            similarity = containment_similarity(claim_shingles, shingles(obs["raw_content"]))

            same_source = obs["source_id"] is not None and obs["source_id"] == claim["source_id"]
            same_root = (
                obs["source_id"] is not None
                and roots.get(obs["source_id"]) == roots.get(claim["source_id"])
            )
            reasons = [
                "Ortak nadir terimler: " + ", ".join(terms),
                (f"{days:.1f} gün arayla" if days >= 0.05 else "Aynı gün"),
            ]
            if obs["dismissed"]:
                # Q17: elenen kaybolmaz. Ama kullanıcı bunu bilerek elemişti — sessizce geri
                # getirmek değil, açıkça söyleyip kararı ona bırakmak gerekiyor.
                note = "Bu gözlem daha önce elenmişti"
                if obs["dismiss_reason"]:
                    note += " (" + obs["dismiss_reason"] + ")"
                reasons.append(note + " — promote edilirse eleme kendiliğinden kalkar")

            if same_source:
                kind = "SAME_SOURCE"
                reasons.insert(0, "Aynı kaynak (" + str(claim["source_name"]) + ") — bağımsız doğrulama olamaz")
            elif same_root:
                kind = "SHARED_ROOT"
                reasons.insert(0, "Kaynaklar farklı ama ikisi de aynı bağımsız köke iniyor (Q6)")
            elif similarity >= DERIVED_SUSPECT_THRESHOLD:
                kind = "DERIVED_SUSPECT"
                reasons.insert(0, f"Metin benzerliği çok yüksek ({similarity:.2f}) — türetme olabilir")
            else:
                kind = "CORROBORATION"
                reasons.insert(
                    0,
                    "Bağımsız kaynak: " + (obs["source_name"] or obs["host"] or "kaynağı çözülemedi"),
                )

            candidate = ObservationCandidate(
                claim=claim, observation=obs, kind=kind, rare_overlap=rare,
                text_similarity=round(similarity, 4), days_apart=round(days, 2),
                shared_terms=terms, reasons=reasons,
                suggested_source_id=obs["source_id"], suggested_source_name=obs["source_name"],
            )
            if kind == "CORROBORATION":
                candidate.projected_confidence = _projected_confidence(claim, 1, independent=True)
            out.append(candidate)

    order = {"CORROBORATION": 0, "DERIVED_SUSPECT": 1, "SHARED_ROOT": 2, "SAME_SOURCE": 3}
    out.sort(key=lambda c: (order[c.kind], -c.rare_overlap))
    return out[:limit]
