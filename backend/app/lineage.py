"""
Source Independence Lineage Graph — Q6 spike + karar.

Q6 sorusu: source independence teknik olarak nasıl tespit edilir? Değerlendirilen üç
yaklaşım:
    (a) Salt metin benzerliği (near-duplicate detection)
    (b) Yayın metadata'sı (yayın zamanı yakınlığı, yazar/kurum bilgisi)
    (c) Syndication API'leri (ör. haber ajansı API'lerinden resmi dağıtım kaydı)

(c) elendi: bu kişisel/tek-kullanıcılı bir araç, gerçek dünyadaki haber siteleri syndication
API erişimi vermiyor (ticari/kurumsal anlaşma gerektirir) — v1 kapsamı dışında.

**Karar: metin benzerliği (kelime n-gram containment/overlap katsayısı) birincil sinyal,
ajans-atıf metadata'sı destekleyici/opsiyonel ikincil sinyal.** Gerekçe ve doğrulama, gerçek
haber makaleleriyle (collector'ın, app/collector.py, network-policy sınırlı çektiği ham metin
üzerinde) yapıldı:

1. **Jaccard yerine containment (Szymkiewicz–Simpson) katsayısı kullanıldı.** İlk denemede
   simetrik Jaccard (kesişim/birleşim) kullanıldı, ama collector'ın çıkardığı ham sayfa metni
   navigasyon/menü/altbilgi "boilerplate" içeriyor ve bu boilerplate iki farklı sitede
   tamamen farklı — bu da sayfa uzunlukları arasındaki asimetriyle birleşince Jaccard'ı
   yapay olarak düşürüyor (ör. gerçek bir türetilmiş çift ölçülen Jaccard'da sadece ~0.20
   çıktı). Containment (kesişim / min(|A|,|B|)) bu asimetriye karşı sağlam: aynı iki gerçek
   çift 0.54-0.62 aralığında ölçüldü, ilgisiz sayfa çiftleri ise 0.01-0.19 aralığında kaldı
   — net bir ayrım.
2. **Ajans-atıf regex'i (parantez içi "(AA)" vb.) gerçek sayfalarda güvenilir çıkmadı.**
   Anadolu Ajansı'nın kendi sitesi kendine "(AA)" diye atıf yapmıyor ("... muhabirinin
   edindiği bilgiye göre..." kalıbını kullanıyor), üçüncü parti siteler de her zaman
   köşeli/parantezli bir imza bırakmıyor. Bu yüzden ajans sinyali ZORUNLU değil, ekstra bir
   destekleyici sinyal olarak tutuldu (düşük benzerlikte bile lineage'a izin veriyor) ama
   birincil karar mekanizması metin benzerliği.

Doğrulanan gerçek örnekler (Roadmap.md Faz 6 notlarında tam detay):
    - aa.com.tr → ensondakika.com.tr (2 farklı haber, ikisinde de containment ≥ 0.44)
    - turkiyeajanspress.com → egelobisi.com (containment 0.54)
    - karsmanset.com → yildirimgazetesi.com → marmarisyenisayfa.com (3'lü zincir, ikili
      containment'lar 0.56-0.60 — agency → site A → site B deseninin somut karşılığı)
Doğru negatif (ilgisiz/bağımsız yeniden yazım) örnekleri de test edildi — aynı konudaki
(balıkçılık) ama farklı kökenden iki site (egelobisi vs denizhaber) 0.19'da kaldı, eşiğin
(0.35) altında — sistem bunları yanlışlıkla türetilmiş işaretlemiyor.
"""
import re
from dataclasses import dataclass

from app.db import fetch_one

# Kelime n-gram (shingle) boyutu — çok küçük (ör. 2-3) yanlış pozitif üretir (ortak kalıp
# ifadeler), çok büyük (ör. 8+) hafif yeniden yazılmış metni kaçırır. 5 kelime, cümle
# düzeyinde yeniden ifade edilmiş ama gövdesi aynı kalan haber metinleri için iyi bir denge.
SHINGLE_SIZE = 5

# Salt metin benzerliğiyle "türetilmiş" kararı için eşik (containment katsayısı üzerinden).
# Gerçek veri: doğru pozitifler 0.44-0.62, en zor doğru negatif (aynı konu, farklı köken)
# 0.19 — 0.35 ikisi arasında güvenli marj bırakıyor.
TEXT_SIMILARITY_THRESHOLD = 0.35

# Ortak ajans ataması VARSA, daha düşük bir benzerlik eşiği yeterli — atıf başlı başına
# güçlü bir sinyal, metin tamamen yeniden yazılmış olsa bile ortak köken hâlâ geçerli. Ama
# bkz. yukarıdaki karar notu: bu sinyal gerçek sayfalarda seyrek yakalanıyor, sadece
# destekleyici.
AGENCY_ASSISTED_THRESHOLD = 0.12

# Bilinen haber ajansı imzaları/atıfları — Türkçe ve uluslararası. Metinde (parantez içinde
# ya da "Kaynak:" kalıbıyla) geçen bir ajans adı, iki farklı sitedeki metnin ortak kökenine
# işaret eden ek bir sinyaldir. Liste büyütülebilir (v1'de kapalı küme, YAGNI).
#
# NOT (spike bulgusu): kısa kısaltmalar ("aa", "iha", "ap" gibi) bilinçli olarak DIŞARIDA
# bırakıldı — gerçek veriyle test edilirken "(İHA)" kalıbının haberin KONUSU olan "İnsansız
# Hava Aracı" kısaltmasıyla çakıştığı (İhlas Haber Ajansı ile aynı kısaltma) ve yanlış
# pozitife yol açtığı görüldü (bkz. Roadmap.md Faz 6 notları — 3'lü İHA-drone zincirinde).
# Bu yüzden sadece tam/uzun, tek anlamlı isimler tutuluyor.
KNOWN_AGENCIES = (
    "anadolu ajansı", "anadolu agency",
    "reuters", "afp", "associated press",
    "demirören haber ajansı",
    "ihlas haber ajansı",
    "dpa",
)

_AGENCY_PATTERN = re.compile(
    r"(?:\(|kaynak:\s*|kaynağı:\s*)\s*(" + "|".join(re.escape(a) for a in KNOWN_AGENCIES) + r")\s*\)?",
    re.IGNORECASE,
)

_WORD_PATTERN = re.compile(r"[\w']+", re.UNICODE)


def normalize_text(text: str) -> str:
    return " ".join(_WORD_PATTERN.findall(text.lower()))


def shingles(text: str, n: int = SHINGLE_SIZE) -> set[str]:
    words = normalize_text(text).split()
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def containment_similarity(a: set[str], b: set[str]) -> float:
    """Szymkiewicz–Simpson containment: kesişim / min(|A|,|B|). Jaccard'dan (kesişim/
    birleşim) farklı olarak, iki dokümanın boyutu çok farklıysa (ör. farklı miktarda site
    boilerplate'i) haksız yere düşük çıkmıyor — bkz. modül dokstring'indeki spike notu."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    return intersection / min(len(a), len(b))


def detect_agencies(text: str) -> set[str]:
    """Metinde geçen bilinen ajans atıflarını döner (normalize edilmiş isimler)."""
    return {m.group(1).lower() for m in _AGENCY_PATTERN.finditer(text)}


@dataclass
class LineageDetection:
    similarity: float
    shared_agencies: list[str]
    is_derived: bool
    method: str  # TEXT_SIMILARITY | AGENCY_ATTRIBUTION | HYBRID | NONE


def detect_derivation(text_a: str, text_b: str) -> LineageDetection:
    similarity = containment_similarity(shingles(text_a), shingles(text_b))
    shared_agencies = sorted(detect_agencies(text_a) & detect_agencies(text_b))

    if similarity >= TEXT_SIMILARITY_THRESHOLD and shared_agencies:
        method = "HYBRID"
        is_derived = True
    elif similarity >= TEXT_SIMILARITY_THRESHOLD:
        method = "TEXT_SIMILARITY"
        is_derived = True
    elif shared_agencies and similarity >= AGENCY_ASSISTED_THRESHOLD:
        method = "AGENCY_ATTRIBUTION"
        is_derived = True
    else:
        method = "NONE"
        is_derived = False

    return LineageDetection(
        similarity=round(similarity, 4),
        shared_agencies=shared_agencies,
        is_derived=is_derived,
        method=method,
    )


def resolve_independent_root(conn, source_id: str, *, max_hops: int = 10) -> str:
    """DERIVED_FROM zincirinde en yukarı (kök/en bağımsız) Source id'sini bulur. Döngüye
    karşı max_hops sınırı var (v1'de döngü oluşturulmaması bekleniyor ama savunma amaçlı)."""
    current = source_id
    for _ in range(max_hops):
        row = fetch_one(
            conn.execute(
                "MATCH (s:Source {id: $id})-[:DERIVED_FROM]->(parent:Source) RETURN parent.id AS id LIMIT 1",
                {"id": current},
            )
        )
        if row is None:
            return current
        current = row["id"]
    return current
