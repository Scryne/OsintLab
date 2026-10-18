import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

from app import archive, doc_worker, docint
from app.db import DATA_ROOT, fetch_all, fetch_one, get_connection
from app.models import (
    _to_utc,
    Evidence,
    EvidenceClaimLink,
    EvidenceCreate,
    EvidenceExtraction,
    EvidenceFingerprint,
    EvidenceObservationCreate,
    EvidenceVaultItem,
    FingerprintLink,
    FingerprintLinkCreate,
)
from app.models import Observation
from app.monitoring import claim_headline
from app.routers.claims import _claim_about, _node_exists, _notify_change, _recompute_and_store, get_claim
from app.vault import safe_render_vault

router = APIRouter(prefix="/evidence", tags=["evidence"])

_STANCE_TO_REL = {"SUPPORTS": "SUPPORTS", "CONTRADICTS": "CONTRADICTS"}

# Faz 15.1: çıkarma alanları listeye eklendi, ama `extracted_text` BİLEREK dışarıda —
# spike'ta tek bir belge 1,65 milyon karakter verdi; her liste yanıtına koymak Evidence
# Vault sayfasını kullanılamaz hale getirirdi. Tam metin ayrı bir uçtan alınıyor.
_FIELDS = (
    "ev.id AS id, ev.evidence_type AS evidence_type, ev.file_path AS file_path, "
    "ev.content_hash AS content_hash, ev.collected_at AS collected_at, ev.created_at AS created_at, "
    "ev.extraction_status AS extraction_status, ev.page_count AS page_count, "
    "ev.pages_done AS pages_done, ev.extraction_error AS extraction_error, "
    "ev.extracted_at AS extracted_at, ev.text_source AS text_source, "
    "ev.ocr_confidence AS ocr_confidence, ev.ocr_lang AS ocr_lang"
)

# Metin önizlemesi: "gerçekten metin çıktı mı" sorusunu tam metni indirmeden cevaplar.
PREVIEW_CHARS = 1500


def _with_status_label(row: dict) -> dict:
    """Ham durum koduna insan tarafını ekler (`extraction_status_label`)."""
    return {**row, "extraction_status_label": docint.STATUS_LABELS.get(row.get("extraction_status"))}

# Faz 13 — Evidence Vault. Yüklenen dosyalar burada; graf'ta yalnızca göreli yol saklanıyor
# (mutlak yol saklamak, proje klasörü taşındığında tüm kanıt bağlarını sessizce kırardı).
# Faz 15.1: veri kökü artık `db.DATA_ROOT` üzerinden (OSINTLAB_DATA_DIR ile taşınabilir) —
# izole bir test backend'i çalıştırılırken graf ve kanıt dosyaları BİRLİKTE taşınmalı,
# yoksa test grafı ayrı ama yüklenen dosyalar gerçek vault'a düşerdi.
EVIDENCE_DIR = DATA_ROOT / "evidence"

# Tek kullanıcılı yerel bir araç; sınır kötü niyete karşı değil, kazara 4 GB'lık bir dosyayı
# belleğe okumaya karşı.
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Belgeden tek seferde üretilebilecek gözlemin sayfa tavanı (bkz. create_observation_from_evidence).
MAX_OBSERVATION_PAGES = 50
MAX_OCR_OBSERVATION_PAGES = 20
# Yol güvenliği ASCII gerektirmiyor: tehlikeli olan ayraçlar ve '..', harfler değil. Sadece
# ASCII'ye indirgemek Türkçe dosya adlarını bozuyordu ("İhale Sonucu.pdf" -> "hale_Sonucu").
# `\w` UNICODE modunda Türkçe harfleri de kapsıyor.
_UNSAFE_NAME_CHARS = re.compile(r"[^\w.\-]+", re.UNICODE)


def _safe_original_name(name: str | None) -> str:
    """Yüklenen dosya adını depolamada kullanılabilir hale getirir.

    Ad yalnızca insan için: asıl kimlik içerik hash'i. Yine de yol ayracı, '..' ve sürücü
    harfi içeren bir adı olduğu gibi kullanmak klasik bir path traversal olurdu — bu yüzden
    yalnızca son bileşen alınıp beyaz listeye indirgeniyor."""
    base = Path(name or "").name  # dizin bileşenlerini at
    # Kodlaması bozuk bir istemci (multipart dosya adı kodlaması standart dışı bir alan)
    # eşleşmemiş surrogate gönderebilir; bunlar dosya sistemi yollarında hataya ya da
    # anlamsız isimlere yol açar. Önce kodlanabilir hale getiriliyor, sonra süzülüyor.
    base = base.encode("utf-8", "replace").decode("utf-8", "replace")
    base = _UNSAFE_NAME_CHARS.sub("_", base).strip("._") or "dosya"
    return base[:80]


def _stored_path(content_hash: str, original_name: str) -> Path:
    """İçerik-adresli depolama: `data/evidence/<hash[:2]>/<hash[:16]>-<ad>`.

    Hash önekli klasör tek dizinde binlerce dosya birikmesini engelliyor. Dosya adının
    hash'le başlaması, aynı içeriğin iki kez yüklenmesini dosya sisteminde de görünür
    kılıyor — Evidence şemasına ayrı bir `original_name` kolonu eklemek yerine ad yolun
    içinde taşınıyor (KùzuDB'de var olan bir tabloya kolon eklemek `CREATE TABLE IF NOT
    EXISTS` ile OLMAZ, ayrı bir migration gerektirir — bu fazın kapsamı değil)."""
    return EVIDENCE_DIR / content_hash[:2] / f"{content_hash[:16]}-{original_name}"


def _is_anchored(file_path: str) -> bool:
    """Mutlak, sürücü harfli ya da UNC (`\\\\sunucu\\paylaşım`) bir yol mu.

    Bunlar vault'a göre göreli olamaz ve `.resolve()`a bile verilmemeli: Windows bir UNC
    yolunu çözerken uzak makineye SMB ile bağlanır ve kullanıcının NTLM özetini gönderir.
    `POST /evidence`in `file_path` alanı elle doldurulabildiği için bu, dışarıdan tetiklenebilir
    bir sızıntıydı (2026-10-18 denetimi)."""
    if file_path.startswith(("\\\\", "//")):
        return True
    return Path(file_path).is_absolute() or bool(PureWindowsPath(file_path).anchor)


def _resolve_stored_file(file_path: str | None) -> Path | None:
    """Graf'taki göreli yolu gerçek dosyaya çevirir — vault dışına çıkan yolu reddederek.

    `file_path` kullanıcı girdisi olabilir (`POST /evidence` alanı elle doldurulabiliyor),
    dolayısıyla '../../etc/passwd' gibi bir değer indirme ucundan okunabilir olurdu."""
    if not file_path or _is_anchored(file_path):
        return None
    candidate = (EVIDENCE_DIR / file_path).resolve()
    try:
        candidate.relative_to(EVIDENCE_DIR.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _hash_file_if_present(file_path: str | None) -> str | None:
    """Q18: dosya vault'ta varsa bütünlük hash'i hesaplanır; yoksa None döner (caller
    kendi hash'ini vermiş olabilir, ya da dosya henüz collector tarafından indirilmemiştir).

    Yalnızca vault İÇİNDEKİ dosyalar: eskiden verilen her yol (mutlak, `..`, UNC) okunup
    hash'i döndürülüyordu — yani API diskteki herhangi bir dosyanın varlığını ve içeriğinin
    özetini söyleyen bir kahine dönüşüyordu. Göreli yollar da artık çalışma dizinine değil
    vault'a göre çözülüyor (önceden doğru bir vault yolu hiç hash'lenmiyordu). Dosya parça
    parça okunuyor: büyük bir dosya belleğe tek seferde yüklenmesin."""
    path = _resolve_stored_file(file_path)
    if path is None or path.stat().st_size > MAX_UPLOAD_BYTES:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@router.post("", response_model=Evidence, status_code=201)
def create_evidence(payload: EvidenceCreate) -> Evidence:
    conn = get_connection()
    evidence_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    content_hash = payload.content_hash or _hash_file_if_present(payload.file_path)
    conn.execute(
        "CREATE (:Evidence {id: $id, evidence_type: $evidence_type, file_path: $file_path, "
        "content_hash: $content_hash, collected_at: $collected_at, created_at: $created_at})",
        {
            "id": evidence_id,
            "evidence_type": payload.evidence_type,
            "file_path": payload.file_path,
            "content_hash": content_hash,
            "collected_at": payload.collected_at,
            "created_at": created_at,
        },
    )
    return Evidence(
        id=evidence_id,
        created_at=created_at,
        **{**payload.model_dump(), "content_hash": content_hash},
    )


@router.post("/upload", response_model=Evidence, status_code=201)
def upload_evidence(
    file: UploadFile = File(...),  # noqa: B008 — FastAPI'nin form/dosya bildirimi böyle
    evidence_type: str = Form(...),  # noqa: B008
    collected_at: datetime | None = Form(None),  # noqa: B008
) -> Evidence:
    """Faz 13 — Evidence Vault: bir dosyayı doğrudan arayüzden yükler.

    Bu fazdan önce Evidence yalnızca `file_path` metniyle oluşturulabiliyordu; yani kanıt
    dosyasının kendisi sisteme hiç girmiyordu, sadece kullanıcının makinesindeki bir yola
    işaret ediliyordu — dosya taşınınca ya da silinince kanıt sessizce buharlaşıyordu.

    Depolama içerik-adresli (SHA-256): aynı bayt dizisi iki kez yüklenirse ikinci çağrı 409
    döner ve mevcut Evidence'ın id'sini söyler. Sessizce ikinci bir kayıt yaratmak, aynı
    kanıtın grafta iki ayrı düğüm olarak durması demekti — confidence formülündeki evidence
    sayacını da şişirirdi (Q18/bütünlük).

    Senkron (`def`) bilerek: `async` iken veritabanı yazması ve dosya diske yazımı olay
    döngüsünün kendi iş parçacığında yapılıyordu — büyük bir dosya yazılırken zamanlayıcı ve
    diğer bütün istekler bekliyordu. FastAPI senkron ucu iş parçacığı havuzunda çalıştırır;
    `UploadFile.file` zaten diskte yedeklenmiş bir dosya nesnesi."""
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    collected_at = _to_utc(collected_at)  # JSON uçlarındaki UTC garantisi form alanında da
    evidence_type = evidence_type.strip()
    if not evidence_type:
        raise HTTPException(status_code=422, detail="Kanıt türü boş olamaz.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya çok büyük (sınır {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )
    if not raw:
        raise HTTPException(status_code=422, detail="Dosya boş.")

    content_hash = hashlib.sha256(raw).hexdigest()
    conn = get_connection()
    existing = fetch_one(
        conn.execute(
            "MATCH (ev:Evidence {content_hash: $h}) RETURN ev.id AS id, ev.evidence_type AS evidence_type",
            {"h": content_hash},
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Bu dosya zaten kayıtlı: Evidence {existing['id'][:8]}… "
                f"({existing['evidence_type']}). Yeniden yüklemek yerine mevcut kanıtı "
                "ilgili claim'e bağlayabilirsin."
            ),
        )

    original_name = _safe_original_name(file.filename)
    target = _stored_path(content_hash, original_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    relative = target.relative_to(EVIDENCE_DIR).as_posix()

    evidence_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    conn.execute(
        "CREATE (:Evidence {id: $id, evidence_type: $evidence_type, file_path: $file_path, "
        "content_hash: $content_hash, collected_at: $collected_at, created_at: $created_at})",
        {
            "id": evidence_id,
            "evidence_type": evidence_type,
            "file_path": relative,
            "content_hash": content_hash,
            "collected_at": collected_at or created_at,
            "created_at": created_at,
        },
    )
    # Faz 15.1 (DOCINT): belge işleme SENKRON DEĞİL. Faz 15 spike'ı 492 sayfalık bir
    # belgenin baştan sona 29,9 saniye sürdüğünü ölçtü — burada beklemek, tek bir yükleme
    # için API'nin tamamını yarım dakika kilitlemek olurdu. Durum önce DB'ye yazılıyor
    # (kayıt bir an bile durumsuz kalmasın), sonra kuyruğa konuyor.
    doc_worker.mark_pending(evidence_id)
    doc_worker.enqueue(evidence_id)

    return Evidence(
        id=evidence_id,
        evidence_type=evidence_type,
        file_path=relative,
        content_hash=content_hash,
        collected_at=collected_at or created_at,
        created_at=created_at,
        extraction_status=docint.PENDING,
        extraction_status_label=docint.STATUS_LABELS[docint.PENDING],
        pages_done=0,
    )


@router.get("/{evidence_id}/extraction", response_model=EvidenceExtraction)
def get_evidence_extraction(evidence_id: str) -> EvidenceExtraction:
    """Faz 15.1 — belgeden ne çıkarıldığı: durum, metadata, sayfa sayısı, metin önizlemesi.

    **Q22 uyarısı:** `metadata` ve `text_preview` alanları GÜVENİLMEYEN VERİDİR. Belge metni
    ve belge metadata'sı açık kaynaktan gelir; Faz 15 spike'ı her ikisinin de talimat-görünümlü
    ifade taşıyabildiğini doğruladı (metin katmanında `SYSTEM: Ignore all previous
    instructions...`, metadata'da `/Subject: Disregard prior instructions...`). Bu alanları
    sunan hiçbir katman içeriklerini komut olarak yorumlamamalı."""
    conn = get_connection()
    row = fetch_one(
        conn.execute(
            "MATCH (ev:Evidence {id: $id}) RETURN ev.extraction_status AS status, "
            "ev.doc_metadata AS doc_metadata, ev.page_count AS page_count, "
            "ev.pages_done AS pages_done, ev.extraction_error AS error, "
            "ev.extracted_at AS extracted_at, ev.extracted_text AS text, "
            "ev.injection_hits AS injection_hits, ev.text_source AS text_source, "
            "ev.ocr_confidence AS ocr_confidence, ev.ocr_lang AS ocr_lang",
            {"id": evidence_id},
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    text = row["text"] or ""
    return EvidenceExtraction(
        evidence_id=evidence_id,
        status=row["status"],
        status_label=docint.STATUS_LABELS.get(row["status"]),
        page_count=row["page_count"],
        pages_done=row["pages_done"],
        error=row["error"],
        extracted_at=row["extracted_at"],
        metadata=docint.metadata_from_json(row["doc_metadata"]),
        text_chars=len(text),
        text_preview=text[:PREVIEW_CHARS],
        injection_hits=docint.hits_from_json(row["injection_hits"]),
        text_source=row["text_source"],
        ocr_confidence=row["ocr_confidence"],
        ocr_lang=row["ocr_lang"],
    )


@router.get("/{evidence_id}/text", response_class=PlainTextResponse)
def get_evidence_text(evidence_id: str) -> PlainTextResponse:
    """Belgeden çıkarılan tam metin (düz metin olarak).

    Ayrı bir uç, çünkü tek bir belge milyonlarca karakter olabiliyor — liste yanıtlarına
    konamaz. `text/plain` ve `nosniff` ile dönüyor: içerik güvenilmeyen kaynaktan geldiği
    için tarayıcının onu HTML sanıp çalıştırması istenmiyor (indirme ucundaki disiplinin aynısı)."""
    conn = get_connection()
    row = fetch_one(
        conn.execute(
            "MATCH (ev:Evidence {id: $id}) RETURN ev.extracted_text AS text, "
            "ev.extraction_status AS status",
            {"id": evidence_id},
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if not row["text"]:
        label = docint.STATUS_LABELS.get(row["status"], "Henüz işlenmedi")
        raise HTTPException(
            status_code=404,
            detail=f"Bu kanıttan çıkarılmış metin yok. Durum: {label}.",
        )
    return PlainTextResponse(
        row["text"],
        media_type="text/plain; charset=utf-8",
        headers={"X-Content-Type-Options": "nosniff"},
    )


def _fingerprint_links(conn, evidence_id: str) -> list[FingerprintLink]:
    rows = fetch_all(
        conn.execute(
            "MATCH (ev:Evidence {id: $id})-[fp:FINGERPRINT_ENTITY]->(e:Entity) "
            "RETURN e.id AS entity_id, e.name AS entity_name, e.entity_type AS entity_type, "
            "fp.field AS field, fp.value AS value ORDER BY fp.created_at",
            {"id": evidence_id},
        )
    )
    return [FingerprintLink(**row) for row in rows]


@router.get("/{evidence_id}/fingerprint", response_model=EvidenceFingerprint)
def get_evidence_fingerprint(evidence_id: str) -> EvidenceFingerprint:
    """Faz 15.3 — belgenin üretildiği ortamın izi (metadata), OSINT anlamına göre gruplanmış.

    **Q22 uyarısı:** buradaki her `value` GÜVENİLMEYEN VERİDİR — belgeyi kim ürettiyse o
    yazmıştır. Faz 15 spike'ı `/Subject` alanına gömülü bir talimat denemesi doğruladı, bu
    yüzden metadata kaynaklı uyarılar yanıtın içinde ayrıca dönüyor. Bu alanları sunan hiçbir
    katman içeriklerini komut olarak yorumlamamalı."""
    conn = get_connection()
    row = fetch_one(
        conn.execute(
            "MATCH (ev:Evidence {id: $id}) RETURN ev.doc_metadata AS doc_metadata, "
            "ev.injection_hits AS injection_hits",
            {"id": evidence_id},
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    metadata = docint.metadata_from_json(row["doc_metadata"])
    hits = [h for h in docint.hits_from_json(row["injection_hits"])
            if str(h.get("where", "")).startswith("metadata")]
    return EvidenceFingerprint(
        evidence_id=evidence_id,
        groups=docint.fingerprint(metadata),
        links=_fingerprint_links(conn, evidence_id),
        injection_hits=hits,
    )


@router.put("/{evidence_id}/fingerprint/{entity_id}", response_model=EvidenceFingerprint)
def link_fingerprint_entity(
    evidence_id: str, entity_id: str, payload: FingerprintLinkCreate
) -> EvidenceFingerprint:
    """Bir metadata alanını graf'taki bir Entity'ye bağlar.

    **Öneri sistem, karar insan** (Design Principle #7). `/Author: Joint Task Force` bir
    kuruma benziyor olabilir, ama hangi Entity olduğu — ya da hiçbiri olmadığı — bir
    yargı. Sistem eşleşmeyi otomatik kurmuyor.

    Alanın o andaki ham değeri kenara yazılıyor: sonradan belge yeniden çıkarılıp metadata
    değişse bile "bu bağ kurulduğunda alan ne diyordu" cevaplanabilir kalsın (Q9 temporal
    disiplininin küçük bir karşılığı)."""
    conn = get_connection()
    if not _node_exists(conn, "Evidence", evidence_id):
        raise HTTPException(status_code=404, detail="Evidence not found")
    if not _node_exists(conn, "Entity", entity_id):
        raise HTTPException(status_code=404, detail="Entity not found")

    row = fetch_one(
        conn.execute(
            "MATCH (ev:Evidence {id: $id}) RETURN ev.doc_metadata AS doc_metadata",
            {"id": evidence_id},
        )
    )
    metadata = docint.metadata_from_json(row["doc_metadata"] if row else None)
    if payload.field not in metadata:
        raise HTTPException(
            status_code=422,
            detail=f"Bu belgenin metadata'sında '{payload.field}' alanı yok.",
        )
    if payload.field not in docint.LINKABLE_FIELDS:
        # Yazılım adı taşıyan alanları (Creator/Producer) Entity'ye bağlamak graf'ı
        # "Acrobat PDFMaker" gibi düğümlerle kirletirdi.
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{payload.field}' alanı bir kişi/kuruma işaret etmiyor. "
                f"Bağlanabilir alanlar: {', '.join(docint.LINKABLE_FIELDS)}."
            ),
        )

    existing = fetch_one(
        conn.execute(
            "MATCH (ev:Evidence {id: $eid})-[fp:FINGERPRINT_ENTITY]->(e:Entity {id: $enid}) "
            "WHERE fp.field = $field RETURN fp.field AS field",
            {"eid": evidence_id, "enid": entity_id, "field": payload.field},
        )
    )
    if existing is None:
        conn.execute(
            "MATCH (ev:Evidence {id: $eid}), (e:Entity {id: $enid}) "
            "CREATE (ev)-[:FINGERPRINT_ENTITY {field: $field, value: $value, created_at: $now}]->(e)",
            {
                "eid": evidence_id,
                "enid": entity_id,
                "field": payload.field,
                "value": metadata[payload.field],
                "now": datetime.now(timezone.utc),
            },
        )
        safe_render_vault(conn)
    return get_evidence_fingerprint(evidence_id)


@router.delete("/{evidence_id}/fingerprint/{entity_id}", status_code=204)
def unlink_fingerprint_entity(evidence_id: str, entity_id: str, field: str) -> None:
    """Yanlış kurulmuş bir parmak izi bağını kaldırır.

    Faz 13'ün F50'siyle aynı ders: bağ kurulabiliyorsa kaldırılabilmeli de — gerçek araştırma
    tek geçişte doğru olmuyor. Ne belge ne entity siliniyor, yalnızca aradaki yargı."""
    conn = get_connection()
    existing = fetch_one(
        conn.execute(
            "MATCH (ev:Evidence {id: $eid})-[fp:FINGERPRINT_ENTITY]->(e:Entity {id: $enid}) "
            "WHERE fp.field = $field RETURN fp.field AS field",
            {"eid": evidence_id, "enid": entity_id, "field": field},
        )
    )
    if existing is None:
        raise HTTPException(status_code=404, detail="Böyle bir parmak izi bağı yok")
    conn.execute(
        "MATCH (ev:Evidence {id: $eid})-[fp:FINGERPRINT_ENTITY]->(e:Entity {id: $enid}) "
        "WHERE fp.field = $field DELETE fp",
        {"eid": evidence_id, "enid": entity_id, "field": field},
    )
    safe_render_vault(conn)


@router.post("/{evidence_id}/observations", response_model=Observation, status_code=201)
def create_observation_from_evidence(
    evidence_id: str, payload: EvidenceObservationCreate
) -> Observation:
    """Faz 15.2 — belgenin bir sayfa aralığından Observation üretir.

    **Neden tüm belge değil, neden otomatik değil.** Promote, `raw_content`'i doğrudan claim
    metnine çeviriyor (`observations.py`); NIST SP 800-53r5 tek gözlem olsaydı 1,65 milyon
    karakterlik bir claim üretirdi. Her sayfayı otomatik gözleme çevirmek ise tek dosyadan
    492 gözlem demekti — Faz 16'nın açmaya çalıştığı değerlendirme darboğazını tek yüklemeyle
    tıkamak. Bu yüzden birim, kullanıcının seçtiği sayfa aralığı ve adım açıkça tetikleniyor
    (Design Principle #7: kritik kararı insan verir).

    **DOCINT ayrı bir boru hattı kurmuyor.** Üretilen gözlem, collector'dan gelen her gözlemle
    aynı: aynı `create_observation_record`, aynı daily log, aynı promote akışı (Q1/Q8). Tek
    farkı provenance'ının URL değil belge olması — o da EXTRACTED_FROM kenarında duruyor."""
    from app.routers.observations import create_observation_record, get_observation

    conn = get_connection()
    evidence = get_evidence(evidence_id)
    if payload.page_to < payload.page_from:
        raise HTTPException(status_code=422, detail="Bitiş sayfası başlangıçtan önce olamaz.")
    # Bu uç SENKRON: OCR sayfa başına ~1,3 sn, metin katmanı ~0,02 sn. Sınırsız bir aralık
    # isteği dakikalarca bekletiyor ve modülün kendi notunun kaçınmak istediği dev gözlemi
    # (1,6 milyon karakterlik bir claim) üretiyordu.
    sayfa = payload.page_to - payload.page_from + 1
    tavan = MAX_OCR_OBSERVATION_PAGES if evidence.text_source == "ocr" else MAX_OBSERVATION_PAGES
    if sayfa > tavan:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Tek gözlem için en fazla {tavan} sayfa seçilebilir ({sayfa} seçildi). "
                "Bir gözlem tek bir iddiaya dönüşecek birim olmalı — aralığı daralt."
            ),
        )
    path = _resolve_stored_file(evidence.file_path)
    if path is None:
        raise HTTPException(
            status_code=422,
            detail="Bu kanıtın vault'ta yüklenmiş bir dosyası yok, gözlem üretilemez.",
        )

    # Faz 15.4: belge OCR ile okunmuşsa metin katmanı YOKTUR — aynı yoldan okumaya
    # çalışmak NO_TEXT_LAYER verirdi. Kaynağa göre doğru okuyucu seçiliyor.
    if evidence.text_source == "ocr":
        result = docint.ocr_page_range(path, payload.page_from, payload.page_to)
    else:
        result = docint.extract_page_range(path, payload.page_from, payload.page_to)
    if result["status"] != docint.DONE:
        # Sessizce boş bir gözlem üretmektense reddediyoruz: bu fazın tamamı, içeriği
        # olmayan bir kaydın "işlenmiş" gibi görünmesini engellemek üzerine kurulu.
        raise HTTPException(
            status_code=422,
            detail=result["error"] or docint.STATUS_LABELS.get(result["status"], "Metin çıkarılamadı."),
        )

    observation = create_observation_record(
        result["text"],
        observed_at=evidence.collected_at or evidence.created_at,
        source_url=None,
        log_extra={
            "evidence_id": evidence_id,
            "page_from": payload.page_from,
            "page_to": payload.page_to,
            "text_source": evidence.text_source,
        },
        text_source=evidence.text_source,
    )
    conn.execute(
        "MATCH (o:Observation {id: $oid}), (ev:Evidence {id: $eid}) "
        "CREATE (o)-[:EXTRACTED_FROM {page_from: $pf, page_to: $pt, created_at: $now}]->(ev)",
        {
            "oid": observation.id,
            "eid": evidence_id,
            "pf": payload.page_from,
            "pt": payload.page_to,
            "now": datetime.now(timezone.utc),
        },
    )
    # Kenar kurulduktan SONRA yeniden okunuyor ki dönen nesne `from_evidence` taşısın.
    return get_observation(observation.id)


@router.post("/{evidence_id}/ocr", status_code=202)
def ocr_evidence(evidence_id: str) -> dict:
    """Faz 15.4 — belgeyi metin katmanından değil GÖRÜNTÜDEN okur (OCR).

    **Açık bir tercih, otomatik değil.** Taranmış 492 sayfalık bir belge dakikalar sürer;
    yüklemede sessizce başlatmak kullanıcıyı sürprizle karşılaştırırdı. Ayrıca OCR bir
    TAHMİNDİR: sonuç `text_source="ocr"` ve bir güven skoruyla saklanıp gözleme kadar
    taşınıyor — çıkarılmış metinle aynı güvenilirlikte sunulmamalı."""
    durum = docint.ocr_status()
    if not durum["available"]:
        # Sessizce başarısız olmak yerine SEBEBİ söylüyoruz: OCR sistem kurulumuna bağlı,
        # ve "neden okunamadı" sorusunun cevabı kullanıcıda olmalı.
        raise HTTPException(status_code=503, detail=durum["error"])
    conn = get_connection()
    if not _node_exists(conn, "Evidence", evidence_id):
        raise HTTPException(status_code=404, detail="Evidence not found")
    if _resolve_stored_file(get_evidence(evidence_id).file_path) is None:
        raise HTTPException(
            status_code=422,
            detail="Bu kanıtın vault'ta yüklenmiş bir dosyası yok, OCR yapılamaz.",
        )
    doc_worker.mark_pending(evidence_id)
    if not doc_worker.enqueue(evidence_id, "ocr"):
        raise HTTPException(status_code=503, detail="Belge işleyicisi çalışmıyor.")
    return {
        "evidence_id": evidence_id,
        "status": docint.PENDING,
        "status_label": "OCR sırada bekliyor",
        "lang": durum["lang"],
        "queue_depth": doc_worker.queue_depth(),
    }


@router.post("/{evidence_id}/extract", status_code=202)
def reextract_evidence(evidence_id: str) -> dict:
    """Bir kanıtı (yeniden) çıkarma kuyruğuna alır.

    İki gerçek ihtiyaç: (1) Faz 15.1'den ÖNCE yüklenmiş kanıtlar hiç işlenmemiş durumda —
    bu uç olmadan onlara ulaşmanın yolu yok; (2) `FAILED`/`CORRUPT` bir belge için tekrar
    denemek. Çıkarma idempotent: sonucu baştan yazıyor, tekrar çalıştırmak güvenli."""
    conn = get_connection()
    if not _node_exists(conn, "Evidence", evidence_id):
        raise HTTPException(status_code=404, detail="Evidence not found")
    if _resolve_stored_file(get_evidence(evidence_id).file_path) is None:
        raise HTTPException(
            status_code=422,
            detail="Bu kanıtın vault'ta yüklenmiş bir dosyası yok, çıkarılacak bir şey yok.",
        )
    doc_worker.mark_pending(evidence_id)
    if not doc_worker.enqueue(evidence_id):
        raise HTTPException(
            status_code=503,
            detail="Belge işleyicisi çalışmıyor. Backend'i yeniden başlatmayı dene.",
        )
    return {
        "evidence_id": evidence_id,
        "status": docint.PENDING,
        "status_label": docint.STATUS_LABELS[docint.PENDING],
        "queue_depth": doc_worker.queue_depth(),
    }


@router.get("/{evidence_id}/file")
def download_evidence_file(evidence_id: str) -> FileResponse:
    """Yüklenen kanıt dosyasını geri verir.

    Bu uç olmasaydı yükleme yalnızca YAZAN bir yol olurdu — bu projenin defalarca yakaladığı
    hata sınıfı (F34-F37: yazılıyor ama okunmuyor). Dosya her zaman ek (attachment) olarak
    ve `application/octet-stream` ile dönüyor: kanıt dosyaları güvenilmeyen kaynaklardan
    geliyor, tarayıcıda gömülü çalıştırılacak bir şey değil."""
    evidence = get_evidence(evidence_id)
    path = _resolve_stored_file(evidence.file_path)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Bu kanıtın yüklenmiş bir dosyası yok. (Elle girilen `file_path` alanı, "
                "vault'a yüklenmiş bir dosyaya işaret etmiyor olabilir.)"
            ),
        )
    # Depolanan ad "<hash16>-<özgün ad>"; kullanıcıya özgün adı geri veriyoruz.
    download_name = path.name.split("-", 1)[-1] or path.name
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=download_name,
        content_disposition_type="attachment",
    )


@router.get("/{evidence_id}/claims")
def list_evidence_claims(evidence_id: str) -> list[dict]:
    """Bu kanıtın bağlı olduğu claim'ler ve duruşları (SUPPORTS/CONTRADICTS).

    Faz 13 bulgusu: bu iki kenar yazılabiliyordu (Faz 10) ve confidence hesabında
    SAYILIYORDU, ama hiçbir uç onları LİSTELEMİYORDU — yani "bu kanıt neyi destekliyor"
    sorusunun cevabı yalnızca dolaylı olarak (claim'in confidence'ı üzerinden) görülebiliyordu."""
    conn = get_connection()
    if not _node_exists(conn, "Evidence", evidence_id):
        raise HTTPException(status_code=404, detail="Evidence not found")
    rows = []
    for stance, rel in _STANCE_TO_REL.items():
        rows += [
            {**row, "stance": stance}
            for row in fetch_all(
                conn.execute(
                    f"MATCH (ev:Evidence {{id: $id}})-[:{rel}]->(c:Claim) "
                    "OPTIONAL MATCH (s:Source)-[:ASSERTS]->(c) "
                    "RETURN c.id AS claim_id, c.text AS text, "
                    "c.knowledge_state AS knowledge_state, c.confidence AS confidence, "
                    "s.id AS source_id, s.name AS source_name ORDER BY c.created_at",
                    {"id": evidence_id},
                )
            )
        ]
    for row in rows:
        row["headline"] = claim_headline(row.pop("text"))
    return rows


@router.delete("/{evidence_id}/claims/{claim_id}", status_code=204)
def unlink_evidence_from_claim(evidence_id: str, claim_id: str) -> None:
    """Yanlış claim'e bağlanmış bir kanıtın bağını kaldırır.

    Faz 13 bulgusu: bağ KURULABİLİYOR ama kaldırılamıyordu — ve yanlış bağ zararsız değil,
    claim'in confidence'ını doğrudan değiştiriyor (CONTRADICTS ise ceza dalını tetikliyor).
    Bu, F16 (about bağı sonradan düzeltilemiyordu) ve F26 (çelişki sonradan kurulamıyordu)
    ile aynı sınıftan: gerçek araştırma tek geçişte doğru olmuyor.

    History Is Immutable ile çelişmez: ne kanıt ne claim siliniyor, yalnızca aralarındaki
    yanlış kurulmuş ilişki kaldırılıyor ve confidence yeniden hesaplanıyor."""
    conn = get_connection()
    if not _node_exists(conn, "Evidence", evidence_id):
        raise HTTPException(status_code=404, detail="Evidence not found")
    if not _node_exists(conn, "Claim", claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    removed = False
    for rel in _STANCE_TO_REL.values():
        existing = fetch_one(
            conn.execute(
                f"MATCH (ev:Evidence {{id: $eid}})-[r:{rel}]->(c:Claim {{id: $cid}}) RETURN ev.id AS id",
                {"eid": evidence_id, "cid": claim_id},
            )
        )
        if existing is not None:
            conn.execute(
                f"MATCH (ev:Evidence {{id: $eid}})-[r:{rel}]->(c:Claim {{id: $cid}}) DELETE r",
                {"eid": evidence_id, "cid": claim_id},
            )
            removed = True
    if not removed:
        raise HTTPException(status_code=404, detail="Bu kanıt ile claim arasında bir bağ yok")
    _recompute_and_store(conn, claim_id)
    safe_render_vault(conn)


@router.get("", response_model=list[EvidenceVaultItem])
def list_evidence(include_archives: bool = False) -> list[EvidenceVaultItem]:
    """Evidence Vault listesi: her kanıt, bağlı claim'leri ve dosyasının gerçekten var olup
    olmadığıyla birlikte.

    `has_file` hesaplanan bir alan: `file_path` dolu olsa bile dosya yerinde olmayabilir
    (elle girilmiş bir yol, ya da taşınmış bir dosya). Bunu göstermemek, indirilemeyen bir
    kanıtı indirilebilir gibi sunmak olurdu.

    Faz 26: arşiv kayıtları varsayılan olarak DIŞARIDA. Kasa, kullanıcının kendi eklediği
    kanıtların yeri; arşiv ise her promote'ta kendiliğinden oluşan bir provenance kaydı.
    Karıştırılsalardı 3 belgelik kasa bir gecede 58 satır olur ve elle yüklenen kanıt
    kendi kasasında kaybolurdu. Arşivlerin yeri `/archive`."""
    conn = get_connection()
    where = "" if include_archives else "WHERE ev.evidence_type <> $archive_type "
    params = {} if include_archives else {"archive_type": archive.ARCHIVE_TYPE}
    result = conn.execute(f"MATCH (ev:Evidence) {where}RETURN {_FIELDS} ORDER BY ev.created_at", params)
    items = []
    for row in fetch_all(result):
        items.append(
            EvidenceVaultItem(
                **_with_status_label(row),
                has_file=_resolve_stored_file(row["file_path"]) is not None,
                linked_claims=list_evidence_claims(row["id"]),
            )
        )
    return items


@router.get("/{evidence_id}", response_model=Evidence)
def get_evidence(evidence_id: str) -> Evidence:
    conn = get_connection()
    result = conn.execute(f"MATCH (ev:Evidence {{id: $id}}) RETURN {_FIELDS}", {"id": evidence_id})
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return Evidence(**_with_status_label(row))


@router.put("/{evidence_id}/claims/{claim_id}")
def link_evidence_to_claim(evidence_id: str, claim_id: str, payload: EvidenceClaimLink) -> dict:
    """Var olan bir Evidence'ı, sonradan bir Claim'e SUPPORTS ya da CONTRADICTS olarak
    bağlar (Faz 10 — create_claim'in evidence_ids/contradicting_evidence_ids ile aynı
    kenarları yaratır, sadece Claim oluşturulduktan SONRA çağrılabilir)."""
    conn = get_connection()
    if payload.stance not in _STANCE_TO_REL:
        raise HTTPException(status_code=422, detail="stance must be SUPPORTS or CONTRADICTS")
    if not _node_exists(conn, "Evidence", evidence_id):
        raise HTTPException(status_code=404, detail="Evidence not found")
    if not _node_exists(conn, "Claim", claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    rel = _STANCE_TO_REL[payload.stance]
    conn.execute(
        f"MATCH (ev:Evidence {{id: $eid}}), (c:Claim {{id: $cid}}) CREATE (ev)-[:{rel}]->(c)",
        {"eid": evidence_id, "cid": claim_id},
    )
    result = _recompute_and_store(conn, claim_id)
    about_entity_id, about_event_id = _claim_about(conn, claim_id)
    _notify_change(
        conn,
        claim_id=claim_id,
        about_entity_id=about_entity_id,
        about_event_id=about_event_id,
        result=result,
        title=f"Bir claim'e yeni kanıt bağlandı ({payload.stance})",
    )
    safe_render_vault(conn)
    return {
        "claim": get_claim(claim_id).model_dump(mode="json"),
        "evidence_id": evidence_id,
        "stance": payload.stance,
    }
