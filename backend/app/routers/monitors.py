import json
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from app.db import fetch_all, fetch_one, get_connection
from app.models import (
    INBOX_ITEM_STATUSES,
    MONITOR_TARGET_TYPES,
    PRIORITY_LEVELS,
    InboxItem,
    InboxSettings,
    InboxStatusUpdate,
    Monitor,
    MonitorCreate,
)
from app.monitoring import load_inbox_settings, priority_at_least, save_inbox_settings
from app.vault import safe_render_inbox_only, safe_render_vault

router = APIRouter(tags=["monitoring"])

_MONITOR_FIELDS = (
    "m.id AS id, m.target_type AS target_type, m.target_id AS target_id, "
    "m.label AS label, m.active AS active, m.created_at AS created_at"
)
_INBOX_FIELDS = (
    "n.id AS id, n.item_type AS item_type, n.priority AS priority, n.title AS title, "
    "n.detail AS detail, n.target_type AS target_type, n.target_id AS target_id, "
    "n.monitor_id AS monitor_id, n.status AS status, n.created_at AS created_at, "
    "n.actioned_at AS actioned_at"
)


def _row_to_inbox_item(row: dict) -> InboxItem:
    row = dict(row)
    row["detail"] = json.loads(row["detail"]) if row["detail"] else {}
    return InboxItem(**row)


# ---- Monitors -----------------------------------------------------------

@router.post("/monitors", response_model=Monitor, status_code=201)
def create_monitor(payload: MonitorCreate) -> Monitor:
    if payload.target_type not in MONITOR_TARGET_TYPES:
        raise HTTPException(status_code=422, detail=f"target_type must be one of {MONITOR_TARGET_TYPES}")
    conn = get_connection()
    if fetch_one(conn.execute(
        f"MATCH (t:{payload.target_type} {{id: $id}}) RETURN t.id AS id", {"id": payload.target_id}
    )) is None:
        raise HTTPException(status_code=404, detail=f"{payload.target_type} not found: {payload.target_id}")

    existing = fetch_one(
        conn.execute(
            "MATCH (m:Monitor {target_type: $tt, target_id: $tid, active: true}) RETURN m.id AS id",
            {"tt": payload.target_type, "tid": payload.target_id},
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Bu hedef için zaten aktif bir Monitor var")

    monitor_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    conn.execute(
        "CREATE (:Monitor {id: $id, target_type: $tt, target_id: $tid, label: $label, "
        "active: true, created_at: $now})",
        {"id": monitor_id, "tt": payload.target_type, "tid": payload.target_id, "label": payload.label, "now": created_at},
    )
    safe_render_vault(conn)
    return Monitor(id=monitor_id, active=True, created_at=created_at, **payload.model_dump())


@router.get("/monitors", response_model=list[Monitor])
def list_monitors(active: bool | None = None) -> list[Monitor]:
    conn = get_connection()
    if active is None:
        result = conn.execute(f"MATCH (m:Monitor) RETURN {_MONITOR_FIELDS} ORDER BY m.created_at")
    else:
        result = conn.execute(
            f"MATCH (m:Monitor {{active: $active}}) RETURN {_MONITOR_FIELDS} ORDER BY m.created_at",
            {"active": active},
        )
    return [Monitor(**row) for row in fetch_all(result)]


@router.delete("/monitors/{monitor_id}", status_code=204)
def delete_monitor(monitor_id: str) -> None:
    """Fiziksel silme değil — active=false (Q14/audit-trail ruhuyla tutarlı: geçmiş Inbox
    öğeleri hangi Monitor'den geldiğini göstermeye devam edebilsin)."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (m:Monitor {id: $id}) RETURN m.id AS id", {"id": monitor_id})) is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    conn.execute("MATCH (m:Monitor {id: $id}) SET m.active = false", {"id": monitor_id})
    safe_render_vault(conn)


# ---- Intelligence Inbox (madde 27, Q13, Q14) -----------------------------

@router.get("/inbox", response_model=list[InboxItem])
def list_inbox(
    min_priority: str | None = Query(None, description="Verilmezse kayıtlı ayar (Q13) kullanılır"),
    status: str | None = None,
) -> list[InboxItem]:
    conn = get_connection()
    threshold = min_priority or load_inbox_settings().get("min_priority", "INFO")
    if threshold not in PRIORITY_LEVELS:
        raise HTTPException(status_code=422, detail=f"min_priority must be one of {PRIORITY_LEVELS}")
    if status is not None and status not in INBOX_ITEM_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {INBOX_ITEM_STATUSES}")

    if status is None:
        result = conn.execute(f"MATCH (n:InboxItem) RETURN {_INBOX_FIELDS} ORDER BY n.created_at DESC")
    else:
        result = conn.execute(
            f"MATCH (n:InboxItem {{status: $status}}) RETURN {_INBOX_FIELDS} ORDER BY n.created_at DESC",
            {"status": status},
        )
    items = [_row_to_inbox_item(row) for row in fetch_all(result)]
    return [item for item in items if priority_at_least(item.priority, threshold)]


@router.get("/inbox/settings", response_model=InboxSettings)
def get_inbox_settings() -> InboxSettings:
    return InboxSettings(**load_inbox_settings())


@router.put("/inbox/settings", response_model=InboxSettings)
def update_inbox_settings(payload: InboxSettings) -> InboxSettings:
    if payload.min_priority not in PRIORITY_LEVELS:
        raise HTTPException(status_code=422, detail=f"min_priority must be one of {PRIORITY_LEVELS}")
    save_inbox_settings(payload.model_dump())
    return payload


@router.patch("/inbox/{item_id}", response_model=InboxItem)
def update_inbox_item(item_id: str, payload: InboxStatusUpdate) -> InboxItem:
    """Q14: kullanıcı davranışı (Ignore/Confirm/Reject/Investigate/Follow) loglanır — v1'de
    prioritization algoritmasını otomatik ETKİLEMEZ, sadece audit trail için tutulur."""
    if payload.status not in INBOX_ITEM_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {INBOX_ITEM_STATUSES}")
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (n:InboxItem {id: $id}) RETURN n.id AS id", {"id": item_id})) is None:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    now = datetime.now(timezone.utc)
    conn.execute(
        "MATCH (n:InboxItem {id: $id}) SET n.status = $status, n.actioned_at = $now",
        {"id": item_id, "status": payload.status, "now": now},
    )
    row = fetch_one(conn.execute(f"MATCH (n:InboxItem {{id: $id}}) RETURN {_INBOX_FIELDS}", {"id": item_id}))
    safe_render_inbox_only(conn)
    return _row_to_inbox_item(row)


# ---- Intelligence Diff (Q10/Q11, madde 11) -------------------------------

@router.get("/intelligence/diff")
def intelligence_diff(
    days: int = Query(30, ge=1, le=3650, description="Kaç gün öncesinden itibaren"),
    since: datetime | None = Query(None, description="Verilirse days yerine bu zaman kullanılır"),
) -> dict:
    """Q10: World State on-demand hesaplanır (materialize edilmez) — bu uç iki 'an' arasındaki
    farkı (WORLD STATE A -> DIFF -> WORLD STATE B) anlık sorgularla üretir. Q11: kapsam hepsi
    birden — entity/event/source/claim/confidence/contradiction/investigation/relationship."""
    conn = get_connection()
    since_ts = since or (datetime.now(timezone.utc) - timedelta(days=days))
    until_ts = datetime.now(timezone.utc)

    def q(cypher: str, **params) -> list[dict]:
        return fetch_all(conn.execute(cypher, {"since": since_ts, **params}))

    new_entities = q(
        "MATCH (e:Entity) WHERE e.created_at >= $since "
        "RETURN e.id AS id, e.name AS name, e.entity_type AS entity_type ORDER BY e.created_at"
    )
    new_events = q(
        "MATCH (e:Event) WHERE e.created_at >= $since "
        "RETURN e.id AS id, e.title AS title, e.event_type AS event_type ORDER BY e.created_at"
    )
    new_sources = q(
        "MATCH (s:Source) WHERE s.created_at >= $since "
        "RETURN s.id AS id, s.name AS name, s.url AS url ORDER BY s.created_at"
    )
    new_investigations = q(
        "MATCH (i:Investigation) WHERE i.created_at >= $since "
        "RETURN i.id AS id, i.title AS title, i.status AS status ORDER BY i.created_at"
    )
    new_claims = q(
        "MATCH (c:Claim) WHERE c.created_at >= $since "
        "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
        "c.confidence AS confidence ORDER BY c.created_at"
    )
    claims_changed = q(
        "MATCH (c:Claim) WHERE c.updated_at >= $since AND c.created_at < $since "
        "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
        "c.confidence AS confidence ORDER BY c.updated_at"
    )
    new_contradictions = q(
        "MATCH (a:Claim)-[r:CLAIM_CONTRADICTS]->(b:Claim) WHERE r.detected_at >= $since "
        "RETURN a.id AS claim_a, b.id AS claim_b, r.status AS status, r.detected_at AS detected_at "
        "ORDER BY r.detected_at"
    )
    investigation_updates = q(
        "MATCH (i:Investigation) WHERE i.updated_at >= $since AND i.created_at < $since "
        "RETURN i.id AS id, i.title AS title, i.status AS status ORDER BY i.updated_at"
    )
    new_relationships = q(
        "MATCH (a:Entity)-[r:ENTITY_RELATION]->(b:Entity) WHERE r.valid_from >= $since "
        "RETURN a.id AS from_entity, b.id AS to_entity, r.relation_type AS relation_type "
        "ORDER BY r.valid_from"
    )
    new_validated_findings = q(
        "MATCH (i:Investigation)-[r:VALIDATED_FINDING]->(c:Claim) WHERE r.promoted_at >= $since "
        "RETURN i.id AS investigation_id, c.id AS claim_id, r.promoted_at AS promoted_at "
        "ORDER BY r.promoted_at"
    )

    return {
        "since": since_ts,
        "until": until_ts,
        "new_entities": new_entities,
        "new_events": new_events,
        "new_sources": new_sources,
        "new_investigations": new_investigations,
        "new_claims": new_claims,
        "claims_changed": claims_changed,
        "new_contradictions": new_contradictions,
        "investigation_updates": investigation_updates,
        "new_relationships": new_relationships,
        "new_validated_findings": new_validated_findings,
    }
