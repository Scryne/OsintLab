import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import fetch_all, fetch_one, get_connection
from app.models import Entity, EntityCreate
from app.recall import entity_recall

router = APIRouter(prefix="/entities", tags=["entities"])

_FIELDS = "e.id AS id, e.entity_type AS entity_type, e.name AS name, e.aliases AS aliases, e.created_at AS created_at"


@router.post("", response_model=Entity, status_code=201)
def create_entity(payload: EntityCreate) -> Entity:
    conn = get_connection()
    entity_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    conn.execute(
        "CREATE (:Entity {id: $id, entity_type: $entity_type, name: $name, "
        "aliases: $aliases, created_at: $created_at})",
        {
            "id": entity_id,
            "entity_type": payload.entity_type,
            "name": payload.name,
            "aliases": payload.aliases,
            "created_at": created_at,
        },
    )
    return Entity(id=entity_id, created_at=created_at, **payload.model_dump())


@router.get("", response_model=list[Entity])
def list_entities(entity_type: str | None = None) -> list[Entity]:
    conn = get_connection()
    if entity_type:
        result = conn.execute(
            f"MATCH (e:Entity {{entity_type: $entity_type}}) RETURN {_FIELDS} ORDER BY e.created_at",
            {"entity_type": entity_type},
        )
    else:
        result = conn.execute(f"MATCH (e:Entity) RETURN {_FIELDS} ORDER BY e.created_at")
    return [Entity(**row) for row in fetch_all(result)]


@router.get("/{entity_id}", response_model=Entity)
def get_entity(entity_id: str) -> Entity:
    conn = get_connection()
    result = conn.execute(f"MATCH (e:Entity {{id: $id}}) RETURN {_FIELDS}", {"id": entity_id})
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return Entity(**row)


@router.get("/{entity_id}/recall")
def recall_entity(entity_id: str) -> dict:
    """OSINT Brain — Memory Recall: bu entity hakkında sistemin şu an ne bildiği."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {"entity_id": entity_id, **entity_recall(conn, entity_id)}


@router.patch("/{entity_id}", response_model=Entity)
def update_entity(entity_id: str, payload: EntityCreate) -> Entity:
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    conn.execute(
        "MATCH (e:Entity {id: $id}) SET e.entity_type = $entity_type, "
        "e.name = $name, e.aliases = $aliases",
        {
            "id": entity_id,
            "entity_type": payload.entity_type,
            "name": payload.name,
            "aliases": payload.aliases,
        },
    )
    return get_entity(entity_id)


@router.delete("/{entity_id}", status_code=204)
def delete_entity(entity_id: str) -> None:
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    conn.execute("MATCH (e:Entity {id: $id}) DETACH DELETE e", {"id": entity_id})
