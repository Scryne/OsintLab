import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import fetch_all, fetch_one, get_connection
from app.models import Event, EventCreate

router = APIRouter(prefix="/events", tags=["events"])

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


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: str) -> None:
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Event {id: $id}) RETURN e.id AS id", {"id": event_id})) is None:
        raise HTTPException(status_code=404, detail="Event not found")
    conn.execute("MATCH (e:Event {id: $id}) DETACH DELETE e", {"id": event_id})
