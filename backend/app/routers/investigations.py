import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import fetch_all, fetch_one, get_connection
from app.models import (
    INVESTIGATION_TRANSITIONS,
    Hypothesis,
    HypothesisCreate,
    HypothesisEvidenceLink,
    Investigation,
    InvestigationCreate,
    InvestigationTransition,
)
from app.monitoring import notify_if_monitored

router = APIRouter(prefix="/investigations", tags=["investigations"])
hypotheses_router = APIRouter(prefix="/hypotheses", tags=["hypotheses"])

_INV_FIELDS = (
    "i.id AS id, i.title AS title, i.research_question AS research_question, "
    "i.status AS status, i.created_at AS created_at, i.updated_at AS updated_at"
)
_HYP_FIELDS = "h.id AS id, h.text AS text, h.status AS status, h.created_at AS created_at"

# Q17: kapanışta sadece bu knowledge_state'lere sahip finding'ler "doğrulanmış" sayılıp
# long-term memory'ye (VALIDATED_FINDING ilişkisiyle) promote edilir.
VERIFIED_KNOWLEDGE_STATES = {"SUPPORTED", "CORROBORATED", "HIGH_CONFIDENCE"}
CLOSING_STATUSES = {"CLOSED", "ARCHIVED"}


def _node_exists(conn, label: str, node_id: str) -> bool:
    return fetch_one(conn.execute(f"MATCH (n:{label} {{id: $id}}) RETURN n.id AS id", {"id": node_id})) is not None


# ---- Investigations ---------------------------------------------------

@router.post("", response_model=Investigation, status_code=201)
def create_investigation(payload: InvestigationCreate) -> Investigation:
    conn = get_connection()
    inv_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    conn.execute(
        "CREATE (:Investigation {id: $id, title: $title, research_question: $rq, "
        "status: 'OPEN', created_at: $created_at, updated_at: $created_at})",
        {"id": inv_id, "title": payload.title, "rq": payload.research_question, "created_at": created_at},
    )
    return Investigation(id=inv_id, status="OPEN", created_at=created_at, updated_at=created_at, **payload.model_dump())


@router.get("", response_model=list[Investigation])
def list_investigations() -> list[Investigation]:
    conn = get_connection()
    result = conn.execute(f"MATCH (i:Investigation) RETURN {_INV_FIELDS} ORDER BY i.created_at")
    return [Investigation(**row) for row in fetch_all(result)]


@router.get("/{investigation_id}", response_model=Investigation)
def get_investigation(investigation_id: str) -> Investigation:
    conn = get_connection()
    result = conn.execute(f"MATCH (i:Investigation {{id: $id}}) RETURN {_INV_FIELDS}", {"id": investigation_id})
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return Investigation(**row)


@router.post("/{investigation_id}/transition", response_model=Investigation)
def transition_investigation(investigation_id: str, payload: InvestigationTransition) -> Investigation:
    conn = get_connection()
    current = get_investigation(investigation_id)
    allowed = INVESTIGATION_TRANSITIONS.get(current.status, ())
    if payload.to_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {current.status} to {payload.to_status}. Allowed: {list(allowed)}",
        )
    now = datetime.now(timezone.utc)
    conn.execute(
        "MATCH (i:Investigation {id: $id}) SET i.status = $status, i.updated_at = $now",
        {"id": investigation_id, "status": payload.to_status, "now": now},
    )
    if payload.to_status in CLOSING_STATUSES:
        _promote_verified_findings(conn, investigation_id)
    _notify_investigation_update(conn, investigation_id, current.status, payload.to_status)
    return get_investigation(investigation_id)


def _notify_investigation_update(conn, investigation_id: str, from_status: str, to_status: str) -> None:
    """Faz 7 — bir investigation'ın kendisi VEYA ona dahil edilmiş (INCLUDES/INVESTIGATES)
    entity/event'ler izleniyorsa, durum geçişi Intelligence Inbox'a düşer."""
    title = f"Investigation durumu değişti: {from_status} -> {to_status}"
    detail = {"investigation_id": investigation_id, "from_status": from_status, "to_status": to_status}
    notify_if_monitored(
        conn, target_type="Investigation", target_id=investigation_id,
        item_type="INVESTIGATION_UPDATE", title=title, detail=detail,
    )
    for row in fetch_all(conn.execute(
        "MATCH (i:Investigation {id: $id})-[:INCLUDES]->(e:Entity) RETURN e.id AS id", {"id": investigation_id}
    )):
        notify_if_monitored(
            conn, target_type="Entity", target_id=row["id"],
            item_type="INVESTIGATION_UPDATE", title=title, detail=detail,
        )
    for row in fetch_all(conn.execute(
        "MATCH (i:Investigation {id: $id})-[:INVESTIGATES]->(e:Event) RETURN e.id AS id", {"id": investigation_id}
    )):
        notify_if_monitored(
            conn, target_type="Event", target_id=row["id"],
            item_type="INVESTIGATION_UPDATE", title=title, detail=detail,
        )


def _promote_verified_findings(conn, investigation_id: str) -> list[str]:
    """Q17: Investigation -> Evaluation -> Validated Knowledge -> Long-Term Memory.
    Sadece VERIFIED_KNOWLEDGE_STATES'teki finding'ler VALIDATED_FINDING kazanır — geçici
    notlar/çürütülmüş hipotezlerin claim'leri Knowledge Graph'ta kalır (silinmez) ama
    "doğrulanmış" olarak işaretlenmez. İdempotent: zaten promote edilmiş claim'ler atlanır."""
    findings = fetch_all(
        conn.execute(
            "MATCH (i:Investigation {id: $id})-[:HAS_FINDING]->(c:Claim) "
            "RETURN c.id AS id, c.knowledge_state AS knowledge_state",
            {"id": investigation_id},
        )
    )
    already_promoted = {
        row["id"]
        for row in fetch_all(
            conn.execute(
                "MATCH (i:Investigation {id: $id})-[:VALIDATED_FINDING]->(c:Claim) RETURN c.id AS id",
                {"id": investigation_id},
            )
        )
    }
    now = datetime.now(timezone.utc)
    promoted: list[str] = []
    for row in findings:
        if row["id"] in already_promoted:
            continue
        if row["knowledge_state"] in VERIFIED_KNOWLEDGE_STATES:
            conn.execute(
                "MATCH (i:Investigation {id: $iid}), (c:Claim {id: $cid}) "
                "CREATE (i)-[:VALIDATED_FINDING {promoted_at: $now}]->(c)",
                {"iid": investigation_id, "cid": row["id"], "now": now},
            )
            promoted.append(row["id"])
    return promoted


@router.put("/{investigation_id}/entities/{entity_id}", status_code=204)
def include_entity(investigation_id: str, entity_id: str) -> None:
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    if not _node_exists(conn, "Entity", entity_id):
        raise HTTPException(status_code=404, detail="Entity not found")
    conn.execute(
        "MATCH (i:Investigation {id: $iid}), (e:Entity {id: $eid}) CREATE (i)-[:INCLUDES]->(e)",
        {"iid": investigation_id, "eid": entity_id},
    )


@router.put("/{investigation_id}/events/{event_id}", status_code=204)
def investigate_event(investigation_id: str, event_id: str) -> None:
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    if not _node_exists(conn, "Event", event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    conn.execute(
        "MATCH (i:Investigation {id: $iid}), (e:Event {id: $eid}) CREATE (i)-[:INVESTIGATES]->(e)",
        {"iid": investigation_id, "eid": event_id},
    )


@router.put("/{investigation_id}/findings/{claim_id}", status_code=204)
def add_finding(investigation_id: str, claim_id: str) -> None:
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    if not _node_exists(conn, "Claim", claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    conn.execute(
        "MATCH (i:Investigation {id: $iid}), (c:Claim {id: $cid}) CREATE (i)-[:HAS_FINDING]->(c)",
        {"iid": investigation_id, "cid": claim_id},
    )


@router.get("/{investigation_id}/findings")
def list_findings(investigation_id: str) -> list[dict]:
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    rows = fetch_all(
        conn.execute(
            "MATCH (i:Investigation {id: $id})-[:HAS_FINDING]->(c:Claim) "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence",
            {"id": investigation_id},
        )
    )
    validated_ids = {
        row["id"]
        for row in fetch_all(
            conn.execute(
                "MATCH (i:Investigation {id: $id})-[:VALIDATED_FINDING]->(c:Claim) RETURN c.id AS id",
                {"id": investigation_id},
            )
        )
    }
    for row in rows:
        row["validated"] = row["id"] in validated_ids
    return rows


# ---- Hypotheses ---------------------------------------------------

@router.post("/{investigation_id}/hypotheses", response_model=Hypothesis, status_code=201)
def create_hypothesis(investigation_id: str, payload: HypothesisCreate) -> Hypothesis:
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    hyp_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    conn.execute(
        "CREATE (:Hypothesis {id: $id, text: $text, status: 'PROPOSED', created_at: $created_at})",
        {"id": hyp_id, "text": payload.text, "created_at": created_at},
    )
    conn.execute(
        "MATCH (i:Investigation {id: $iid}), (h:Hypothesis {id: $hid}) CREATE (i)-[:HAS_HYPOTHESIS]->(h)",
        {"iid": investigation_id, "hid": hyp_id},
    )
    return Hypothesis(id=hyp_id, status="PROPOSED", created_at=created_at, **payload.model_dump())


@router.get("/{investigation_id}/hypotheses", response_model=list[Hypothesis])
def list_hypotheses(investigation_id: str) -> list[Hypothesis]:
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    result = conn.execute(
        f"MATCH (i:Investigation {{id: $id}})-[:HAS_HYPOTHESIS]->(h:Hypothesis) "
        f"RETURN {_HYP_FIELDS} ORDER BY h.created_at",
        {"id": investigation_id},
    )
    return [Hypothesis(**row) for row in fetch_all(result)]


@hypotheses_router.get("/{hypothesis_id}", response_model=Hypothesis)
def get_hypothesis(hypothesis_id: str) -> Hypothesis:
    conn = get_connection()
    result = conn.execute(f"MATCH (h:Hypothesis {{id: $id}}) RETURN {_HYP_FIELDS}", {"id": hypothesis_id})
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return Hypothesis(**row)


def _recompute_hypothesis_status(conn, hypothesis_id: str) -> str:
    stances = fetch_all(
        conn.execute(
            "MATCH (ev:Evidence)-[r:HYPOTHESIS_EVIDENCE]->(h:Hypothesis {id: $id}) RETURN r.stance AS stance",
            {"id": hypothesis_id},
        )
    )
    supports = sum(1 for s in stances if s["stance"] == "SUPPORTS")
    weakens = sum(1 for s in stances if s["stance"] == "WEAKENS")
    refutes = sum(1 for s in stances if s["stance"] == "REFUTES")

    if refutes > 0:
        status = "REFUTED"
    elif supports == 0 and weakens == 0:
        status = "PROPOSED"
    elif supports > weakens:
        status = "SUPPORTED"
    elif weakens > supports:
        status = "WEAKENED"
    else:
        status = "UNRESOLVED"

    conn.execute("MATCH (h:Hypothesis {id: $id}) SET h.status = $status", {"id": hypothesis_id, "status": status})
    return status


@hypotheses_router.put("/{hypothesis_id}/evidence", response_model=Hypothesis)
def link_hypothesis_evidence(hypothesis_id: str, payload: HypothesisEvidenceLink) -> Hypothesis:
    conn = get_connection()
    if not _node_exists(conn, "Hypothesis", hypothesis_id):
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    if not _node_exists(conn, "Evidence", payload.evidence_id):
        raise HTTPException(status_code=404, detail="Evidence not found")
    if payload.stance not in ("SUPPORTS", "WEAKENS", "REFUTES"):
        raise HTTPException(status_code=422, detail="stance must be SUPPORTS, WEAKENS or REFUTES")
    conn.execute(
        "MATCH (ev:Evidence {id: $eid}), (h:Hypothesis {id: $hid}) "
        "CREATE (ev)-[:HYPOTHESIS_EVIDENCE {stance: $stance}]->(h)",
        {"eid": payload.evidence_id, "hid": hypothesis_id, "stance": payload.stance},
    )
    _recompute_hypothesis_status(conn, hypothesis_id)
    return get_hypothesis(hypothesis_id)
