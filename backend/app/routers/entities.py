import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import fetch_all, fetch_one, get_connection
from app.dedup import find_candidates, pair_score
from app.entityrelations import relation_candidates
from app.models import (
    Entity,
    EntityCreate,
    EntityRelationCreate,
    RelationCandidate,
    SameAsSuggestRequest,
)
from app.recall import entity_recall
from app.vault import safe_render_vault

router = APIRouter(prefix="/entities", tags=["entities"])
same_as_router = APIRouter(prefix="/entities/same-as", tags=["same-as"])

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
    safe_render_vault(conn)
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
    safe_render_vault(conn)
    return get_entity(entity_id)


@router.delete("/{entity_id}", status_code=204)
def delete_entity(entity_id: str) -> None:
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    conn.execute("MATCH (e:Entity {id: $id}) DETACH DELETE e", {"id": entity_id})
    safe_render_vault(conn)


# ---- ENTITY_RELATION (Entity <-> Entity) ---------------------------------------------------


@router.post("/{entity_id}/relations", status_code=201)
def create_entity_relation(entity_id: str, payload: EntityRelationCreate) -> dict:
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": payload.to_entity_id})) is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {payload.to_entity_id}")
    if entity_id == payload.to_entity_id:
        raise HTTPException(status_code=422, detail="Bir entity kendisiyle ilişkilendirilemez")
    now = datetime.now(timezone.utc)
    conn.execute(
        "MATCH (a:Entity {id: $aid}), (b:Entity {id: $bid}) "
        "CREATE (a)-[:ENTITY_RELATION {relation_type: $rt, confidence: $conf, "
        "valid_from: $now, valid_to: NULL, status: 'ACTIVE'}]->(b)",
        {"aid": entity_id, "bid": payload.to_entity_id, "rt": payload.relation_type, "conf": payload.confidence, "now": now},
    )
    safe_render_vault(conn)
    return {
        "from_entity_id": entity_id,
        "to_entity_id": payload.to_entity_id,
        "relation_type": payload.relation_type,
        "confidence": payload.confidence,
        "valid_from": now,
        "valid_to": None,
        "status": "ACTIVE",
    }


@router.get("/{entity_id}/relations")
def list_entity_relations(entity_id: str) -> list[dict]:
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    outgoing = fetch_all(
        conn.execute(
            "MATCH (e:Entity {id: $id})-[r:ENTITY_RELATION]->(other:Entity) WHERE r.status <> 'SUPERSEDED' "
            "RETURN other.id AS entity_id, other.name AS name, r.relation_type AS relation_type, "
            "r.confidence AS confidence, r.status AS status, r.valid_from AS valid_from, 'OUTGOING' AS direction",
            {"id": entity_id},
        )
    )
    incoming = fetch_all(
        conn.execute(
            "MATCH (other:Entity)-[r:ENTITY_RELATION]->(e:Entity {id: $id}) WHERE r.status <> 'SUPERSEDED' "
            "RETURN other.id AS entity_id, other.name AS name, r.relation_type AS relation_type, "
            "r.confidence AS confidence, r.status AS status, r.valid_from AS valid_from, 'INCOMING' AS direction",
            {"id": entity_id},
        )
    )
    return outgoing + incoming


@router.get("/{entity_id}/relation-candidates", response_model=list[RelationCandidate])
def list_relation_candidates(entity_id: str) -> list[RelationCandidate]:
    """Faz 19 — bu entity ile ilişkili OLABİLECEK entity'ler (bkz. app/entityrelations.py).

    Öneridir: sistem "bu ikisi birbiriyle ilgili" der, ilişkinin TÜRÜNÜ kullanıcı yazar.
    Zaten ACTIVE ilişkisi olanlar ve CONFIRMED SAME_AS grubundakiler listede yer almaz."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return [RelationCandidate(**c) for c in relation_candidates(conn, entity_id)]


@router.delete("/{entity_id}/relations/{to_entity_id}", status_code=204)
def delete_entity_relation(entity_id: str, to_entity_id: str, relation_type: str) -> None:
    """History Is Immutable: kenar fiziksel silinmez, ACTIVE/CONTRADICTED/SUPERSEDED
    üçlüsü (schema.py'nin öngördüğü) kullanılarak SUPERSEDED'e çekilir — Claim.supersede
    ile aynı disiplin."""
    conn = get_connection()
    now = datetime.now(timezone.utc)
    result = fetch_one(
        conn.execute(
            "MATCH (a:Entity {id: $aid})-[r:ENTITY_RELATION {relation_type: $rt}]->(b:Entity {id: $bid}) "
            "WHERE r.status = 'ACTIVE' SET r.status = 'SUPERSEDED', r.valid_to = $now RETURN r.status AS status",
            {"aid": entity_id, "bid": to_entity_id, "rt": relation_type, "now": now},
        )
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Aktif ENTITY_RELATION bulunamadı")
    safe_render_vault(conn)


# ---- SAME_AS (entity merge/dedup önerisi, Q7 — asla otomatik merge yok) --------------------


@router.get("/{entity_id}/same-as/candidates")
def same_as_candidates(entity_id: str) -> list[dict]:
    """Salt okunur: hiçbir şey yazmaz, sadece aday hesaplar."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return [c.__dict__ for c in find_candidates(conn, entity_id)]


@router.post("/{entity_id}/same-as", status_code=201)
def suggest_same_as(entity_id: str, payload: SameAsSuggestRequest) -> dict:
    """Sadece PENDING öneri yaratır — skor ne olursa olsun asla CONFIRMED yaratmaz (Q7)."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": payload.to_entity_id})) is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {payload.to_entity_id}")
    if entity_id == payload.to_entity_id:
        raise HTTPException(status_code=422, detail="Bir entity kendisiyle eşleşemez")
    existing = fetch_one(
        conn.execute(
            "MATCH (a:Entity {id: $a})-[r:SAME_AS]->(b:Entity {id: $b}) RETURN r.status AS status",
            {"a": entity_id, "b": payload.to_entity_id},
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Bu çift için zaten bir SAME_AS kaydı var (status={existing['status']})")
    score = pair_score(conn, entity_id, payload.to_entity_id)
    now = datetime.now(timezone.utc)
    conn.execute(
        "MATCH (a:Entity {id: $a}), (b:Entity {id: $b}) "
        "CREATE (a)-[:SAME_AS {confidence: $score, status: 'PENDING', created_at: $now}]->(b) "
        "CREATE (b)-[:SAME_AS {confidence: $score, status: 'PENDING', created_at: $now}]->(a)",
        {"a": entity_id, "b": payload.to_entity_id, "score": score, "now": now},
    )
    safe_render_vault(conn)
    return {"from_entity_id": entity_id, "to_entity_id": payload.to_entity_id, "confidence": score, "status": "PENDING"}


def _resolve_same_as(conn, a_id: str, b_id: str, status: str) -> bool:
    found = False
    for x, y in ((a_id, b_id), (b_id, a_id)):
        result = fetch_one(
            conn.execute(
                "MATCH (a:Entity {id: $a})-[r:SAME_AS]->(b:Entity {id: $b}) WHERE r.status = 'PENDING' "
                "SET r.status = $status RETURN r.status AS status",
                {"a": x, "b": y, "status": status},
            )
        )
        found = found or result is not None
    return found


@same_as_router.get("/pending")
def list_pending_same_as() -> list[dict]:
    conn = get_connection()
    return fetch_all(
        conn.execute(
            "MATCH (a:Entity)-[r:SAME_AS]->(b:Entity) WHERE r.status = 'PENDING' AND a.id < b.id "
            "RETURN a.id AS entity_a_id, a.name AS entity_a_name, a.entity_type AS entity_a_type, "
            "b.id AS entity_b_id, b.name AS entity_b_name, b.entity_type AS entity_b_type, "
            "r.confidence AS confidence, r.created_at AS created_at ORDER BY r.created_at"
        )
    )


@same_as_router.post("/{from_entity_id}/{to_entity_id}/confirm")
def confirm_same_as(from_entity_id: str, to_entity_id: str) -> dict:
    """Q7/Human Remains In Control: CONFIRMED'e giden TEK yol — kullanıcının açıkça
    tıkladığı bu uç, hiçbir arka plan işi ya da otomatik akış buraya ulaşmaz. Entity
    node'ları FİZİKSEL OLARAK BİRLEŞTİRİLMEZ/SİLİNMEZ (History Is Immutable) — sadece
    kenar durumu CONFIRMED'e çekilir."""
    conn = get_connection()
    if not _resolve_same_as(conn, from_entity_id, to_entity_id, "CONFIRMED"):
        raise HTTPException(status_code=404, detail="PENDING bir SAME_AS önerisi bulunamadı")
    safe_render_vault(conn)
    return {"from_entity_id": from_entity_id, "to_entity_id": to_entity_id, "status": "CONFIRMED"}


@same_as_router.post("/{from_entity_id}/{to_entity_id}/reject")
def reject_same_as(from_entity_id: str, to_entity_id: str) -> dict:
    conn = get_connection()
    if not _resolve_same_as(conn, from_entity_id, to_entity_id, "REJECTED"):
        raise HTTPException(status_code=404, detail="PENDING bir SAME_AS önerisi bulunamadı")
    safe_render_vault(conn)
    return {"from_entity_id": from_entity_id, "to_entity_id": to_entity_id, "status": "REJECTED"}
