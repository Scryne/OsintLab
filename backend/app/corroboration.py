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
            "RETURN c.id AS id, c.text AS text, c.valid_from AS valid_from, "
            "c.confidence AS confidence, c.knowledge_state AS knowledge_state, "
            "s.id AS source_id, s.name AS source_name, s.reliability AS reliability"
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
    docs = [_tokens(c["text"]) for c in claims]
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
