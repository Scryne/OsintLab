import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.confidence import ConfidenceResult, compute_confidence
from app.db import fetch_all, fetch_one, get_connection
from app.models import Claim, ClaimCreate
from app.recall import why_matters

router = APIRouter(prefix="/claims", tags=["claims"])

_FIELDS = (
    "c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
    "c.confidence AS confidence, c.valid_from AS valid_from, c.valid_to AS valid_to, "
    "c.created_at AS created_at"
)


def _node_exists(conn, label: str, node_id: str) -> bool:
    result = conn.execute(f"MATCH (n:{label} {{id: $id}}) RETURN n.id AS id", {"id": node_id})
    return fetch_one(result) is not None


def _claim_source_id(conn, claim_id: str) -> str | None:
    result = conn.execute(
        "MATCH (s:Source)-[:ASSERTS]->(c:Claim {id: $id}) RETURN s.id AS id, s.reliability AS reliability",
        {"id": claim_id},
    )
    row = fetch_one(result)
    return row


def _claim_about(conn, claim_id: str) -> tuple[str | None, str | None]:
    entity_row = fetch_one(
        conn.execute(
            "MATCH (c:Claim {id: $id})-[:ABOUT_ENTITY]->(e:Entity) RETURN e.id AS id", {"id": claim_id}
        )
    )
    event_row = fetch_one(
        conn.execute(
            "MATCH (c:Claim {id: $id})-[:ABOUT_EVENT]->(e:Event) RETURN e.id AS id", {"id": claim_id}
        )
    )
    return (entity_row["id"] if entity_row else None, event_row["id"] if event_row else None)


def _gather_confidence_inputs(conn, claim_id: str) -> ConfidenceResult:
    source_row = _claim_source_id(conn, claim_id)
    source_reliability = source_row["reliability"] if source_row else 0.5

    corroborators = fetch_all(
        conn.execute(
            "MATCH (s:Source)-[:ASSERTS]->(other:Claim)-[:CORROBORATES]->(c:Claim {id: $id}) "
            "RETURN DISTINCT s.id AS source_id, other.id AS claim_id",
            {"id": claim_id},
        )
    )
    corroborating_source_ids = {row["source_id"] for row in corroborators}
    corroborating_claims_count = len({row["claim_id"] for row in corroborators})

    evidence_count = len(
        fetch_all(
            conn.execute(
                "MATCH (ev:Evidence)-[:SUPPORTS]->(c:Claim {id: $id}) RETURN ev.id AS id",
                {"id": claim_id},
            )
        )
    )
    contradicting_evidence_count = len(
        fetch_all(
            conn.execute(
                "MATCH (ev:Evidence)-[:CONTRADICTS]->(c:Claim {id: $id}) RETURN ev.id AS id",
                {"id": claim_id},
            )
        )
    )

    outgoing_unresolved = fetch_all(
        conn.execute(
            "MATCH (c:Claim {id: $id})-[r:CLAIM_CONTRADICTS]->(other:Claim) "
            "WHERE r.status = 'UNRESOLVED' RETURN other.id AS id",
            {"id": claim_id},
        )
    )
    incoming_unresolved = fetch_all(
        conn.execute(
            "MATCH (other:Claim)-[r:CLAIM_CONTRADICTS]->(c:Claim {id: $id}) "
            "WHERE r.status = 'UNRESOLVED' RETURN other.id AS id",
            {"id": claim_id},
        )
    )
    has_unresolved_contradiction = bool(outgoing_unresolved or incoming_unresolved)

    return compute_confidence(
        source_reliability=source_reliability,
        corroborating_source_ids=corroborating_source_ids,
        corroborating_claims_count=corroborating_claims_count,
        evidence_count=evidence_count,
        contradicting_evidence_count=contradicting_evidence_count,
        has_unresolved_contradiction=has_unresolved_contradiction,
    )


def _recompute_and_store(conn, claim_id: str) -> ConfidenceResult:
    result = _gather_confidence_inputs(conn, claim_id)
    conn.execute(
        "MATCH (c:Claim {id: $id}) SET c.confidence = $confidence, c.knowledge_state = $state",
        {"id": claim_id, "confidence": result.confidence, "state": result.knowledge_state},
    )
    return result


def _row_to_claim(conn, row: dict) -> Claim:
    source_row = _claim_source_id(conn, row["id"])
    return Claim(source_id=source_row["id"] if source_row else "", **row)


@router.post("", response_model=Claim, status_code=201)
def create_claim(payload: ClaimCreate) -> Claim:
    conn = get_connection()

    if not _node_exists(conn, "Source", payload.source_id):
        raise HTTPException(status_code=404, detail=f"Source not found: {payload.source_id}")
    if payload.about_entity_id and not _node_exists(conn, "Entity", payload.about_entity_id):
        raise HTTPException(status_code=404, detail=f"Entity not found: {payload.about_entity_id}")
    if payload.about_event_id and not _node_exists(conn, "Event", payload.about_event_id):
        raise HTTPException(status_code=404, detail=f"Event not found: {payload.about_event_id}")
    for eid in payload.evidence_ids:
        if not _node_exists(conn, "Evidence", eid):
            raise HTTPException(status_code=404, detail=f"Evidence not found: {eid}")
    for cid in payload.corroborates + payload.contradicts:
        if not _node_exists(conn, "Claim", cid):
            raise HTTPException(status_code=404, detail=f"Claim not found: {cid}")
    if payload.supersedes and not _node_exists(conn, "Claim", payload.supersedes):
        raise HTTPException(status_code=404, detail=f"Claim not found: {payload.supersedes}")

    claim_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    conn.execute(
        "CREATE (:Claim {id: $id, text: $text, knowledge_state: 'OBSERVED', confidence: 0.0, "
        "valid_from: $now, valid_to: NULL, created_at: $now})",
        {"id": claim_id, "text": payload.text, "now": now},
    )
    conn.execute(
        "MATCH (s:Source {id: $sid}), (c:Claim {id: $cid}) CREATE (s)-[:ASSERTS]->(c)",
        {"sid": payload.source_id, "cid": claim_id},
    )
    if payload.about_entity_id:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (e:Entity {id: $eid}) CREATE (c)-[:ABOUT_ENTITY]->(e)",
            {"cid": claim_id, "eid": payload.about_entity_id},
        )
    if payload.about_event_id:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (e:Event {id: $eid}) CREATE (c)-[:ABOUT_EVENT]->(e)",
            {"cid": claim_id, "eid": payload.about_event_id},
        )
    for eid in payload.evidence_ids:
        conn.execute(
            "MATCH (ev:Evidence {id: $eid}), (c:Claim {id: $cid}) CREATE (ev)-[:SUPPORTS]->(c)",
            {"eid": eid, "cid": claim_id},
        )

    # Q4 corroboration: simetrik bir ilişki — bağımsız iki claim aynı şeyi doğruluyorsa
    # ikisi de birbirini destekler, bu yüzden ilişki her iki yönde de kurulur ve her iki
    # claim de yeniden hesaplanır.
    for cid in payload.corroborates:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (other:Claim {id: $oid}) "
            "CREATE (c)-[:CORROBORATES]->(other) CREATE (other)-[:CORROBORATES]->(c)",
            {"cid": claim_id, "oid": cid},
        )
        _recompute_and_store(conn, cid)

    # Q9 Contradiction: eski bilgi SİLİNMEZ, her iki claim de CONTRADICTED'a döner,
    # çelişki UNRESOLVED olarak kaydedilir.
    for cid in payload.contradicts:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (other:Claim {id: $oid}) "
            "CREATE (c)-[:CLAIM_CONTRADICTS {status: 'UNRESOLVED', detected_at: $now}]->(other)",
            {"cid": claim_id, "oid": cid, "now": now},
        )
        _recompute_and_store(conn, cid)

    # Q9 temporal versiyonlama: eski claim silinmez, valid_to = şimdi ile "supersede" edilir.
    if payload.supersedes:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (old:Claim {id: $oid}) "
            "CREATE (c)-[:SUPERSEDES {at: $now}]->(old)",
            {"cid": claim_id, "oid": payload.supersedes, "now": now},
        )
        conn.execute(
            "MATCH (old:Claim {id: $oid}) SET old.valid_to = $now",
            {"oid": payload.supersedes, "now": now},
        )

    _recompute_and_store(conn, claim_id)
    return get_claim(claim_id)


@router.get("", response_model=list[Claim])
def list_claims() -> list[Claim]:
    conn = get_connection()
    result = conn.execute(f"MATCH (c:Claim) RETURN {_FIELDS} ORDER BY c.created_at")
    return [_row_to_claim(conn, row) for row in fetch_all(result)]


@router.get("/{claim_id}", response_model=Claim)
def get_claim(claim_id: str) -> Claim:
    conn = get_connection()
    result = conn.execute(f"MATCH (c:Claim {{id: $id}}) RETURN {_FIELDS}", {"id": claim_id})
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return _row_to_claim(conn, row)


@router.get("/{claim_id}/explain")
def explain_claim(claim_id: str) -> dict:
    """Auditability: 'Sistem bunu neden düşünüyor?' — confidence'ın alt-skor kırılımı."""
    conn = get_connection()
    if not _node_exists(conn, "Claim", claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    result = _gather_confidence_inputs(conn, claim_id)
    return {
        "claim_id": claim_id,
        "source_quality": result.source_quality,
        "independence": result.independence,
        "evidence": result.evidence,
        "corroboration": result.corroboration,
        "confidence": result.confidence,
        "knowledge_state": result.knowledge_state,
        "weights": {
            "source_quality": 0.40,
            "independence": 0.25,
            "evidence": 0.20,
            "corroboration": 0.15,
        },
    }


@router.get("/{claim_id}/why-matters")
def claim_why_matters(claim_id: str) -> dict:
    """Q12: kural + graph tabanlı 'neden önemli' gerekçesi. AI bu listeyi akıcı cümleye
    çevirebilir (bkz. .claude/skills/osint-brain/) ama karar mantığı burada, deterministik."""
    conn = get_connection()
    row = fetch_one(conn.execute(f"MATCH (c:Claim {{id: $id}}) RETURN {_FIELDS}", {"id": claim_id}))
    if row is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    confidence_result = _gather_confidence_inputs(conn, claim_id)
    about_entity_id, about_event_id = _claim_about(conn, claim_id)
    reasons = why_matters(conn, claim_id, row, confidence_result, about_entity_id, about_event_id)
    return {"claim_id": claim_id, "reasons": reasons}
