import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import fetch_all, fetch_one, get_connection
from app.models import Event, EventCreate, InvolvedInLink
from app.monitoring import notify_if_monitored
from app.recall import event_recall
from app.vault import safe_render_vault

router = APIRouter(prefix="/events", tags=["events"])


def _source_exists(conn, source_id: str) -> bool:
    return fetch_one(conn.execute("MATCH (s:Source {id: $id}) RETURN s.id AS id", {"id": source_id})) is not None

_FIELDS = (
    "e.id AS id, e.title AS title, e.event_type AS event_type, e.occurred_at AS occurred_at, "
    "e.location AS location, e.knowledge_state AS knowledge_state, e.confidence AS confidence, "
    "e.created_at AS created_at"
)


@router.post("", response_model=Event, status_code=201)
def create_event(payload: EventCreate) -> Event:
    conn = get_connection()
    event_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    # Yeni oluşturulan bir Event'in henüz hiç claim/evidence'ı yok — Q1/Q8: eşiği geçmemiş
    # bilgi düşük confidence ile başlar, OBSERVED durumunda.
    conn.execute(
        "CREATE (:Event {id: $id, title: $title, event_type: $event_type, "
        "occurred_at: $occurred_at, location: $location, knowledge_state: 'OBSERVED', "
        "confidence: 0.0, created_at: $created_at})",
        {
            "id": event_id,
            "title": payload.title,
            "event_type": payload.event_type,
            "occurred_at": payload.occurred_at,
            "location": payload.location,
            "created_at": created_at,
        },
    )
    safe_render_vault(conn)
    return Event(id=event_id, knowledge_state="OBSERVED", confidence=0.0, created_at=created_at, **payload.model_dump())


@router.get("", response_model=list[Event])
def list_events() -> list[Event]:
    conn = get_connection()
    result = conn.execute(f"MATCH (e:Event) RETURN {_FIELDS} ORDER BY e.created_at")
    return [Event(**row) for row in fetch_all(result)]


@router.get("/{event_id}", response_model=Event)
def get_event(event_id: str) -> Event:
    conn = get_connection()
    result = conn.execute(f"MATCH (e:Event {{id: $id}}) RETURN {_FIELDS}", {"id": event_id})
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return Event(**row)


@router.put("/{event_id}/entities/{entity_id}", status_code=204)
def link_entity(event_id: str, entity_id: str, payload: InvolvedInLink) -> None:
    """Entity <-INVOLVED_IN- Event ilişkisini kurar (recall.py'nin entity_recall/event_recall'ı
    zaten okuyordu ama yazan bir uç eksikti). Faz 7: hedef Entity izleniyorsa, yeni bir
    event'e karışması Intelligence Inbox'a NEW_EVENT olarak düşer (madde 22-23)."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    if fetch_one(conn.execute("MATCH (e:Event {id: $id}) RETURN e.id AS id", {"id": event_id})) is None:
        raise HTTPException(status_code=404, detail="Event not found")
    conn.execute(
        "MATCH (e:Entity {id: $eid}), (ev:Event {id: $evid}) CREATE (e)-[:INVOLVED_IN {role: $role}]->(ev)",
        {"eid": entity_id, "evid": event_id, "role": payload.role},
    )
    event = get_event(event_id)
    notify_if_monitored(
        conn,
        target_type="Entity",
        target_id=entity_id,
        item_type="NEW_EVENT",
        title=f"Yeni bir event'e karıştı: {event.title}",
        detail={"event_id": event_id, "role": payload.role},
        confidence=event.confidence,
        is_novel=True,
    )
    safe_render_vault(conn)


@router.put("/{event_id}/sources/{source_id}", status_code=204)
def link_source(event_id: str, source_id: str) -> None:
    """Event <-REPORTED_BY- Source: bu event'i hangi kaynaklar bildirdi (provenance,
    ASSERTS'ten bağımsız — bir Source bir Claim'e hiç ASSERTS yapmadan da bir Event'i
    'raporlamış' olabilir, ör. sadece haberi geçen ama iddia üretmeyen bir kaynak)."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Event {id: $id}) RETURN e.id AS id", {"id": event_id})) is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if not _source_exists(conn, source_id):
        raise HTTPException(status_code=404, detail="Source not found")
    conn.execute(
        "MATCH (ev:Event {id: $evid}), (s:Source {id: $sid}) CREATE (ev)-[:REPORTED_BY]->(s)",
        {"evid": event_id, "sid": source_id},
    )
    safe_render_vault(conn)


@router.get("/{event_id}/recall")
def recall_event(event_id: str) -> dict:
    """OSINT Brain — Memory Recall: bu event hakkında sistemin şu an ne bildiği."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Event {id: $id}) RETURN e.id AS id", {"id": event_id})) is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"event_id": event_id, **event_recall(conn, event_id)}


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: str) -> None:
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Event {id: $id}) RETURN e.id AS id", {"id": event_id})) is None:
        raise HTTPException(status_code=404, detail="Event not found")
    conn.execute("MATCH (e:Event {id: $id}) DETACH DELETE e", {"id": event_id})
    safe_render_vault(conn)
