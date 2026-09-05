"""
Faz 15.1 — DOCINT arka plan işçisi: "belge ne zaman işlenir" sorusunun cevabı.
Çıkarmanın kendisi `app/docint.py` içinde (Faz 12'deki scanning/scheduler ayrımının aynısı).

**Neden arka plan? Bu bir tercih değil, ölçülmüş bir zorunluluk.**
Faz 15 spike'ı NIST SP 800-53r5'i (6,1 MB / 492 sayfa) baştan sona çıkarmanın **29,9 saniye**
sürdüğünü gösterdi. `POST /evidence/upload` senkron bir uç; çıkarma oraya konsaydı tek bir
belge yüklemesi API'nin tamamını yarım dakika kilitlerdi (uvicorn'un iş parçacığı havuzu
dolar, zamanlanmış tarama dahil her şey beklerdi).

Spike'ın ikinci ölçümü bu çözümü mümkün kılıyor: maliyet TAMAMEN sayfa metni çıkarmada ve
sayfa başına bölünebiliyor (`PdfReader()` açılışı 0,11 sn, sayfa başına ~0,022 sn). Yani iş
parçalanabiliyor ve gerçek bir ilerleme yazılabiliyor — "işleniyor" derken kaçıncı sayfada
olduğu biliniyor.

**Neden ayrı bir süreç değil?** Zamanlayıcıyla aynı gerekçe (bkz. `scheduler.py`): KùzuDB
gömülü ve veritabanı dosyasını aynı anda tek süreç açabiliyor. Ayrı süreç grafa yazamaz.

**Yeniden başlatmaya dayanıklılık.** Kuyruk bellekte, ama gerçek kaynak veritabanı: açılışta
`PENDING` ya da `RUNNING` durumunda kalmış her Evidence yeniden kuyruğa alınıyor. `RUNNING`
kalmış bir kayıt, backend'in çıkarmanın ortasında kapandığı anlamına gelir — çıkarma
idempotent (sonucu baştan yazıyor), o yüzden tekrar çalıştırmak güvenli. Bu olmasaydı
yükleme anında kapanan bir backend, belgeyi sonsuza dek "işleniyor"da bırakırdı.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app import docint
from app.db import fetch_all, fetch_one, get_connection

logger = logging.getLogger(__name__)

# Kuyruk ögesi: (evidence_id, mod). Mod "extract" (metin katmanı) ya da "ocr".
_queue: asyncio.Queue[tuple[str, str]] | None = None
_task: asyncio.Task | None = None


# --- Veritabanı yazmaları (işçi iş parçacığından çağrılır) -----------------------------

def _set_status(evidence_id: str, status: str, **fields) -> None:
    conn = get_connection()
    assignments = ["ev.extraction_status = $status"]
    params: dict = {"id": evidence_id, "status": status}
    for key, value in fields.items():
        assignments.append(f"ev.{key} = ${key}")
        params[key] = value
    conn.execute(
        f"MATCH (ev:Evidence {{id: $id}}) SET {', '.join(assignments)}",
        params,
    )


def process_evidence(evidence_id: str, mode: str = "extract") -> str:
    """Tek bir Evidence'ı işler ve bitiş durumunu döndürür. Bu fonksiyon bloklar —
    her zaman `asyncio.to_thread` içinden çağrılmalı.

    `mode="ocr"` (Faz 15.4) belgeyi metin katmanından değil GÖRÜNTÜDEN okur. Ayrı bir mod,
    çünkü OCR açık bir kullanıcı tercihi: taranmış 492 sayfalık bir belge dakikalar sürer,
    sürpriz olarak başlatılmamalı."""
    # Geç import: routers.evidence -> routers.claims -> ... zincirini modül yüklenirken
    # değil çağrı anında kurar (scanning.py'deki aynı desen).
    from app.routers.evidence import _resolve_stored_file

    conn = get_connection()
    row = fetch_one(
        conn.execute(
            "MATCH (ev:Evidence {id: $id}) RETURN ev.file_path AS file_path",
            {"id": evidence_id},
        )
    )
    if row is None:
        logger.warning("DOCINT: Evidence %s bulunamadı, atlanıyor", evidence_id[:8])
        return docint.FAILED

    path = _resolve_stored_file(row["file_path"])
    if path is None:
        _set_status(
            evidence_id,
            docint.FAILED,
            extraction_error="Kanıtın vault'ta yüklenmiş bir dosyası yok.",
            extracted_at=datetime.now(timezone.utc),
        )
        return docint.FAILED

    _set_status(evidence_id, docint.RUNNING, pages_done=0, extraction_error=None)

    def on_progress(done: int, total: int) -> None:
        # İlerleme "işleniyor" durumunu bozmadan yazılıyor; kullanıcı 492 sayfalık bir
        # belgede nerede olunduğunu görebilsin diye.
        try:
            _set_status(evidence_id, docint.RUNNING, pages_done=done, page_count=total)
        except Exception:  # noqa: BLE001 — ilerleme yazması çıkarmayı düşürmemeli
            logger.debug("DOCINT: ilerleme yazılamadı (%s)", evidence_id[:8])

    try:
        if mode == "ocr":
            sayfa_sayisi = docint.page_count_of(path)
            result = docint.ocr_page_range(path, 1, sayfa_sayisi, on_progress=on_progress)
            result["metadata"] = docint.extract(path)["metadata"] if sayfa_sayisi else {}
        else:
            result = docint.extract(path, on_progress=on_progress)
    except Exception as exc:  # noqa: BLE001 — işçi hiçbir belgede ölmemeli
        logger.exception("DOCINT: %s çıkarılırken beklenmedik hata", evidence_id[:8])
        _set_status(
            evidence_id,
            docint.FAILED,
            extraction_error=f"{type(exc).__name__}: {exc}",
            extracted_at=datetime.now(timezone.utc),
        )
        return docint.FAILED

    # Q22 (Faz 15.2): belge metni ve metadata'sı talimat-görünümlü ifade taşıyabiliyor —
    # Faz 15 spike'ı ikisinde de gerçek örnek doğruladı. Tarama çıkarmanın parçası, çünkü
    # sonucun kullanıcıya ulaşması için ayrı bir adım beklenmemeli.
    hits = docint.scan_for_injection(result["text"], result["metadata"])
    if hits:
        logger.warning(
            "DOCINT (%s): belgede %s talimat-görünümlü ifade bulundu — veri olarak işlendi, "
            "komut olarak DEĞİL",
            evidence_id[:8],
            len(hits),
        )

    _set_status(
        evidence_id,
        result["status"],
        extracted_text=result["text"],
        doc_metadata=docint.metadata_to_json(result["metadata"]),
        page_count=result["page_count"],
        pages_done=result["pages_done"],
        extraction_error=result["error"],
        extracted_at=datetime.now(timezone.utc),
        injection_hits=docint.hits_to_json(hits),
        # `text_source` YALNIZCA gerçekten metin üretildiğinde yazılıyor. Aksi halde
        # OCR'lanmaya çalışılmış ama PDF bile olmayan bir dosya kalıcı olarak "ocr kaynaklı"
        # görünüyordu ve arayüz ona sonsuza dek "Yeniden OCR" öneriyordu (görsel turda
        # yakalandı). Metin yoksa kaynak da yoktur.
        text_source=(("ocr" if mode == "ocr" else "extracted") if result["status"] == docint.DONE else None),
        ocr_confidence=result.get("confidence"),
        ocr_lang=result.get("lang"),
    )
    logger.info(
        "DOCINT tamam (%s): %s — %s sayfa, %s karakter",
        evidence_id[:8],
        result["status"],
        result["page_count"],
        len(result["text"]),
    )
    return result["status"]


def mark_pending(evidence_id: str) -> None:
    """Bir kanıtı kuyruğa alınmış olarak işaretler (DB tarafı).

    Kuyruğa koymadan ÖNCE çağrılır: kayıt bir an bile durumsuz kalmasın. Aksi halde yükleme
    ile işçinin sırayı alması arasındaki boşlukta arayüz belgeyi "hiç işlenmemiş" gösterirdi."""
    _set_status(evidence_id, docint.PENDING, pages_done=0, extraction_error=None)


# --- Kuyruk (olay döngüsünden çağrılır) -------------------------------------------------

def enqueue(evidence_id: str, mode: str = "extract") -> bool:
    """Bir kanıtı işleme kuyruğuna ekler. Olay döngüsü iş parçacığından çağrılmalı."""
    if _queue is None:
        logger.warning("DOCINT: işçi çalışmıyor, %s kuyruğa alınamadı", evidence_id[:8])
        return False
    _queue.put_nowait((evidence_id, mode))
    return True


async def _worker() -> None:
    assert _queue is not None
    while True:
        evidence_id, mode = await _queue.get()
        try:
            await asyncio.to_thread(process_evidence, evidence_id, mode)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — döngü hiçbir hatada ölmemeli
            logger.exception("DOCINT işçisi beklenmedik şekilde çöktü (%s)", evidence_id[:8])
        finally:
            _queue.task_done()


def _sweep_unfinished() -> list[str]:
    """Açılışta yarım kalmış işleri bulur (bkz. modül başlığı: yeniden başlatmaya dayanıklılık)."""
    conn = get_connection()
    rows = fetch_all(
        conn.execute(
            "MATCH (ev:Evidence) WHERE ev.extraction_status IN $states "
            "RETURN ev.id AS id ORDER BY ev.created_at",
            {"states": [docint.PENDING, docint.RUNNING]},
        )
    )
    return [r["id"] for r in rows]


def start() -> bool:
    global _queue, _task
    if _task is not None and not _task.done():
        return True
    _queue = asyncio.Queue()
    _task = asyncio.create_task(_worker(), name="osintlab-docint-worker")

    try:
        unfinished = _sweep_unfinished()
    except Exception:  # noqa: BLE001 — tarama başarısız olsa da işçi ayakta kalmalı
        logger.exception("DOCINT: yarım kalmış işler taranamadı")
        unfinished = []
    for evidence_id in unfinished:
        # Yarım kalan iş her zaman metin katmanı modunda yeniden denenir; OCR açık bir
        # tercih olduğu için kendiliğinden yeniden başlatılmıyor.
        _queue.put_nowait((evidence_id, "extract"))
    if unfinished:
        logger.info("DOCINT: yarım kalmış %s belge yeniden kuyruğa alındı", len(unfinished))
    logger.info("DOCINT işçisi başladı")
    return True


async def stop() -> None:
    global _task, _queue
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    finally:
        _task = None
        _queue = None


def is_running() -> bool:
    return _task is not None and not _task.done()


def queue_depth() -> int:
    return _queue.qsize() if _queue is not None else 0
