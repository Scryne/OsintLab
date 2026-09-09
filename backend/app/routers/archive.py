"""Faz 26 — arşiv uçları.

Ayrı bir router, çünkü arşiv iki düğümün ORTASINDA duruyor: Evidence olarak yaşıyor ama
her zaman bir Claim'e ait. `/claims` altına konsaydı Kanıt Kasası'ndan görünmez, `/evidence`
altına konsaydı "bu claim'in arşivi var mı" sorusu claim tarafından cevaplanamazdı.

Yol `/archive`; her uç claim_id ile konuşur çünkü kullanıcının sorusu her zaman
"BU iddianın dayanağı duruyor mu" biçimindedir.
"""
from fastapi import APIRouter, HTTPException

from app import archive
from app.db import fetch_one, get_connection
from app.monitoring import claim_headline
from app.models import (
    ArchiveBatchItem,
    ArchiveBatchRequest,
    ArchiveBatchResult,
    ArchiveRecord,
    ArchiveVerifyItem,
    ArchiveVerifyRequest,
    ArchiveVerifyResult,
)
from app.routers.claims import _recompute_and_store
from app.vault import safe_render_vault

router = APIRouter(prefix="/archive", tags=["archive"])


def _record(conn, row: dict) -> ArchiveRecord:
    scored = fetch_one(
        conn.execute(
            "MATCH (ev:Evidence {id: $eid})-[:SUPPORTS]->(c:Claim {id: $cid}) RETURN ev.id AS id",
            {"eid": row["evidence_id"], "cid": row["claim_id"]},
        )
    ) is not None
    status = row["archive_status"] or archive.ARSIVLENDI
    return ArchiveRecord(
        evidence_id=row["evidence_id"], claim_id=row["claim_id"],
        archive_url=row["archive_url"], archive_status=status,
        archive_status_label=archive.STATUS_LABELS.get(status, status),
        archive_match=row["archive_match"], archive_checked_at=row["archive_checked_at"],
        archive_note=row["archive_note"], content_hash=row["content_hash"],
        collected_at=row["collected_at"], scored=scored,
        claim_headline=claim_headline(row.get("claim_text") or ""),
        claim_state=row.get("claim_state"), claim_confidence=row.get("claim_confidence"),
    )


@router.get("", response_model=list[ArchiveRecord])
def list_archives() -> list[ArchiveRecord]:
    conn = get_connection()
    return [_record(conn, row) for row in archive.archive_rows(conn)]


@router.get("/pending", response_model=list[str])
def list_claims_without_archive() -> list[str]:
    """Arşivi olmayan claim'ler. Geri doldurmanın ne kadar iş olduğunu söyler."""
    return archive.claims_without_archive(get_connection())


@router.get("/claims/{claim_id}", response_model=ArchiveRecord)
def get_claim_archive(claim_id: str) -> ArchiveRecord:
    conn = get_connection()
    rows = archive.archive_rows(conn, [claim_id])
    if not rows:
        raise HTTPException(status_code=404, detail="Bu claim'in arşiv kopyası yok.")
    return _record(conn, rows[0])


@router.post("/create", response_model=ArchiveBatchResult)
def create_archives(payload: ArchiveBatchRequest) -> ArchiveBatchResult:
    """Arşiv kopyalarını üretir. Ağ KULLANMAZ — arşiv gözlemin ham metninden doğar.

    `claim_ids` boşsa arşivi olmayan tüm claim'ler işlenir (geri doldurma)."""
    conn = get_connection()
    ids = payload.claim_ids or archive.claims_without_archive(conn)
    items = [ArchiveBatchItem(**archive.create_archive(conn, cid)) for cid in ids]
    created = sum(1 for i in items if i.action == "olusturuldu")
    if created:
        safe_render_vault(conn)
    return ArchiveBatchResult(
        created=created,
        already=sum(1 for i in items if i.action == "zaten_var"),
        skipped=sum(1 for i in items if i.action == "atlandi"),
        items=items,
    )


@router.post("/verify", response_model=ArchiveVerifyResult)
def verify_archives(payload: ArchiveVerifyRequest) -> ArchiveVerifyResult:
    """Arşivleri canlı sayfaya karşı doğrular ve skor kenarını buna göre kurar/kaldırır.

    Her kaydın confidence'ı doğrulamadan ÖNCE ve SONRA dönüyor: fazın sınavı "en az bir
    claim yalnızca kanıt sayesinde durum değiştirdi mi" olduğu için, bu farkı ölçmenin
    kullanıcıdan gizlenmiş bir yolu olmamalı."""
    conn = get_connection()
    rows = archive.archive_rows(conn, payload.claim_ids)
    items: list[ArchiveVerifyItem] = []
    state_changes = 0
    for row in rows:
        before = fetch_one(
            conn.execute(
                "MATCH (c:Claim {id: $cid}) RETURN c.confidence AS confidence, "
                "c.knowledge_state AS state",
                {"cid": row["claim_id"]},
            )
        ) or {"confidence": None, "state": None}
        result = archive.verify_archive(conn, row["evidence_id"], row["claim_id"])
        after = _recompute_and_store(conn, row["claim_id"])
        if before["state"] != after.knowledge_state:
            state_changes += 1
        items.append(ArchiveVerifyItem(
            evidence_id=result["evidence_id"], claim_id=result["claim_id"],
            status=result["status"],
            status_label=archive.STATUS_LABELS.get(result["status"] or "", result["note"]),
            match=result["match"], note=result["note"], scored=result["scored"],
            confidence_before=before["confidence"], confidence_after=after.confidence,
            state_before=before["state"], state_after=after.knowledge_state,
        ))
    if items:
        safe_render_vault(conn)
    return ArchiveVerifyResult(
        checked=len(items),
        verified=sum(1 for i in items if i.status == archive.DOGRULANDI),
        changed=sum(1 for i in items if i.status == archive.DEGISMIS),
        unreachable=sum(1 for i in items if i.status == archive.ERISILEMEDI),
        state_changes=state_changes,
        items=items,
    )
