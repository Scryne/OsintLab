import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.db import fetch_all, fetch_one, get_connection
from app.models import Evidence, EvidenceClaimLink, EvidenceCreate
from app.routers.claims import _claim_about, _node_exists, _notify_change, _recompute_and_store, get_claim
from app.vault import safe_render_vault

router = APIRouter(prefix="/evidence", tags=["evidence"])

_STANCE_TO_REL = {"SUPPORTS": "SUPPORTS", "CONTRADICTS": "CONTRADICTS"}

_FIELDS = (
    "ev.id AS id, ev.evidence_type AS evidence_type, ev.file_path AS file_path, "
    "ev.content_hash AS content_hash, ev.collected_at AS collected_at, ev.created_at AS created_at"
)


def _hash_file_if_present(file_path: str | None) -> str | None:
    """Q18: dosya yerelde varsa bütünlük hash'i hesaplanır; yoksa None döner (caller
    kendi hash'ini vermiş olabilir, ya da dosya henüz collector tarafından indirilmemiştir)."""
    if not file_path:
        return None
    path = Path(file_path)
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
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


@router.get("", response_model=list[Evidence])
def list_evidence() -> list[Evidence]:
    conn = get_connection()
    result = conn.execute(f"MATCH (ev:Evidence) RETURN {_FIELDS} ORDER BY ev.created_at")
    return [Evidence(**row) for row in fetch_all(result)]


@router.get("/{evidence_id}", response_model=Evidence)
def get_evidence(evidence_id: str) -> Evidence:
    conn = get_connection()
    result = conn.execute(f"MATCH (ev:Evidence {{id: $id}}) RETURN {_FIELDS}", {"id": evidence_id})
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return Evidence(**row)


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
