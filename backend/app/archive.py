"""
Faz 26 — Kanıt Katmanı: bir claim'in dayandığı içeriğin arşiv kopyası.

**Asıl mesele skor değil, PROVENANCE.** Faz 26'ya kadar bir claim'in dayanağı yalnızca
`Observation.source_url`di. O sayfa değişir ya da silinirse elimizde hiçbir şey kalmıyordu:
bağlantı ölüyor, "bu iddia neye dayanıyordu" sorusu cevapsız kalıyordu. "History Is
Immutable" ve "Auditability" ilkeleri tam bu noktada karşılıksızdı.

**Arşiv YENİDEN ÇEKİLMİYOR, gözlemden alınıyor.** İlk tasarım sayfayı promote anında tekrar
indirmekti; yanlış olurdu. Arşivin doğru içeriği *gözlediğimiz* metindir, bugünkü sayfa
değil — bugün indirilen şey arşiv değil, yeni bir gözlemdir. Gözlemin ham metni zaten hem
graf'ta hem append-only günlükte duruyor; eksik olan şey onun hash'i, ayrı bir Evidence
kaydı ve canlı sayfaya karşı doğrulanabilmesiydi. Bu yüzden arşivleme AĞSIZ çalışır:
her claim için, allowlist/erişim durumundan bağımsız olarak.

**Arşiv tek başına confidence YÜKSELTMEZ — bu fazın merkezi kararı.** Roadmap'in uyarısı:
"her claim kendi kaynağının arşiviyle otomatik kanıtlı sayılırsa, kanıt alt-skoru kaynak
kalitesinin bir kopyası olur ve ayrı bir bileşen olmaktan çıkar." Doğru: arşiv, iddianın
DOĞRU olduğunun kanıtı değil, kaynağın onu SÖYLEDİĞİNİN kaydıdır — ve "kaynağın sözüne ne
kadar güveniyoruz" sorusunun cevabı formülde zaten `source_quality` olarak duruyor.

Bu yüzden iki kenar var:
    ARCHIVES  — her arşiv kurar. Provenance. Skora girmez.
    SUPPORTS  — yalnızca arşiv CANLI sayfaya karşı DOĞRULANDIĞINDA kurulur. Skora girer.

Doğrulama neden gerçek bir sinyal: farklı bir ZAMANDA dünyaya ikinci kez bakmaktır. Sayfa
hâlâ aynı başlığı taşıyorsa kaynak arkasında duruyor demektir; geri çekilmiş/değiştirilmiş
bir haber `DEGISMIS`, silinmiş bir sayfa `ERISILEMEDI` döner ve SUPPORTS kurulmaz. Aynı
kaynaktan gelen iki claim bu eksende farklı sonuç alabilir — yani sabit bir kaydırma değil,
ayırt eden bir ölçüdür. Ne KADAR ayırt ettiği tahmin edilmedi, ölçüldü; sonuç ve ilk
denemenin neden yanlış olduğu `docs/Roadmap.md` Faz 26 bölümünde ve aşağıda
`VERIFY_MIN_HEADLINE_LENGTH`in başındaki notta.
"""
import hashlib
import html
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app import docint
from app.collector import (
    CollectorFetchError,
    CollectorSecurityError,
    extract_content_from_html,
    load_allowlist,
    safe_fetch,
)
from app.db import DATA_ROOT, fetch_all, fetch_one

ARCHIVE_TYPE = "arşiv"
ARCHIVE_TEXT_SOURCE = "archive"

# Durumlar. `ARSIVLENDI` bir "henüz bakılmadı" durumudur, bir başarısızlık değil — arşivin
# kendisi ağ gerektirmeden oluşur, doğrulama ayrı bir adımdır.
ARSIVLENDI = "ARSIVLENDI"
DOGRULANDI = "DOGRULANDI"
DEGISMIS = "DEGISMIS"
ERISILEMEDI = "ERISILEMEDI"

STATUS_LABELS = {
    ARSIVLENDI: "Arşivlendi — canlı sayfaya karşı henüz bakılmadı",
    DOGRULANDI: "Doğrulandı — kaynak ayakta ve aynı başlığı taşıyor",
    DEGISMIS: "Değişmiş — canlı sayfa arşivdeki başlığı artık taşımıyor",
    ERISILEMEDI: "Erişilemedi — kaynak sayfa artık alınamıyor",
}

# Doğrulamanın ölçtüğü şey: **başlık canlı sayfada hâlâ duruyor mu.**
#
# İlk tasarım gövde içerilmesini (Faz 25'in `_containment` ölçüsü, eşik 0.8) kapı olarak
# kullanıyordu. Gerçek veride ölçüldü (2026-09-09, 27 arşiv) ve YANLIŞ olduğu görüldü:
# doğrulanan 0, dağılım 0.5 (21 kayıt), 0.0 (5), 0.25 (1). Sebep tek cümlede — claim'lerin
# neredeyse tamamı `mode=rss` ile toplandı, yani arşivdeki metin "başlık + RSS özeti"dir;
# canlı sayfadaki metin ise makalenin GÖVDESİ. RSS özeti makalenin içinde birebir geçmez
# (çoğu yayın için ayrı yazılmış bir dek'tir). 0.5'ler tam olarak şunu söylüyordu: iki
# satırdan biri — başlık — bulundu, özet bulunamadı. Yani ölçü, sormak istediğimiz soruyu
# değil, iki farklı türden metnin birbirine benzeyip benzemediğini ölçüyordu.
#
# Sormak istediğimiz soru şu: kaynak hâlâ ayakta mı ve bu içeriği taşımaya devam ediyor mu?
# Bunun ayırt edici ve tür-bağımsız sınavı başlıktır: geri çekilmiş, silinmiş, yerine başka
# bir yazı konmuş bir sayfa başlığı taşımaz. Gövde içerilmesi ölçülmeye devam ediyor ama
# KAPI DEĞİL, bildirilen bir sayı — "ne kadarı duruyor" bilgisi kararı insana bırakır.
VERIFY_MIN_HEADLINE_LENGTH = 20

# Karşılaştırmaya giren satırın asgari uzunluğu: kısa satırlar ("Paylaş", tarih) her sayfada
# var ve hem yanlış eşleşme hem yanlış ayrışma üretirler.
VERIFY_MIN_LINE = 25

# Kanıt dosyalarıyla aynı kök: `OSINTLAB_DATA_DIR` ile taşınabilir olmalı, yoksa izole
# bir test backend'i grafı ayrı ama arşivi gerçek veri klasörüne yazardı (Faz 15.1'de
# EVIDENCE_DIR için öğrenilen ders).
ARCHIVE_DIR = DATA_ROOT / "archive"


def archive_dir() -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    return ARCHIVE_DIR


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Karşılaştırma öncesi normalleştirme. Gerekçesi ölçümden çıktı: theverge kaydının arşiv
# başlığı `OpenAI&#8217;s Astra`, canlı sayfada ise `OpenAI’s Astra` — ikisi AYNI cümle,
# fark bizim kendi toplama katmanımızdan geliyor (Faz 11/F13 HTML entity ayıklamasından
# önce toplanmış bir kayıt). Normalleştirme olmadan bu, "sayfa değişmiş" diye raporlanırdı:
# kendi geçmiş hatamızı kaynağın suçu gibi göstermek.
#
# Kapsam dar tutuldu — entity çözümü ve tipografik karakterlerin ASCII karşılıkları. Daha
# gevşek bir eşleştirme (küçük harfe indirme, noktalama atma) gerçek bir başlık
# değişikliğini de yutardı.
# Tire ailesi de ölçümde çıktı: openai.com başlığı bölünmez tire (U+2011) kullanıyor,
# aynı yazının RSS başlığı düz tire — aynı ad, farklı karakter. Yumuşak tire (U+00AD)
# görünmez bir bölme işaretidir, karşılığı boş dizedir.
_TYPOGRAPHIC = {
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "‐": "-", "‑": "-", "­": "",
    " ": " ",
}


def normalize_for_compare(text: str) -> str:
    text = html.unescape(text)
    for src, dst in _TYPOGRAPHIC.items():
        text = text.replace(src, dst)
    return " ".join(text.split())


def containment(needle_text: str, haystack_text: str) -> float:
    """`needle_text`in satırlarının ne kadarı `haystack_text` içinde geçiyor (0..1)."""
    lines = [
        line for line in (raw.strip() for raw in needle_text.splitlines())
        if len(line) >= VERIFY_MIN_LINE
    ]
    if not lines:
        return 0.0
    blob = normalize_for_compare(haystack_text)
    hit = sum(1 for line in lines if normalize_for_compare(line) in blob)
    return hit / len(lines)


def existing_archive(conn, claim_id: str) -> dict | None:
    return fetch_one(
        conn.execute(
            "MATCH (ev:Evidence)-[:ARCHIVES]->(c:Claim {id: $cid}) "
            "RETURN ev.id AS id, ev.content_hash AS content_hash, ev.file_path AS file_path, "
            "ev.archive_url AS archive_url, ev.archive_status AS archive_status, "
            "ev.archive_checked_at AS archive_checked_at, ev.archive_match AS archive_match, "
            "ev.archive_note AS archive_note, ev.extracted_text AS extracted_text",
            {"cid": claim_id},
        )
    )


def _source_observation(conn, claim_id: str) -> dict | None:
    return fetch_one(
        conn.execute(
            "MATCH (o:Observation)-[:PRODUCED]->(c:Claim {id: $cid}) "
            "RETURN o.id AS id, o.raw_content AS raw_content, o.source_url AS source_url, "
            "o.observed_at AS observed_at",
            {"cid": claim_id},
        )
    )


def create_archive(conn, claim_id: str) -> dict:
    """Claim'in dayandığı gözlemden arşiv Evidence'ı üretir. Ağ kullanmaz, idempotenttir.

    Dönen sözlükteki `action`: "olusturuldu" | "zaten_var" | "atlandi"."""
    already = existing_archive(conn, claim_id)
    if already:
        return {"claim_id": claim_id, "action": "zaten_var", "evidence_id": already["id"],
                "archive_status": already["archive_status"], "reason": None}

    observation = _source_observation(conn, claim_id)
    if observation is None:
        return {"claim_id": claim_id, "action": "atlandi", "evidence_id": None,
                "archive_status": None,
                "reason": "Bu claim bir gözlemden üretilmemiş (PRODUCED bağı yok) — "
                          "arşivlenecek ham içerik yok."}
    text = observation["raw_content"] or ""
    if not text.strip():
        return {"claim_id": claim_id, "action": "atlandi", "evidence_id": None,
                "archive_status": None, "reason": "Gözlemin ham metni boş."}

    digest = content_hash(text)
    # Dosya adı içerik hash'i: aynı metin iki claim'e dayanak olduğunda tek dosya yazılır ve
    # dosya adının kendisi bir bütünlük kontrolüdür. Evidence düğümü yine claim başına ayrı —
    # arşivin DURUMU (doğrulandı/değişmiş) claim'e değil, o claim'in dayanağına aittir.
    path = archive_dir() / f"{digest}.txt"
    if not path.exists():
        path.write_text(text, encoding="utf-8")

    evidence_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    # Q22: arşiv metni de toplanan içeriktir; enjeksiyon taraması gözlemde yapıldığı gibi
    # burada da yapılır ki uyarı Evidence kaydıyla birlikte seyahat etsin.
    hits = docint.find_instruction_like(text, where="arşiv metni")
    conn.execute(
        "CREATE (:Evidence {id: $id, evidence_type: $type, file_path: $path, "
        "content_hash: $hash, collected_at: $collected_at, created_at: $now, "
        "extracted_text: $text, text_source: $text_source, injection_hits: $hits, "
        "archive_url: $url, archive_status: $status})",
        {
            "id": evidence_id, "type": ARCHIVE_TYPE, "path": str(path), "hash": digest,
            "collected_at": observation["observed_at"] or now, "now": now, "text": text,
            "text_source": ARCHIVE_TEXT_SOURCE, "hits": docint.hits_to_json(hits),
            "url": observation["source_url"], "status": ARSIVLENDI,
        },
    )
    conn.execute(
        "MATCH (ev:Evidence {id: $eid}), (c:Claim {id: $cid}) "
        "CREATE (ev)-[:ARCHIVES {created_at: $now}]->(c)",
        {"eid": evidence_id, "cid": claim_id, "now": now},
    )
    return {"claim_id": claim_id, "action": "olusturuldu", "evidence_id": evidence_id,
            "archive_status": ARSIVLENDI, "reason": None}


def archive_headline(archived_text: str) -> str:
    """Arşivin başlık satırı — doğrulamanın karşılaştırdığı şey.

    Faz 25'ten sonra `mode=web` metni zaten "başlık

gövde"; `mode=rss` metni ise
    "başlık

özet". İkisinde de ilk anlamlı satır başlıktır. Çok kısa bir ilk satır
    ("Haberler", bir tarih) başlık sayılmaz: her sayfada bulunur ve doğrulamayı bedavaya
    geçirirdi."""
    for line in (raw.strip() for raw in archived_text.splitlines()):
        if len(line) >= VERIFY_MIN_HEADLINE_LENGTH:
            return line
    return ""


def _contains_line(line: str, haystack: str) -> bool:
    return normalize_for_compare(line) in normalize_for_compare(haystack)


def _set_archive_result(conn, evidence_id: str, status: str, match: float | None, note: str | None) -> None:
    conn.execute(
        "MATCH (ev:Evidence {id: $eid}) SET ev.archive_status = $status, "
        "ev.archive_checked_at = $now, ev.archive_match = $match, ev.archive_note = $note",
        {"eid": evidence_id, "status": status, "now": datetime.now(timezone.utc),
         "match": match, "note": note},
    )


def _has_supports(conn, evidence_id: str, claim_id: str) -> bool:
    return fetch_one(
        conn.execute(
            "MATCH (ev:Evidence {id: $eid})-[:SUPPORTS]->(c:Claim {id: $cid}) RETURN ev.id AS id",
            {"eid": evidence_id, "cid": claim_id},
        )
    ) is not None


def verify_archive(conn, evidence_id: str, claim_id: str) -> dict:
    """Arşivi CANLI sayfaya karşı doğrular. Ağ gerektirir; skor kenarını burada kurar/kaldırır.

    Doğrulanırsa `SUPPORTS` kurulur (kanıt alt-skoru açılır), doğrulanmazsa VAR OLAN SUPPORTS
    KALDIRILIR — bir zamanlar doğrulanmış ama sonradan değişmiş bir sayfa, skoru taşımaya
    devam edemez. Kaldırma sessiz değil: durum ve gerekçe kayda geçer."""
    row = fetch_one(
        conn.execute(
            "MATCH (ev:Evidence {id: $eid}) RETURN ev.archive_url AS url, "
            "ev.extracted_text AS text",
            {"eid": evidence_id},
        )
    )
    if row is None:
        return {"evidence_id": evidence_id, "claim_id": claim_id, "status": None,
                "match": None, "note": "Arşiv kaydı bulunamadı.", "scored": False}

    archived = row["text"] or ""
    url = row["url"]
    if not url:
        note = "Arşivin kaynak adresi yok — canlı sayfa ile karşılaştırılamaz."
        _set_archive_result(conn, evidence_id, ERISILEMEDI, None, note)
        return {"evidence_id": evidence_id, "claim_id": claim_id, "status": ERISILEMEDI,
                "match": None, "note": note, "scored": False}

    try:
        _, content, _ = safe_fetch(url, load_allowlist())
    except (CollectorSecurityError, CollectorFetchError) as exc:
        note = str(exc)
        _set_archive_result(conn, evidence_id, ERISILEMEDI, None, note)
        _drop_supports(conn, evidence_id, claim_id)
        return {"evidence_id": evidence_id, "claim_id": claim_id, "status": ERISILEMEDI,
                "match": None, "note": note, "scored": False}

    live = extract_content_from_html(content)
    match = round(containment(archived, live), 3)
    headline = archive_headline(archived)

    if not headline:
        note = ("Arşivde karşılaştırılacak bir başlık satırı yok — bu kayıt otomatik "
                "doğrulanamaz.")
        _set_archive_result(conn, evidence_id, DEGISMIS, match, note)
        _drop_supports(conn, evidence_id, claim_id)
        return {"evidence_id": evidence_id, "claim_id": claim_id, "status": DEGISMIS,
                "match": match, "note": note, "scored": False}

    if _contains_line(headline, live):
        note = (
            f"Kaynak hâlâ ayakta ve aynı başlığı taşıyor; arşiv gövdesinin "
            f"%{match * 100:.0f}'i canlı sayfada bulundu."
        )
        _set_archive_result(conn, evidence_id, DOGRULANDI, match, note)
        if not _has_supports(conn, evidence_id, claim_id):
            conn.execute(
                "MATCH (ev:Evidence {id: $eid}), (c:Claim {id: $cid}) CREATE (ev)-[:SUPPORTS]->(c)",
                {"eid": evidence_id, "cid": claim_id},
            )
        return {"evidence_id": evidence_id, "claim_id": claim_id, "status": DOGRULANDI,
                "match": match, "note": note, "scored": True}

    note = (
        "Canlı sayfa arşivdeki başlığı artık taşımıyor — yazı geri çekilmiş, düzenlenmiş ya "
        "da adres başka bir içeriğe gitmiş olabilir. Arşiv artık bu içeriğin TEK kaydı."
    )
    _set_archive_result(conn, evidence_id, DEGISMIS, match, note)
    _drop_supports(conn, evidence_id, claim_id)
    return {"evidence_id": evidence_id, "claim_id": claim_id, "status": DEGISMIS,
            "match": match, "note": note, "scored": False}


def _drop_supports(conn, evidence_id: str, claim_id: str) -> None:
    conn.execute(
        "MATCH (ev:Evidence {id: $eid})-[r:SUPPORTS]->(c:Claim {id: $cid}) DELETE r",
        {"eid": evidence_id, "cid": claim_id},
    )


def archive_rows(conn, claim_ids: list[str] | None = None) -> list[dict]:
    """Arşiv kayıtları + bağlı oldukları claim. Ölçüm ve liste uçlarının ortak sorgusu."""
    where = "WHERE c.id IN $ids " if claim_ids else ""
    params = {"ids": claim_ids} if claim_ids else {}
    return fetch_all(
        conn.execute(
            f"MATCH (ev:Evidence)-[:ARCHIVES]->(c:Claim) {where}"
            "RETURN ev.id AS evidence_id, c.id AS claim_id, ev.archive_url AS archive_url, "
            "ev.archive_status AS archive_status, ev.archive_match AS archive_match, "
            "ev.archive_checked_at AS archive_checked_at, ev.archive_note AS archive_note, "
            "ev.content_hash AS content_hash, ev.collected_at AS collected_at, "
            # Claim'in kendisi de dönüyor: arşiv listesi "hangi iddianın dayanağı" sorusunu
            # cevaplamıyorsa 55 satırlık anonim bir hash listesidir. N+1 sorgu yapmamak için
            # aynı sorguda (Faz 12/F58'de öğrenilen ders).
            "c.text AS claim_text, c.knowledge_state AS claim_state, "
            "c.confidence AS claim_confidence",
            params,
        )
    )


def claims_without_archive(conn) -> list[str]:
    rows = fetch_all(
        conn.execute(
            "MATCH (c:Claim) WHERE NOT EXISTS { MATCH (:Evidence)-[:ARCHIVES]->(c) } "
            "RETURN c.id AS id"
        )
    )
    return [r["id"] for r in rows]
