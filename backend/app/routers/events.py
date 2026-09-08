import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.db import fetch_all, fetch_one, get_connection
from app.eventcluster import event_candidates, recompute_event_confidence
from app.models import (
    Event,
    EventCandidate,
    EventCreate,
    EventFromCluster,
    EventFromClusterResult,
    EventUpdate,
    InvolvedInLink,
)
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


# DİKKAT: bu rota `/{event_id}`den ÖNCE tanımlı olmak zorunda — FastAPI sırayla eşleştirir,
# sonra tanımlansaydı "candidates" bir event id'si sanılıp 404 dönerdi.
@router.get("/candidates", response_model=list[EventCandidate])
def list_event_candidates(
    min_size: int = Query(2, ge=1, le=50, description="Bir kümenin aday sayılması için en az claim sayısı"),
) -> list[EventCandidate]:
    """Faz 18 — doğrulama kümelerinden olay adayları (bkz. app/eventcluster.py).

    Yeni bir sinyal üretmez: Faz 17'de kullanıcının elleriyle kurduğu `CORROBORATES`
    bağlarının bağlantılı bileşenlerini okur. Öneridir, karar değildir."""
    conn = get_connection()
    return [EventCandidate(**candidate) for candidate in event_candidates(conn, min_size=min_size)]


@router.post("/from-cluster", response_model=EventFromClusterResult, status_code=201)
def create_event_from_cluster(payload: EventFromCluster) -> EventFromClusterResult:
    """Bir olay adayını Event'e çevirir: olayı yaratır, claim'leri ona bağlar, claim'lerin
    entity'lerini INVOLVED_IN ile, kaynaklarını REPORTED_BY ile olaya taşır.

    Neden entity taşınıyor: bir claim aynı anda hem entity hem event hakkında olamaz, yani
    claim'i olaya bağlamak ABOUT_ENTITY bağını siler. Taşıma olmasaydı, olay kurmak
    entity'nin bildiklerini AZALTIRDI — Faz 18'in çözmeye çalıştığı sorunun (33 claim tek
    kovada) yerine yenisini koyardı."""
    conn = get_connection()
    if not payload.claim_ids:
        raise HTTPException(status_code=422, detail="En az bir claim seçilmeli")
    missing = [
        cid
        for cid in payload.claim_ids
        if fetch_one(conn.execute("MATCH (c:Claim {id: $id}) RETURN c.id AS id", {"id": cid})) is None
    ]
    if missing:
        raise HTTPException(status_code=404, detail=f"Claim not found: {', '.join(missing)}")

    event = create_event(EventCreate(**payload.model_dump(include=set(EventCreate.model_fields))))

    entities: dict[str, str] = {}
    sources: set[str] = set()
    for claim_id in payload.claim_ids:
        row = fetch_one(
            conn.execute(
                "MATCH (c:Claim {id: $id}) "
                "OPTIONAL MATCH (c)-[:ABOUT_ENTITY]->(e:Entity) "
                "OPTIONAL MATCH (s:Source)-[:ASSERTS]->(c) "
                "RETURN e.id AS entity_id, e.name AS entity_name, s.id AS source_id",
                {"id": claim_id},
            )
        )
        if row and row["entity_id"]:
            entities[row["entity_id"]] = row["entity_name"]
        if row and row["source_id"]:
            sources.add(row["source_id"])
        conn.execute("MATCH (c:Claim {id: $id})-[r:ABOUT_ENTITY]->(:Entity) DELETE r", {"id": claim_id})
        conn.execute("MATCH (c:Claim {id: $id})-[r:ABOUT_EVENT]->(:Event) DELETE r", {"id": claim_id})
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (ev:Event {id: $evid}) CREATE (c)-[:ABOUT_EVENT]->(ev)",
            {"cid": claim_id, "evid": event.id},
        )
        conn.execute(
            "MATCH (c:Claim {id: $id}) SET c.updated_at = $now",
            {"id": claim_id, "now": datetime.now(timezone.utc)},
        )

    linked_entities = []
    if payload.carry_entities:
        for entity_id, name in entities.items():
            conn.execute(
                "MATCH (e:Entity {id: $eid}), (ev:Event {id: $evid}) "
                "CREATE (e)-[:INVOLVED_IN {role: $role}]->(ev)",
                {"eid": entity_id, "evid": event.id, "role": payload.entity_role},
            )
            linked_entities.append({"id": entity_id, "name": name, "role": payload.entity_role})

    for source_id in sources:
        conn.execute(
            "MATCH (ev:Event {id: $evid}), (s:Source {id: $sid}) CREATE (ev)-[:REPORTED_BY]->(s)",
            {"evid": event.id, "sid": source_id},
        )

    confidence, state = recompute_event_confidence(conn, event.id)
    event = event.model_copy(update={"confidence": confidence, "knowledge_state": state})

    for entity in linked_entities:
        notify_if_monitored(
            conn,
            target_type="Entity",
            target_id=entity["id"],
            item_type="NEW_EVENT",
            title=f"Yeni bir event'e karıştı: {event.title}",
            detail={"event_id": event.id, "role": entity["role"]},
            confidence=confidence,
            is_novel=True,
        )

    safe_render_vault(conn)
    return EventFromClusterResult(
        event=event,
        linked_claims=len(payload.claim_ids),
        linked_entities=linked_entities,
        linked_sources=len(sources),
    )


@router.get("/{event_id}", response_model=Event)
def get_event(event_id: str) -> Event:
    conn = get_connection()
    result = conn.execute(f"MATCH (e:Event {{id: $id}}) RETURN {_FIELDS}", {"id": event_id})
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return Event(**row)


@router.patch("/{event_id}", response_model=Event)
def update_event(event_id: str, payload: EventUpdate) -> Event:
    """Olayın sınıflandırma alanlarını düzeltir. Bir olayın NE ZAMAN olduğu genellikle ilk
    claim'den sonra netleşir; düzeltme yolu olmasaydı olay adayından kurulan her olay
    "oluşturulduğu an" tarihiyle donup kalırdı."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Event {id: $id}) RETURN e.id AS id", {"id": event_id})) is None:
        raise HTTPException(status_code=404, detail="Event not found")
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return get_event(event_id)
    assignments = ", ".join(f"e.{field} = ${field}" for field in updates)
    conn.execute(f"MATCH (e:Event {{id: $id}}) SET {assignments}", {"id": event_id, **updates})
    safe_render_vault(conn)
    return get_event(event_id)


@router.put("/{event_id}/claims/{claim_id}", response_model=Event)
def link_claim(event_id: str, claim_id: str) -> Event:
    """Mevcut bir claim'i bu olaya bağlar (Faz 11/F16'nın dersi: bağ SONRADAN kurulabilmeli).

    `PATCH /claims/{id}/about` aynı işi yapıyordu ama olay tarafında hiçbir arayüz yoktu ve
    olayın confidence'ı da güncellenmiyordu — burada ikisi bir arada."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Event {id: $id}) RETURN e.id AS id", {"id": event_id})) is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if fetch_one(conn.execute("MATCH (c:Claim {id: $id}) RETURN c.id AS id", {"id": claim_id})) is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    conn.execute("MATCH (c:Claim {id: $id})-[r:ABOUT_ENTITY]->(:Entity) DELETE r", {"id": claim_id})
    conn.execute("MATCH (c:Claim {id: $id})-[r:ABOUT_EVENT]->(:Event) DELETE r", {"id": claim_id})
    conn.execute(
        "MATCH (c:Claim {id: $cid}), (ev:Event {id: $evid}) CREATE (c)-[:ABOUT_EVENT]->(ev)",
        {"cid": claim_id, "evid": event_id},
    )
    conn.execute(
        "MATCH (c:Claim {id: $id}) SET c.updated_at = $now",
        {"id": claim_id, "now": datetime.now(timezone.utc)},
    )
    recompute_event_confidence(conn, event_id)
    safe_render_vault(conn)
    return get_event(event_id)


@router.delete("/{event_id}/claims/{claim_id}", response_model=Event)
def unlink_claim(event_id: str, claim_id: str) -> Event:
    """Claim'i olaydan ayırır — claim SİLİNMEZ (History Is Immutable), yalnızca bağ kalkar.
    Yanlış kümelenmiş bir claim'i düzeltmenin yolu bu."""
    conn = get_connection()
    if fetch_one(conn.execute("MATCH (e:Event {id: $id}) RETURN e.id AS id", {"id": event_id})) is None:
        raise HTTPException(status_code=404, detail="Event not found")
    conn.execute(
        "MATCH (c:Claim {id: $cid})-[r:ABOUT_EVENT]->(:Event {id: $evid}) DELETE r",
        {"cid": claim_id, "evid": event_id},
    )
    recompute_event_confidence(conn, event_id)
    safe_render_vault(conn)
    return get_event(event_id)


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
    # Faz 18: aynı entity'yi iki kez bağlamak, olay sayfasında ikiz satır ve Inbox'ta ikinci
    # bir bildirim üretirdi. Bağ zaten varsa sessizce geçilmez, 409 ile söylenir.
    if fetch_one(
        conn.execute(
            "MATCH (e:Entity {id: $eid})-[:INVOLVED_IN]->(ev:Event {id: $evid}) RETURN e.id AS id",
            {"eid": entity_id, "evid": event_id},
        )
    ) is not None:
        raise HTTPException(status_code=409, detail="Bu entity zaten bu event'e bağlı")
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


@router.delete("/{event_id}/entities/{entity_id}", status_code=204)
def unlink_entity(event_id: str, entity_id: str) -> None:
    conn = get_connection()
    conn.execute(
        "MATCH (e:Entity {id: $eid})-[r:INVOLVED_IN]->(ev:Event {id: $evid}) DELETE r",
        {"eid": entity_id, "evid": event_id},
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
    if fetch_one(
        conn.execute(
            "MATCH (ev:Event {id: $evid})-[:REPORTED_BY]->(s:Source {id: $sid}) RETURN s.id AS id",
            {"evid": event_id, "sid": source_id},
        )
    ) is not None:
        raise HTTPException(status_code=409, detail="Bu kaynak zaten bu event'e bağlı")
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
