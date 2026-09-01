import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import fetch_all, fetch_one, get_connection
from app.models import Source, SourceCreate

router = APIRouter(prefix="/sources", tags=["sources"])

_FIELDS = (
    "s.id AS id, s.name AS name, s.source_type AS source_type, s.url AS url, "
    "s.reliability AS reliability, s.created_at AS created_at"
)


@router.post("", response_model=Source, status_code=201)
def create_source(payload: SourceCreate) -> Source:
    conn = get_connection()
    source_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    conn.execute(
        "CREATE (:Source {id: $id, name: $name, source_type: $source_type, url: $url, "
        "reliability: $reliability, created_at: $created_at})",
        {
            "id": source_id,
            "name": payload.name,
            "source_type": payload.source_type,
            "url": payload.url,
            "reliability": payload.reliability,
            "created_at": created_at,
        },
    )
    return Source(id=source_id, created_at=created_at, **payload.model_dump())


@router.get("", response_model=list[Source])
def list_sources() -> list[Source]:
    conn = get_connection()
    result = conn.execute(f"MATCH (s:Source) RETURN {_FIELDS} ORDER BY s.created_at")
    return [Source(**row) for row in fetch_all(result)]


@router.get("/{source_id}", response_model=Source)
def get_source(source_id: str) -> Source:
    conn = get_connection()
    result = conn.execute(f"MATCH (s:Source {{id: $id}}) RETURN {_FIELDS}", {"id": source_id})
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return Source(**row)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: str) -> None:
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (s:Source {id: $id}) RETURN s.id AS id", {"id": source_id})) is None:
        raise HTTPException(status_code=404, detail="Source not found")
    conn.execute("MATCH (s:Source {id: $id}) DETACH DELETE s", {"id": source_id})
