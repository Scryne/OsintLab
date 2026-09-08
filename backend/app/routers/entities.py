import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.db import fetch_all, fetch_one, get_connection
from app.dedup import find_candidates, pair_score
from app.entityextract import entity_candidates
from app.entityrelations import entity_graph, relation_candidates, relation_pair_candidates
from app.models import (
    Entity,
    EntityCandidateDecisionResult,
    EntityCandidateDismiss,
    EntityCandidatePromote,
    EntityCreate,
    EntityRelationCreate,
    EntityGraph,
    ExtractedEntityCandidate,
    RelationBatch,
    RelationBatchResult,
    RelationCandidate,
    RelationPairCandidate,
    SameAsSuggestRequest,
)
from app.recall import entity_recall
from app.vault import safe_render_vault

router = APIRouter(prefix="/entities", tags=["entities"])
same_as_router = APIRouter(prefix="/entities/same-as", tags=["same-as"])
candidates_router = APIRouter(prefix="/entities/candidates", tags=["entity-candidates"])
relations_router = APIRouter(prefix="/entities/relations", tags=["entity-relations"])

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


def _write_entity_relation(conn, entity_id: str, payload: EntityRelationCreate) -> None:
    """İlişkiyi yazar — vault RENDER ETMEZ.

    Faz 22'de ayrıldı: toplu karar ucu 76 ilişkiyi tek çağrıda kuruyor ve her biri için
    vault'u baştan render etmek (Entity/Event/Source/Investigation klasörlerinin tamamı
    siliniyor ve yeniden yazılıyor) işlemi dakikalarca sürdürüyordu. Render, çağıranın
    sorumluluğunda ve iş bitince BİR KEZ yapılıyor."""
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": payload.to_entity_id})) is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {payload.to_entity_id}")
    if entity_id == payload.to_entity_id:
        raise HTTPException(status_code=422, detail="Bir entity kendisiyle ilişkilendirilemez")
    conn.execute(
        "MATCH (a:Entity {id: $aid}), (b:Entity {id: $bid}) "
        "CREATE (a)-[:ENTITY_RELATION {relation_type: $rt, confidence: $conf, "
        "valid_from: $now, valid_to: NULL, status: 'ACTIVE'}]->(b)",
        {
            "aid": entity_id,
            "bid": payload.to_entity_id,
            "rt": payload.relation_type,
            "conf": payload.confidence,
            "now": datetime.now(timezone.utc),
        },
    )


@router.post("/{entity_id}/relations", status_code=201)
def create_entity_relation(entity_id: str, payload: EntityRelationCreate) -> dict:
    conn = get_connection()
    _write_entity_relation(conn, entity_id, payload)
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


# ---- Faz 20: Entity adayı çıkarma (deterministik) ------------------------------------------
#
# Ayrı bir router, `same_as_router` ile aynı gerekçeyle: `/entities/candidates` yolu
# `/entities/{entity_id}`den ÖNCE eşleşmeli, yoksa "candidates" bir entity id'si sanılır.
# main.py bu router'ları `entities.router`dan önce include ediyor.


def _set_candidate_status(conn, key: str, name: str, status: str, entity_id: str | None = None) -> None:
    """Kararı yaz/güncelle. Aday DÜĞÜMÜ silinmez, durumu değişir — "elenen kaybolmaz,
    işaretlenir" (Q17): geri alma yolu ancak kayıt durursa mümkün."""
    now = datetime.now(timezone.utc)
    exists = fetch_one(
        conn.execute("MATCH (c:EntityCandidate {key: $key}) RETURN c.key AS key", {"key": key})
    )
    if exists:
        conn.execute(
            "MATCH (c:EntityCandidate {key: $key}) SET c.status = $status, c.decided_at = $now, "
            "c.promoted_entity_id = $eid, c.name = $name",
            {"key": key, "status": status, "now": now, "eid": entity_id or "", "name": name},
        )
    else:
        conn.execute(
            "CREATE (:EntityCandidate {key: $key, name: $name, status: $status, "
            "decided_at: $now, promoted_entity_id: $eid})",
            {"key": key, "name": name, "status": status, "now": now, "eid": entity_id or ""},
        )


@candidates_router.get("", response_model=list[ExtractedEntityCandidate])
def list_entity_candidates(
    include_decided: bool = Query(False, description="Karar verilmiş adaylar da dönsün mü"),
) -> list[ExtractedEntityCandidate]:
    """Faz 20 — claim metinlerinden çıkarılmış entity adayları (bkz. app/entityextract.py).

    Adaylar saklanmıyor, her çağrıda yeniden çıkarılıyor; saklanan tek şey kullanıcının
    kararı. Sıralama sinyali: kaç FARKLI kaynak, sonra kaç claim."""
    conn = get_connection()
    return [
        ExtractedEntityCandidate(**c) for c in entity_candidates(conn, include_decided=include_decided)
    ]


@candidates_router.post("/dismiss", response_model=EntityCandidateDecisionResult)
def dismiss_entity_candidates(payload: EntityCandidateDismiss) -> EntityCandidateDecisionResult:
    """Toplu eleme. Elenen aday listeden kalkar ama SİLİNMEZ — `include_decided=true` ile
    görülebilir ve `/restore` ile geri alınabilir."""
    conn = get_connection()
    known = {c["key"]: c["name"] for c in entity_candidates(conn, include_decided=True)}
    count = 0
    for key in payload.keys:
        _set_candidate_status(conn, key, known.get(key, key), "DISMISSED")
        count += 1
    return EntityCandidateDecisionResult(dismissed=count)


@candidates_router.post("/restore", response_model=EntityCandidateDecisionResult)
def restore_entity_candidates(payload: EntityCandidateDismiss) -> EntityCandidateDecisionResult:
    """Elemeyi geri alır. PROMOTED bir aday geri alınmaz: karşılığında bir Entity yaratıldı
    ve o Entity silinmeden aday listesine dönmek iki kaydı aynı anda canlı tutardı."""
    conn = get_connection()
    count = 0
    for key in payload.keys:
        row = fetch_one(
            conn.execute(
                "MATCH (c:EntityCandidate {key: $key}) RETURN c.status AS status", {"key": key}
            )
        )
        if row is None or row["status"] != "DISMISSED":
            continue
        conn.execute("MATCH (c:EntityCandidate {key: $key}) DELETE c", {"key": key})
        count += 1
    return EntityCandidateDecisionResult(restored=count)


@candidates_router.post("/promote", response_model=EntityCandidateDecisionResult)
def promote_entity_candidates(payload: EntityCandidatePromote) -> EntityCandidateDecisionResult:
    """Adayı gerçek bir Entity'ye çevirir. Tür serbest metin (F8) — sabit bir listeye
    kilitlenmiş tür alanı gerçek araştırmada hep yanlış kovaya zorluyor."""
    conn = get_connection()
    known = {c["key"]: c["name"] for c in entity_candidates(conn, include_decided=True)}
    created: list[Entity] = []
    for item in payload.items:
        name = (item.name or known.get(item.key) or item.key).strip()
        if not name:
            continue
        entity = create_entity(
            EntityCreate(name=name, entity_type=item.entity_type.strip() or "Organization", aliases=item.aliases)
        )
        _set_candidate_status(conn, item.key, name, "PROMOTED", entity.id)
        created.append(entity)
    return EntityCandidateDecisionResult(promoted=len(created), entities=created)


# ---- Faz 22: İlişki adaylarını toplu eritme + graf ------------------------------------------
#
# Ayrı router, `/entities/{entity_id}`den önce eşleşmesi için (same_as_router deseni).


@relations_router.get("/candidates", response_model=list[RelationPairCandidate])
def list_relation_pair_candidates() -> list[RelationPairCandidate]:
    """Graf'ın tamamı için ilişki adayı çiftleri (bkz. app/entityrelations.py).

    Faz 19 yalnızca entity başına aday veriyordu; 109 çiftin tamamını eritmek için entity
    entity gezmek gerekiyordu ve kararı pahalı yapan şey buydu (Faz 16'nın dersi)."""
    conn = get_connection()
    return [RelationPairCandidate(**c) for c in relation_pair_candidates(conn)]


@relations_router.post("/batch", response_model=RelationBatchResult)
def decide_relations(payload: RelationBatch) -> RelationBatchResult:
    """Toplu karar: ilişki kur ya da "bu ikisi ilgisiz" de.

    Reddetme Faz 22'de eklendi: Faz 19'da yalnızca KURMA yolu vardı, dolayısıyla ilgisiz bir
    çift aday listesinde sonsuza kadar kalıyordu ve liste hiç erimiyordu (Faz 20/21'in aynı
    kararı: reddedilen kaybolmaz, işaretlenir)."""
    conn = get_connection()
    now = datetime.now(timezone.utc)
    created = rejected = 0
    for decision in payload.decisions:
        action = decision.action.upper()
        for entity_id in (decision.from_entity_id, decision.to_entity_id):
            if fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.id AS id", {"id": entity_id})) is None:
                raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
        if action == "CREATE":
            if not decision.relation_type.strip():
                raise HTTPException(status_code=422, detail="İlişki türü boş olamaz — türü sistem tahmin etmez")
            _write_entity_relation(
                conn,
                decision.from_entity_id,
                EntityRelationCreate(
                    to_entity_id=decision.to_entity_id,
                    relation_type=decision.relation_type.strip(),
                    confidence=decision.confidence,
                ),
            )
            created += 1
        elif action == "REJECT":
            already = fetch_one(
                conn.execute(
                    "MATCH (a:Entity {id: $aid})-[:RELATION_REJECTED]->(b:Entity {id: $bid}) RETURN a.id AS id",
                    {"aid": decision.from_entity_id, "bid": decision.to_entity_id},
                )
            )
            if already is None:
                conn.execute(
                    "MATCH (a:Entity {id: $aid}), (b:Entity {id: $bid}) "
                    "CREATE (a)-[:RELATION_REJECTED {created_at: $now}]->(b)",
                    {"aid": decision.from_entity_id, "bid": decision.to_entity_id, "now": now},
                )
            rejected += 1
        else:
            raise HTTPException(status_code=422, detail=f"Geçersiz aksiyon: {decision.action}")
    safe_render_vault(conn)
    return RelationBatchResult(created=created, rejected=rejected)


@relations_router.get("/graph", response_model=EntityGraph)
def get_entity_graph() -> EntityGraph:
    """Graf görünümünün verisi: entity ve event düğümleri + aralarındaki kenarlar.

    Faz 8'in "Entity Graph paneli duruyor" notunun yanlış olduğu 2026-09-02'de bulunmuştu ve
    o günden beri kapanmamıştı — Faz 22'de kapanıyor."""
    conn = get_connection()
    return EntityGraph(**entity_graph(conn))
