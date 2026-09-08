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
    InvestigationNarrativeUpdate,
    InvestigationTransition,
)
from app.monitoring import claim_headline, notify_if_monitored
from app.vault import safe_render_vault

router = APIRouter(prefix="/investigations", tags=["investigations"])
hypotheses_router = APIRouter(prefix="/hypotheses", tags=["hypotheses"])

_INV_FIELDS = (
    "i.id AS id, i.title AS title, i.research_question AS research_question, "
    "i.status AS status, i.analysis AS analysis, i.conclusion AS conclusion, "
    "i.concluded_at AS concluded_at, i.created_at AS created_at, i.updated_at AS updated_at"
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
    safe_render_vault(conn)
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
    # Faz 13 (madde 30): CLOSED, bulguların uzun süreli hafızaya promote edildiği adım —
    # yani "bu araştırma bitti ve şu bilgiyi bilgi grafına ekliyorum" demek. Sonucu hiçbir
    # yere yazmadan bunu yapmak, tam olarak bu projenin defalarca yakaladığı hatanın en
    # pahalı hali olurdu: sistem ne öğrendiğini söyleyemez. ARCHIVED bilerek serbest —
    # o "cevabı buldum" değil, "bunu bıraktım" demek.
    if payload.to_status == "CLOSED" and not (current.conclusion or "").strip():
        raise HTTPException(
            status_code=409,
            detail=(
                "Sonuç (Conclusion) yazılmadan kapatılamaz: kapanış, doğrulanmış bulguları "
                "Knowledge Graph'a yükselten adım. Araştırmayı cevapsız bırakmak istiyorsan "
                "ARCHIVED kullan."
            ),
        )
    now = datetime.now(timezone.utc)
    conn.execute(
        "MATCH (i:Investigation {id: $id}) SET i.status = $status, i.updated_at = $now",
        {"id": investigation_id, "status": payload.to_status, "now": now},
    )
    if payload.to_status in CLOSING_STATUSES:
        _promote_verified_findings(conn, investigation_id)
    _notify_investigation_update(conn, investigation_id, current.status, payload.to_status)
    safe_render_vault(conn)
    return get_investigation(investigation_id)


@router.patch("/{investigation_id}/narrative", response_model=Investigation)
def update_narrative(investigation_id: str, payload: InvestigationNarrativeUpdate) -> Investigation:
    """Analysis ve/veya Conclusion'ı yazar (madde 30'un son iki adımı).

    History Is Immutable ile çelişmez: bunlar toplanan veri değil, ANALİSTİN kendi metni —
    araştırma sürerken gelişmesi beklenen bir defter. `concluded_at` yalnızca sonuç ilk kez
    yazıldığında damgalanıyor; sonraki düzeltmeler ilk sonuca varış anını değiştirmiyor."""
    conn = get_connection()
    current = get_investigation(investigation_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Değiştirilecek bir alan verilmedi")

    now = datetime.now(timezone.utc)
    sets = ["i.updated_at = $now"]
    params: dict = {"id": investigation_id, "now": now}
    if "analysis" in updates:
        sets.append("i.analysis = $analysis")
        params["analysis"] = updates["analysis"]
    if "conclusion" in updates:
        sets.append("i.conclusion = $conclusion")
        params["conclusion"] = updates["conclusion"]
        if (updates["conclusion"] or "").strip() and current.concluded_at is None:
            sets.append("i.concluded_at = $now")
    conn.execute(f"MATCH (i:Investigation {{id: $id}}) SET {', '.join(sets)}", params)
    safe_render_vault(conn)
    return get_investigation(investigation_id)


def _notify_investigation_update(conn, investigation_id: str, from_status: str, to_status: str) -> None:
    """Faz 23: bu bildirim ARTIK ÜRETİLMİYOR — fonksiyon bilerek boş bırakıldı.

    Ölçüm (2026-09-08): Inbox'taki 59 öğenin 3'ü buydu ve üçü de kullanıcının kendi yaptığı
    durum geçişiydi ("OPEN -> ACTIVE"). Tek kullanıcılı bir araçta, kişinin bir saniye önce
    kendi tıkladığı işlemi ona haber vermek tanım gereği gürültüdür — ve Inbox'ın işi
    "more signal, less noise" (madde 25). Geçiş kaybolmuyor: `Investigation.status` graf'ta,
    geçiş de vault'un günlük notunda duruyor.

    Fonksiyon SİLİNMEDİ, çünkü çağrı noktaları durum makinesinin okunmasını kolaylaştırıyor
    ve ileride "başkasının araştırması" gibi çok kullanıcılı bir senaryo çıkarsa bildirimin
    yeri burasıdır. Gövde boş ama gerekçe burada duruyor."""
    return


def _notify_investigation_update_disabled(conn, investigation_id: str, from_status: str, to_status: str) -> None:
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


def _scope_edge_exists(conn, investigation_id: str, rel: str, node_id: str) -> bool:
    return (
        fetch_one(
            conn.execute(
                f"MATCH (i:Investigation {{id: $iid}})-[:{rel}]->(n {{id: $nid}}) RETURN n.id AS id",
                {"iid": investigation_id, "nid": node_id},
            )
        )
        is not None
    )


@router.get("/{investigation_id}/scope")
def get_scope(investigation_id: str) -> dict:
    """Faz 11 (tarama bulgusu F35): investigation'ın kapsamı YAZILABİLİYOR ama OKUNAMIYORDU —
    `INCLUDES`/`INVESTIGATES` için PUT uçları vardı, karşılığında hiçbir GET yoktu. Yani bir
    investigation'ın hangi entity/event'leri kapsadığı, kurulduktan sonra hiçbir yerden geri
    alınamıyordu (arayüz de bu yüzden hiç göstermiyordu).

    Faz 3'ün "Research Question → Scope → Entities → ..." akışının Scope adımı bu."""
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    entities = fetch_all(
        conn.execute(
            "MATCH (i:Investigation {id: $iid})-[:INCLUDES]->(e:Entity) "
            "RETURN e.id AS id, e.name AS name, e.entity_type AS entity_type ORDER BY e.name",
            {"iid": investigation_id},
        )
    )
    events = fetch_all(
        conn.execute(
            "MATCH (i:Investigation {id: $iid})-[:INVESTIGATES]->(ev:Event) "
            "RETURN ev.id AS id, ev.title AS title, ev.event_type AS event_type ORDER BY ev.title",
            {"iid": investigation_id},
        )
    )
    return {"entities": entities, "events": events}


@router.get("/{investigation_id}/workspace")
def get_workspace(investigation_id: str) -> dict:
    """Faz 13 (madde 30) — Investigation Workspace'in tam zinciri:
    Research Question -> Scope -> Entities -> Sources -> Observations -> Claims -> Evidence
    -> Hypotheses -> Analysis -> Findings -> Conclusion.

    **Ara adımlar TÜRETİLİYOR, ayrıca beyan edilmiyor.** Kaynak/gözlem/claim/kanıt için yeni
    ilişki tabloları eklemek, kullanıcıdan zaten grafta duran bağları elle bir kez daha
    kurmasını istemek olurdu — ve elle kurulan her bağ, kurulmayı unutulabilen bir bağdır
    (Faz 11'in tekrar eden dersi). Burada zincir kapsamdaki entity/event'lerden ve
    finding'lerden geriye doğru yürünerek çıkarılıyor:

        Entity/Event (kapsam)
          <- ABOUT_ENTITY/ABOUT_EVENT -  Claim
          <- ASSERTS                  -  Source        (hangi kaynakları kullandık)
          <- PRODUCED                 -  Observation   (hangi ham veriden geldi)
          <- SUPPORTS/CONTRADICTS     -  Evidence      (neye dayanıyor)

    Bu aynı zamanda madde 33 (Provenance) ve 34 (Research Reproducibility) sorularının
    cevabı: "bu sonuca hangi ham gözlemden, hangi kaynak üzerinden gelindi".

    `included` alanı bir claim'in kapsamdan mı yoksa doğrudan finding olarak mı geldiğini
    söyler — ikisi aynı şey değil ve karıştırmak "neyi bulgu ilan ettim" sorusunu bulanıklaştırır."""
    conn = get_connection()
    inv = get_investigation(investigation_id)
    scope = get_scope(investigation_id)
    entity_ids = [e["id"] for e in scope["entities"]]
    event_ids = [e["id"] for e in scope["events"]]

    finding_rows = fetch_all(
        conn.execute(
            "MATCH (i:Investigation {id: $iid})-[:HAS_FINDING]->(c:Claim) RETURN c.id AS id",
            {"iid": investigation_id},
        )
    )
    finding_ids = {r["id"] for r in finding_rows}

    # Kapsamdaki entity/event hakkındaki claim'ler + doğrudan finding olarak eklenmiş olanlar.
    claims: dict[str, dict] = {}

    def _collect(cypher: str, params: dict) -> None:
        for row in fetch_all(conn.execute(cypher, params)):
            claims.setdefault(row["id"], row)

    if entity_ids:
        _collect(
            "MATCH (c:Claim)-[:ABOUT_ENTITY]->(e:Entity) WHERE e.id IN $ids "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence, c.valid_from AS valid_from, c.valid_to AS valid_to",
            {"ids": entity_ids},
        )
    if event_ids:
        _collect(
            "MATCH (c:Claim)-[:ABOUT_EVENT]->(ev:Event) WHERE ev.id IN $ids "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence, c.valid_from AS valid_from, c.valid_to AS valid_to",
            {"ids": event_ids},
        )
    if finding_ids:
        _collect(
            "MATCH (c:Claim) WHERE c.id IN $ids "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence, c.valid_from AS valid_from, c.valid_to AS valid_to",
            {"ids": sorted(finding_ids)},
        )

    claim_ids = sorted(claims)
    for cid, row in claims.items():
        row["headline"] = claim_headline(row.pop("text"))
        row["is_finding"] = cid in finding_ids
        # F34: yerini almış bir claim, güncel olanla aynı görünmemeli.
        row["superseded"] = row.get("valid_to") is not None

    sources = fetch_all(
        conn.execute(
            "MATCH (s:Source)-[:ASSERTS]->(c:Claim) WHERE c.id IN $ids "
            "RETURN DISTINCT s.id AS id, s.name AS name, s.source_type AS source_type, "
            "s.reliability AS reliability ORDER BY name",
            {"ids": claim_ids},
        )
    ) if claim_ids else []

    observations = fetch_all(
        conn.execute(
            "MATCH (o:Observation)-[:PRODUCED]->(c:Claim) WHERE c.id IN $ids "
            "RETURN DISTINCT o.id AS id, o.raw_content AS raw_content, "
            "o.source_url AS source_url, o.observed_at AS observed_at, o.promoted AS promoted "
            "ORDER BY observed_at",
            {"ids": claim_ids},
        )
    ) if claim_ids else []
    for o in observations:
        o["headline"] = claim_headline(o.pop("raw_content"))

    evidence = []
    if claim_ids:
        for stance in ("SUPPORTS", "CONTRADICTS"):
            evidence += [
                {**row, "stance": stance}
                for row in fetch_all(
                    conn.execute(
                        f"MATCH (ev:Evidence)-[:{stance}]->(c:Claim) WHERE c.id IN $ids "
                        "RETURN DISTINCT ev.id AS id, ev.evidence_type AS evidence_type, "
                        "ev.file_path AS file_path, ev.content_hash AS content_hash",
                        {"ids": claim_ids},
                    )
                )
            ]

    hypotheses = [h.model_dump(mode="json") for h in list_hypotheses(investigation_id)]

    return {
        "investigation": inv.model_dump(mode="json"),
        "scope": scope,
        "sources": sources,
        "observations": observations,
        "claims": sorted(claims.values(), key=lambda c: (not c["is_finding"], c["headline"])),
        "evidence": evidence,
        "hypotheses": hypotheses,
        "findings": sorted(finding_ids),
        # Zincirin her adımının "dolu mu" durumu — arayüz akışı adım adım gösterebilsin ve
        # nerede durulduğu görünsün (madde 34, reproducibility).
        "steps": {
            "research_question": bool((inv.research_question or "").strip()),
            "scope": bool(entity_ids or event_ids),
            "sources": bool(sources),
            "observations": bool(observations),
            "claims": bool(claims),
            "evidence": bool(evidence),
            "hypotheses": bool(hypotheses),
            "analysis": bool((inv.analysis or "").strip()),
            "findings": bool(finding_ids),
            "conclusion": bool((inv.conclusion or "").strip()),
        },
    }


@router.put("/{investigation_id}/entities/{entity_id}", status_code=204)
def include_entity(investigation_id: str, entity_id: str) -> None:
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    if not _node_exists(conn, "Entity", entity_id):
        raise HTTPException(status_code=404, detail="Entity not found")
    # F35: PUT idempotent olmalı; guard yokken aynı entity iki kez eklenince graf'ta iki
    # INCLUDES kenarı oluşuyordu (kapsam listesi kaydı çift gösterirdi).
    if _scope_edge_exists(conn, investigation_id, "INCLUDES", entity_id):
        return
    conn.execute(
        "MATCH (i:Investigation {id: $iid}), (e:Entity {id: $eid}) CREATE (i)-[:INCLUDES]->(e)",
        {"iid": investigation_id, "eid": entity_id},
    )
    safe_render_vault(conn)


@router.delete("/{investigation_id}/entities/{entity_id}", status_code=204)
def exclude_entity(investigation_id: str, entity_id: str) -> None:
    """F35: kapsamdan çıkarma yolu yoktu. Yanlış eklenen bir entity'yi geri almanın hiçbir
    yolu olmaması, Faz 11'de üç kez tekrarlanan hatanın (F16, F23b, F29) aynısı olurdu.
    Kapsam bir çalışma alanı tanımıdır, geçmiş kaydı değil — düzeltilebilir olmalı."""
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    conn.execute(
        "MATCH (i:Investigation {id: $iid})-[r:INCLUDES]->(e:Entity {id: $eid}) DELETE r",
        {"iid": investigation_id, "eid": entity_id},
    )
    safe_render_vault(conn)


@router.put("/{investigation_id}/events/{event_id}", status_code=204)
def investigate_event(investigation_id: str, event_id: str) -> None:
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    if not _node_exists(conn, "Event", event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    if _scope_edge_exists(conn, investigation_id, "INVESTIGATES", event_id):
        return
    conn.execute(
        "MATCH (i:Investigation {id: $iid}), (e:Event {id: $eid}) CREATE (i)-[:INVESTIGATES]->(e)",
        {"iid": investigation_id, "eid": event_id},
    )
    safe_render_vault(conn)


@router.delete("/{investigation_id}/events/{event_id}", status_code=204)
def uninvestigate_event(investigation_id: str, event_id: str) -> None:
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    conn.execute(
        "MATCH (i:Investigation {id: $iid})-[r:INVESTIGATES]->(e:Event {id: $eid}) DELETE r",
        {"iid": investigation_id, "eid": event_id},
    )
    safe_render_vault(conn)


@router.put("/{investigation_id}/findings/{claim_id}", status_code=204)
def add_finding(investigation_id: str, claim_id: str) -> None:
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    if not _node_exists(conn, "Claim", claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    # F38: kapsam PUT'larıyla aynı sorun — guard yokken aynı claim iki kez eklenince iki
    # HAS_FINDING kenarı oluşuyor ve finding listesi kaydı çift gösteriyordu.
    if _scope_edge_exists(conn, investigation_id, "HAS_FINDING", claim_id):
        return
    conn.execute(
        "MATCH (i:Investigation {id: $iid}), (c:Claim {id: $cid}) CREATE (i)-[:HAS_FINDING]->(c)",
        {"iid": investigation_id, "cid": claim_id},
    )
    safe_render_vault(conn)


@router.delete("/{investigation_id}/findings/{claim_id}", status_code=204)
def remove_finding(investigation_id: str, claim_id: str) -> None:
    """F38: yanlış eklenen finding geri alınabilmeli. Claim SİLİNMEZ — yalnızca bu
    investigation'ın bulgu listesinden çıkarılır."""
    conn = get_connection()
    if not _node_exists(conn, "Investigation", investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    conn.execute(
        "MATCH (i:Investigation {id: $iid})-[r:HAS_FINDING]->(c:Claim {id: $cid}) DELETE r",
        {"iid": investigation_id, "cid": claim_id},
    )
    safe_render_vault(conn)


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
        # Faz 13: `headline` UÇTA üretiliyor, arayüzde değil. `claim_headline`'ın docstring'i
        # (F46) kalıcı çözümü zaten söylüyordu: "tüm render yollarının tek bir noktadan
        # geçmesi". Aynı hata dördüncü kez, aynı sayfada çıktı — Workspace'in Claim'ler
        # bölümü başlığı doğru kesiyordu ama Findings bölümü ham metni basıyordu, yani
        # RSS'ten gelen "başlık + özet" tek satıra yapışık görünüyordu. Ham `text` yanıtta
        # kalıyor (tam metin gerektiğinde lazım), ama render edilecek olan bu.
        row["headline"] = claim_headline(row["text"])
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
    safe_render_vault(conn)
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
    safe_render_vault(conn)
    return get_hypothesis(hypothesis_id)
