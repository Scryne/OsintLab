import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import fetch_all, fetch_one, get_connection
from app.lineage import detect_derivation, resolve_independent_root
from app.models import LineageDetectRequest, Source, SourceCreate
from app.routers.claims import _recompute_and_store

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


def _claim_text_source_created(conn, claim_id: str) -> dict:
    row = fetch_one(
        conn.execute(
            "MATCH (s:Source)-[:ASSERTS]->(c:Claim {id: $id}) "
            "RETURN c.text AS text, c.created_at AS created_at, s.id AS source_id",
            {"id": claim_id},
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Claim not found or has no asserting Source: {claim_id}")
    return row


@router.post("/lineage/detect")
def detect_lineage(payload: LineageDetectRequest) -> dict:
    """Q6: iki claim'in metnini (near-duplicate shingle containment) ve ajans-atıf sinyalini
    karşılaştırır. Türetilmiş bulunursa, daha SONRA oluşturulan claim'in kaynağından daha
    ÖNCE oluşturulana doğru bir DERIVED_FROM ilişkisi kurulur (Site B -> Site A -> Agency
    zinciri) — bkz. app/lineage.py karar gerekçesi."""
    conn = get_connection()
    claim_a = _claim_text_source_created(conn, payload.claim_id_a)
    claim_b = _claim_text_source_created(conn, payload.claim_id_b)

    detection = detect_derivation(claim_a["text"], claim_b["text"])

    result = {
        "similarity": detection.similarity,
        "shared_agencies": detection.shared_agencies,
        "is_derived": detection.is_derived,
        "method": detection.method,
        "edge_created": False,
    }

    if not detection.is_derived:
        return result

    if claim_a["source_id"] == claim_b["source_id"]:
        result["note"] = "Aynı Source — lineage ilişkisi gereksiz."
        return result

    # Daha sonra oluşturulan (downstream) -> daha önce oluşturulan (upstream).
    if claim_a["created_at"] <= claim_b["created_at"]:
        upstream_id, downstream_id = claim_a["source_id"], claim_b["source_id"]
    else:
        upstream_id, downstream_id = claim_b["source_id"], claim_a["source_id"]

    existing = fetch_one(
        conn.execute(
            "MATCH (:Source {id: $down})-[r:DERIVED_FROM]->(:Source {id: $up}) RETURN r.method AS method",
            {"down": downstream_id, "up": upstream_id},
        )
    )
    if existing is not None:
        result["note"] = "DERIVED_FROM ilişkisi zaten mevcut."
        result["edge_created"] = False
        result["downstream_source_id"] = downstream_id
        result["upstream_source_id"] = upstream_id
        return result

    now = datetime.now(timezone.utc)
    conn.execute(
        "MATCH (down:Source {id: $down}), (up:Source {id: $up}) "
        "CREATE (down)-[:DERIVED_FROM {method: $method, similarity: $similarity, "
        "shared_agencies: $agencies, detected_at: $now}]->(up)",
        {
            "down": downstream_id,
            "up": upstream_id,
            "method": detection.method,
            "similarity": detection.similarity,
            "agencies": ",".join(detection.shared_agencies),
            "now": now,
        },
    )

    affected = fetch_all(
        conn.execute(
            "MATCH (s:Source)-[:ASSERTS]->(c:Claim) WHERE s.id IN [$down, $up] "
            "OPTIONAL MATCH (c)-[:CORROBORATES]->(other:Claim) "
            "RETURN DISTINCT c.id AS id, other.id AS other_id",
            {"down": downstream_id, "up": upstream_id},
        )
    )
    affected_ids = {row["id"] for row in affected} | {row["other_id"] for row in affected if row["other_id"]}
    for cid in affected_ids:
        _recompute_and_store(conn, cid)

    result["edge_created"] = True
    result["downstream_source_id"] = downstream_id
    result["upstream_source_id"] = upstream_id
    result["recomputed_claim_ids"] = sorted(affected_ids)
    return result


@router.get("/{source_id}/lineage")
def get_lineage(source_id: str) -> dict:
    """Bir Source'un tam lineage zincirini döner: ancestors (bu source'un türediği kaynaklar,
    kökten uzağa doğru sıralı) ve descendants (bu source'tan türeyenler)."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (s:Source {id: $id}) RETURN s.id AS id", {"id": source_id})) is None:
        raise HTTPException(status_code=404, detail="Source not found")

    ancestors = fetch_all(
        conn.execute(
            "MATCH (s:Source {id: $id})-[:DERIVED_FROM*1..10]->(a:Source) "
            "RETURN DISTINCT a.id AS id, a.name AS name, a.url AS url",
            {"id": source_id},
        )
    )
    descendants = fetch_all(
        conn.execute(
            "MATCH (d:Source)-[:DERIVED_FROM*1..10]->(s:Source {id: $id}) "
            "RETURN DISTINCT d.id AS id, d.name AS name, d.url AS url",
            {"id": source_id},
        )
    )
    return {
        "source_id": source_id,
        "ancestors": ancestors,
        "descendants": descendants,
        "independent_root_id": resolve_independent_root(conn, source_id),
    }
