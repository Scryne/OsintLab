import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.confidence import ConfidenceResult, compute_confidence
from app.db import fetch_all, fetch_one, get_connection
from app.lineage import resolve_independent_root
from app.corroboration import find_candidates, find_observation_candidates
from app.eventcluster import recompute_event_confidence
from app.mentions import claim_mentions, mention_candidates, set_mention
from app.models import (
    CandidateClaim,
    ObservationCorroborationCandidate,
    Claim,
    ClaimAboutUpdate,
    ClaimContradictionAdd,
    ClaimCreate,
    ClaimLinkBatch,
    ClaimLinkBatchResult,
    ClaimLinkResult,
    ClaimMention,
    ClaimMentionGroup,
    ClaimSupersedeAdd,
    CorroborationCandidate,
    MentionBatch,
    MentionBatchResult,
)
from app.monitoring import claim_headline, notify_if_monitored
from app.recall import why_matters
from app.vault import safe_render_vault

router = APIRouter(prefix="/claims", tags=["claims"])
mentions_router = APIRouter(prefix="/claims/mentions", tags=["mentions"])

# `CandidateClaim` alanlarının `corroboration._load_claims` satırından okunacak kısmı.
_CANDIDATE_FIELDS = (
    "id", "text", "source_id", "source_name", "confidence", "knowledge_state", "valid_from",
)

_FIELDS = (
    "c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
    "c.confidence AS confidence, c.valid_from AS valid_from, c.valid_to AS valid_to, "
    "c.created_at AS created_at, c.updated_at AS updated_at"
)


def _node_exists(conn, label: str, node_id: str) -> bool:
    result = conn.execute(f"MATCH (n:{label} {{id: $id}}) RETURN n.id AS id", {"id": node_id})
    return fetch_one(result) is not None


def _claim_source_id(conn, claim_id: str) -> str | None:
    result = conn.execute(
        "MATCH (s:Source)-[:ASSERTS]->(c:Claim {id: $id}) RETURN s.id AS id, s.reliability AS reliability",
        {"id": claim_id},
    )
    row = fetch_one(result)
    return row


def _claim_about(conn, claim_id: str) -> tuple[str | None, str | None]:
    entity_row = fetch_one(
        conn.execute(
            "MATCH (c:Claim {id: $id})-[:ABOUT_ENTITY]->(e:Entity) RETURN e.id AS id", {"id": claim_id}
        )
    )
    event_row = fetch_one(
        conn.execute(
            "MATCH (c:Claim {id: $id})-[:ABOUT_EVENT]->(e:Event) RETURN e.id AS id", {"id": claim_id}
        )
    )
    return (entity_row["id"] if entity_row else None, event_row["id"] if event_row else None)


def _gather_confidence_inputs(conn, claim_id: str) -> ConfidenceResult:
    source_row = _claim_source_id(conn, claim_id)
    source_reliability = source_row["reliability"] if source_row else 0.5

    corroborators = fetch_all(
        conn.execute(
            "MATCH (s:Source)-[:ASSERTS]->(other:Claim)-[:CORROBORATES]->(c:Claim {id: $id}) "
            "RETURN DISTINCT s.id AS source_id, other.id AS claim_id",
            {"id": claim_id},
        )
    )
    # Q6 (Faz 6): iki farklı Source aynı DERIVED_FROM zincirinin kökündeyse (ör. Site B
    # -> Site A -> Agency), bunlar bağımsız kaynaklar SAYILMAZ — sadece tek bir kökene
    # (independent root) indirgenmiş id kümesi independence hesabına girer. Ajansın kendisi
    # ile o ajanstan türeyen bir site arasındaki corroboration da bu yüzden bağımsızlık
    # katkısı yapmaz.
    corroborating_source_ids = {
        resolve_independent_root(conn, row["source_id"]) for row in corroborators
    }
    if source_row is not None:
        corroborating_source_ids.discard(resolve_independent_root(conn, source_row["id"]))
    corroborating_claims_count = len({row["claim_id"] for row in corroborators})

    evidence_count = len(
        fetch_all(
            conn.execute(
                "MATCH (ev:Evidence)-[:SUPPORTS]->(c:Claim {id: $id}) RETURN ev.id AS id",
                {"id": claim_id},
            )
        )
    )
    contradicting_evidence_count = len(
        fetch_all(
            conn.execute(
                "MATCH (ev:Evidence)-[:CONTRADICTS]->(c:Claim {id: $id}) RETURN ev.id AS id",
                {"id": claim_id},
            )
        )
    )

    outgoing_unresolved = fetch_all(
        conn.execute(
            "MATCH (c:Claim {id: $id})-[r:CLAIM_CONTRADICTS]->(other:Claim) "
            "WHERE r.status = 'UNRESOLVED' RETURN other.id AS id",
            {"id": claim_id},
        )
    )
    incoming_unresolved = fetch_all(
        conn.execute(
            "MATCH (other:Claim)-[r:CLAIM_CONTRADICTS]->(c:Claim {id: $id}) "
            "WHERE r.status = 'UNRESOLVED' RETURN other.id AS id",
            {"id": claim_id},
        )
    )
    has_unresolved_contradiction = bool(outgoing_unresolved or incoming_unresolved)

    return compute_confidence(
        source_reliability=source_reliability,
        corroborating_source_ids=corroborating_source_ids,
        corroborating_claims_count=corroborating_claims_count,
        evidence_count=evidence_count,
        contradicting_evidence_count=contradicting_evidence_count,
        has_unresolved_contradiction=has_unresolved_contradiction,
    )


def _recompute_and_store(conn, claim_id: str) -> ConfidenceResult:
    result = _gather_confidence_inputs(conn, claim_id)
    conn.execute(
        "MATCH (c:Claim {id: $id}) SET c.confidence = $confidence, c.knowledge_state = $state, "
        "c.updated_at = $now",
        {"id": claim_id, "confidence": result.confidence, "state": result.knowledge_state, "now": datetime.now(timezone.utc)},
    )
    # Faz 18: olayın confidence'ı claim'lerinden türetildiği için, claim'in skoru her
    # değiştiğinde (doğrulama bağı, kanıt, çelişki) olay da tazelenmeli. Tek boğaz noktası
    # burası — çağıran her uca ayrı ayrı eklenseydi biri mutlaka unutulurdu.
    event_row = fetch_one(
        conn.execute(
            "MATCH (c:Claim {id: $id})-[:ABOUT_EVENT]->(ev:Event) RETURN ev.id AS id", {"id": claim_id}
        )
    )
    if event_row:
        recompute_event_confidence(conn, event_row["id"])
    return result


def _is_first_claim_about(conn, entity_id: str | None, event_id: str | None, exclude_claim_id: str) -> bool:
    """Faz 7 (madde 24) novelty sinyali: bu entity/event hakkındaki İLK claim mi?"""
    if entity_id:
        rows = fetch_all(
            conn.execute(
                "MATCH (c:Claim)-[:ABOUT_ENTITY]->(:Entity {id: $id}) WHERE c.id <> $exclude RETURN c.id AS id",
                {"id": entity_id, "exclude": exclude_claim_id},
            )
        )
        return not rows
    if event_id:
        rows = fetch_all(
            conn.execute(
                "MATCH (c:Claim)-[:ABOUT_EVENT]->(:Event {id: $id}) WHERE c.id <> $exclude RETURN c.id AS id",
                {"id": event_id, "exclude": exclude_claim_id},
            )
        )
        return not rows
    return False


def _notify_change(
    conn,
    *,
    claim_id: str,
    about_entity_id: str | None,
    about_event_id: str | None,
    result: ConfidenceResult,
    title: str,
) -> None:
    """Faz 7 — Change Detection'ın 'Notify' adımı: izlenen bir Entity/Event bu claim'le
    ilgiliyse Intelligence Inbox'a bir öğe düşer (bkz. app/monitoring.py). item_type burada
    kendi belirleniyor: çelişki > yenilik (ilk kez görülen entity/event) > mevcut bilginin
    güncellenmesi (madde 23/24)."""
    has_contradiction = result.knowledge_state == "CONTRADICTED"
    is_novel = _is_first_claim_about(conn, about_entity_id, about_event_id, claim_id)
    if has_contradiction:
        item_type = "CONTRADICTION"
        # Faz 23 hata düzeltmesi: `item_type` SONUÇTAN türetiliyordu ama başlık ÇAĞIRANDAN
        # geliyordu ve ikisi çelişebiliyordu. Ölçümde Inbox'taki 4 CONTRADICTION öğesinin
        # dördü de "Claim bağımsız olarak doğrulandı" diyordu — çünkü toplu bağlama ucu
        # (links-batch) iki tarafa da aynı doğrulama başlığını geçiyor. En yüksek öncelikli
        # öğeler tam tersini söyleyen bir başlıkla duruyordu; Inbox'ın hiç kullanılmamış
        # olmasının muhtemel sebeplerinden biri bu. Başlık artık türle birlikte, tek yerde
        # türetiliyor — çağıranın metni çelişki durumunda eziliyor.
        row = fetch_one(conn.execute("MATCH (c:Claim {id: $id}) RETURN c.text AS text", {"id": claim_id}))
        excerpt = claim_headline(row["text"]) if row else ""
        title = f"Çelişki: {excerpt}" if excerpt else "Bir claim çelişkili duruma düştü"
    elif is_novel:
        item_type = "NEW_RELATIONSHIP"
    else:
        item_type = "SIGNIFICANT_CHANGE"
    detail = {"claim_id": claim_id, "knowledge_state": result.knowledge_state}
    for target_type, target_id in (("Entity", about_entity_id), ("Event", about_event_id)):
        if not target_id:
            continue
        notify_if_monitored(
            conn,
            target_type=target_type,
            target_id=target_id,
            item_type=item_type,
            title=title,
            detail=detail,
            confidence=result.confidence,
            has_contradiction=has_contradiction,
            independence=result.independence,
            is_novel=is_novel,
        )


def _claim_supersede_links(conn, claim_id: str) -> tuple[str | None, str | None]:
    """F34: (bu claim'in yerini alan, bu claim'in yerini aldığı). SUPERSEDES tek yön
    saklanıyor (yeni)-[:SUPERSEDES]->(eski), ama iki soru da sorulabilmeli: 'bu bilgi hâlâ
    geçerli mi' ve 'neyin yerini aldı'."""
    yeni = fetch_one(
        conn.execute(
            "MATCH (yeni:Claim)-[:SUPERSEDES]->(c:Claim {id: $id}) RETURN yeni.id AS id",
            {"id": claim_id},
        )
    )
    eski = fetch_one(
        conn.execute(
            "MATCH (c:Claim {id: $id})-[:SUPERSEDES]->(eski:Claim) RETURN eski.id AS id",
            {"id": claim_id},
        )
    )
    return (yeni["id"] if yeni else None, eski["id"] if eski else None)


def _row_to_claim(conn, row: dict) -> Claim:
    source_row = _claim_source_id(conn, row["id"])
    about_entity_id, about_event_id = _claim_about(conn, row["id"])
    superseded_by, supersedes = _claim_supersede_links(conn, row["id"])
    return Claim(
        source_id=source_row["id"] if source_row else "",
        about_entity_id=about_entity_id,
        about_event_id=about_event_id,
        superseded_by_claim_id=superseded_by,
        supersedes_claim_id=supersedes,
        **row,
    )


@router.post("", response_model=Claim, status_code=201)
def create_claim(payload: ClaimCreate) -> Claim:
    conn = get_connection()

    if not _node_exists(conn, "Source", payload.source_id):
        raise HTTPException(status_code=404, detail=f"Source not found: {payload.source_id}")
    if payload.about_entity_id and not _node_exists(conn, "Entity", payload.about_entity_id):
        raise HTTPException(status_code=404, detail=f"Entity not found: {payload.about_entity_id}")
    if payload.about_event_id and not _node_exists(conn, "Event", payload.about_event_id):
        raise HTTPException(status_code=404, detail=f"Event not found: {payload.about_event_id}")
    for eid in payload.evidence_ids + payload.contradicting_evidence_ids:
        if not _node_exists(conn, "Evidence", eid):
            raise HTTPException(status_code=404, detail=f"Evidence not found: {eid}")
    for cid in payload.corroborates + payload.contradicts:
        if not _node_exists(conn, "Claim", cid):
            raise HTTPException(status_code=404, detail=f"Claim not found: {cid}")
    if payload.supersedes and not _node_exists(conn, "Claim", payload.supersedes):
        raise HTTPException(status_code=404, detail=f"Claim not found: {payload.supersedes}")

    claim_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    # Faz 11 (F12): created_at = kaydın oluşturulduğu an (değişmez sistem kaydı),
    # valid_from = iddianın geçerli olduğu an (kaynağın yayın tarihi). İkisi aynı şey değil;
    # önceden ikisi de "şimdi" olduğu için arşivden gelen eski bilgi en yeni gibi sıralanıyordu.
    valid_from = payload.valid_from or now

    conn.execute(
        "CREATE (:Claim {id: $id, text: $text, knowledge_state: 'OBSERVED', confidence: 0.0, "
        "valid_from: $valid_from, valid_to: NULL, created_at: $now, updated_at: $now})",
        {"id": claim_id, "text": payload.text, "now": now, "valid_from": valid_from},
    )
    conn.execute(
        "MATCH (s:Source {id: $sid}), (c:Claim {id: $cid}) CREATE (s)-[:ASSERTS]->(c)",
        {"sid": payload.source_id, "cid": claim_id},
    )
    if payload.about_entity_id:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (e:Entity {id: $eid}) CREATE (c)-[:ABOUT_ENTITY]->(e)",
            {"cid": claim_id, "eid": payload.about_entity_id},
        )
    if payload.about_event_id:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (e:Event {id: $eid}) CREATE (c)-[:ABOUT_EVENT]->(e)",
            {"cid": claim_id, "eid": payload.about_event_id},
        )
    for eid in payload.evidence_ids:
        conn.execute(
            "MATCH (ev:Evidence {id: $eid}), (c:Claim {id: $cid}) CREATE (ev)-[:SUPPORTS]->(c)",
            {"eid": eid, "cid": claim_id},
        )
    for eid in payload.contradicting_evidence_ids:
        conn.execute(
            "MATCH (ev:Evidence {id: $eid}), (c:Claim {id: $cid}) CREATE (ev)-[:CONTRADICTS]->(c)",
            {"eid": eid, "cid": claim_id},
        )

    # Q4 corroboration: simetrik bir ilişki — bağımsız iki claim aynı şeyi doğruluyorsa
    # ikisi de birbirini destekler, bu yüzden ilişki her iki yönde de kurulur ve her iki
    # claim de yeniden hesaplanır.
    for cid in payload.corroborates:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (other:Claim {id: $oid}) "
            "CREATE (c)-[:CORROBORATES]->(other) CREATE (other)-[:CORROBORATES]->(c)",
            {"cid": claim_id, "oid": cid},
        )
        other_result = _recompute_and_store(conn, cid)
        other_about_entity, other_about_event = _claim_about(conn, cid)
        _notify_change(
            conn,
            claim_id=cid,
            about_entity_id=other_about_entity,
            about_event_id=other_about_event,
            result=other_result,
            title="Var olan bir claim bağımsız olarak doğrulandı",
        )

    # Q9 Contradiction: eski bilgi SİLİNMEZ, her iki claim de CONTRADICTED'a döner,
    # çelişki UNRESOLVED olarak kaydedilir.
    for cid in payload.contradicts:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (other:Claim {id: $oid}) "
            "CREATE (c)-[:CLAIM_CONTRADICTS {status: 'UNRESOLVED', detected_at: $now}]->(other)",
            {"cid": claim_id, "oid": cid, "now": now},
        )
        other_result = _recompute_and_store(conn, cid)
        other_about_entity, other_about_event = _claim_about(conn, cid)
        _notify_change(
            conn,
            claim_id=cid,
            about_entity_id=other_about_entity,
            about_event_id=other_about_event,
            result=other_result,
            title="Var olan bir claim ile çelişki tespit edildi",
        )

    # Q9 temporal versiyonlama: eski claim silinmez, geçerliliği kapatılır.
    if payload.supersedes:
        _apply_supersede(conn, new_claim_id=claim_id, old_claim_id=payload.supersedes, new_valid_from=valid_from, now=now)

    final_result = _recompute_and_store(conn, claim_id)
    _notify_change(
        conn,
        claim_id=claim_id,
        about_entity_id=payload.about_entity_id,
        about_event_id=payload.about_event_id,
        result=final_result,
        title=f"Yeni claim: {claim_headline(payload.text)}",
    )
    safe_render_vault(conn)
    return get_claim(claim_id)


@router.get("", response_model=list[Claim])
def list_claims() -> list[Claim]:
    conn = get_connection()
    result = conn.execute(f"MATCH (c:Claim) RETURN {_FIELDS} ORDER BY c.created_at")
    return [_row_to_claim(conn, row) for row in fetch_all(result)]


@router.get("/corroboration/candidates", response_model=list[CorroborationCandidate])
def corroboration_candidates(
    claim_id: str | None = None, include_linked: bool = False, limit: int = 200
) -> list[CorroborationCandidate]:
    """Faz 17 — aynı olayı anlatıyor olabilecek claim çiftleri, gerekçeleriyle.

    Yol sırası önemli: `/{claim_id}`DAN ÖNCE tanımlanmalı, yoksa FastAPI "corroboration"ı bir
    claim id'si sanar (Faz 16'da `/observations/queue` ile aynı tuzak).

    Sonuç ÜÇ kategoriye ayrılıyor ve ikisi bağlanmamalı — bkz. `CorroborationCandidate`."""
    conn = get_connection()
    pairs = find_candidates(conn, claim_id=claim_id, include_linked=include_linked, limit=limit)
    return [
        CorroborationCandidate(
            claim_a=CandidateClaim(**{k: p.a[k] for k in _CANDIDATE_FIELDS}),
            claim_b=CandidateClaim(**{k: p.b[k] for k in _CANDIDATE_FIELDS}),
            kind=p.kind,
            rare_overlap=p.rare_overlap,
            text_similarity=p.text_similarity,
            days_apart=p.days_apart,
            shared_terms=p.shared_terms,
            reasons=p.reasons,
            projected_a=p.projected_a,
            projected_b=p.projected_b,
        )
        for p in pairs
    ]


@router.get(
    "/corroboration/observation-candidates",
    response_model=list[ObservationCorroborationCandidate],
)
def observation_corroboration_candidates(
    claim_id: str | None = None,
    include_corroborated: bool = False,
    include_dismissed: bool = True,
    limit: int = 200,
) -> list[ObservationCorroborationCandidate]:
    """Faz 28 — doğrulayanı olmayan claim'leri doğrulayabilecek HAM GÖZLEMLER.

    Faz 17'nin ekranı claim ↔ claim çalışıyor ve ikinci claim'in zaten var olmasını
    gerektiriyor; ölçüm 55 claim'in 30'unda doğrulayan olmadığını, Faz 24'ün eklediği dört
    yeni kaynağın ise toplam 1 claim ürettiğini gösterdi. Eksik olan ters yönlü aramaydı.

    Bağlamak burada bir kenar çekmek değil, gözlemi PROMOTE etmek demek — sonuç grafta yeni
    bir claim. Bu yüzden uç yalnızca öneriyor; promote kararı `POST /observations/{id}/promote`
    üzerinden ve insanda kalıyor (Design Principle #7)."""
    conn = get_connection()
    found = find_observation_candidates(
        conn, claim_id=claim_id, include_corroborated=include_corroborated,
        include_dismissed=include_dismissed, limit=limit,
    )
    return [
        ObservationCorroborationCandidate(
            claim_id=c.claim["id"],
            claim_text=c.claim["text"],
            claim_source_name=c.claim["source_name"],
            claim_confidence=c.claim["confidence"],
            claim_knowledge_state=c.claim["knowledge_state"],
            claim_about_entity_id=c.claim.get("about_entity_id"),
            claim_about_event_id=c.claim.get("about_event_id"),
            observation_id=c.observation["id"],
            observation_text=c.observation["raw_content"],
            observation_url=c.observation["source_url"],
            observation_host=c.observation["host"],
            observation_dismissed=c.observation["dismissed"],
            kind=c.kind,
            rare_overlap=c.rare_overlap,
            text_similarity=c.text_similarity,
            days_apart=c.days_apart,
            shared_terms=c.shared_terms,
            reasons=c.reasons,
            suggested_source_id=c.suggested_source_id,
            suggested_source_name=c.suggested_source_name,
            projected_confidence=c.projected_confidence,
        )
        for c in found
    ]


def _link_corroborates(conn, a_id: str, b_id: str) -> None:
    """Q4: corroboration SİMETRİK bir ilişki — bağımsız iki claim aynı şeyi doğruluyorsa ikisi
    de birbirini destekler, bu yüzden kenar her iki yönde de kuruluyor.

    (Çelişkiden farkı: `CLAIM_CONTRADICTS` tek yön saklanıyor çünkü okuma tarafı hem gelen hem
    giden kenara bakıyor ve iki yön yazmak çift sayıma yol açardı. `_gather_confidence_inputs`
    corroboration'ı yalnızca GELEN yönde okuduğu için burada iki yön ŞART.)"""
    conn.execute(
        "MATCH (a:Claim {id: $a}), (b:Claim {id: $b}) "
        "CREATE (a)-[:CORROBORATES]->(b) CREATE (b)-[:CORROBORATES]->(a)",
        {"a": a_id, "b": b_id},
    )


def _already_linked(conn, a_id: str, b_id: str) -> str | None:
    for query, label in (
        ("MATCH (a:Claim {id: $a})-[:CORROBORATES]->(b:Claim {id: $b}) RETURN 1 AS x", "CORROBORATES"),
        ("MATCH (a:Claim {id: $b})-[:CORROBORATES]->(b:Claim {id: $a}) RETURN 1 AS x", "CORROBORATES"),
        ("MATCH (a:Claim {id: $a})-[:CLAIM_CONTRADICTS]->(b:Claim {id: $b}) RETURN 1 AS x", "CONTRADICTS"),
        ("MATCH (a:Claim {id: $b})-[:CLAIM_CONTRADICTS]->(b:Claim {id: $a}) RETURN 1 AS x", "CONTRADICTS"),
    ):
        if fetch_one(conn.execute(query, {"a": a_id, "b": b_id})):
            return label
    return None


@router.post("/links-batch", response_model=ClaimLinkBatchResult)
def link_claims_batch(payload: ClaimLinkBatch) -> ClaimLinkBatchResult:
    """Faz 17 — seçilen claim çiftlerini toplu olarak birbirine bağlar.

    Doğrulama ve çelişki AYNI uçtan: aynı olayı anlatan iki claim birbirini doğrulayabileceği
    gibi çelişebilir de, ve ikisi de aynı aday listesinden çıkıyor. Ayrı uçlar/ekranlar
    olsaydı kullanıcı aynı çifti iki kez bulmak zorunda kalırdı.

    Faz 16'nın toplu promote'undan alınan iki ders burada da geçerli: kısmi başarısızlık
    diğerlerini durdurmuyor ve her çiftin ne olduğu sebebiyle dönüyor; vault BİR kez, sonda
    render ediliyor."""
    conn = get_connection()
    results: list[ClaimLinkResult] = []
    changed = False

    for pair in payload.pairs:
        a_id, b_id, link = pair.claim_a_id, pair.claim_b_id, pair.link.upper()

        def skip(message: str) -> None:
            results.append(
                ClaimLinkResult(claim_a_id=a_id, claim_b_id=b_id, link=link, status="SKIPPED", message=message)
            )

        if link not in ("CORROBORATES", "CONTRADICTS"):
            skip(f"Bilinmeyen bağ türü: {pair.link}")
            continue
        if a_id == b_id:
            skip("Bir claim kendisiyle bağlanamaz")
            continue
        if not _node_exists(conn, "Claim", a_id) or not _node_exists(conn, "Claim", b_id):
            skip("Claim bulunamadı")
            continue
        existing = _already_linked(conn, a_id, b_id)
        if existing:
            skip(f"Bu iki claim arasında zaten bir {existing} bağı var")
            continue

        # Q6 — bağımsızlık bir NEZAKET KONTROLÜ DEĞİL, bu fazın varlık sebebi. Aynı bağımsız
        # köke inen iki claim birbirini doğruladığında confidence SAHTE yükselirdi: kullanıcı
        # aday listesinde uyarıyı görse bile API'nin bunu kabul etmesi, arayüzün dışından
        # gelen her çağrıda aynı hatayı mümkün kılardı. Çelişki için böyle bir kısıt YOK —
        # aynı kaynak kendi kendisiyle pekâlâ çelişebilir (ve bu değerli bir sinyaldir).
        if link == "CORROBORATES":
            source_a = _claim_source_id(conn, a_id)
            source_b = _claim_source_id(conn, b_id)
            if source_a and source_b:
                root_a = resolve_independent_root(conn, source_a["id"])
                root_b = resolve_independent_root(conn, source_b["id"])
                if root_a == root_b:
                    skip(
                        "İki claim aynı bağımsız kaynağa iniyor — doğrulama bağı kurulmadı. "
                        "Bağımsız olmayan bir doğrulama confidence'ı sahte yükseltirdi (Q6). "
                        "Aynı haberin iki kaydıysa biri supersede edilmeli."
                    )
                    continue

        before = {
            a_id: _gather_confidence_inputs(conn, a_id).confidence,
            b_id: _gather_confidence_inputs(conn, b_id).confidence,
        }

        if link == "CORROBORATES":
            _link_corroborates(conn, a_id, b_id)
            titles = ("Claim bağımsız olarak doğrulandı", "Claim bağımsız olarak doğrulandı")
        else:
            # Çelişki tek yön saklanıyor (bkz. add_claim_contradiction) — anlamı simetrik ama
            # okuma tarafı iki yöne de bakıyor, iki yön yazmak çift sayım olurdu.
            conn.execute(
                "MATCH (a:Claim {id: $a}), (b:Claim {id: $b}) "
                "CREATE (a)-[:CLAIM_CONTRADICTS {status: 'UNRESOLVED', detected_at: $now}]->(b)",
                {"a": a_id, "b": b_id, "now": datetime.now(timezone.utc)},
            )
            titles = ("Claim çelişkili olarak işaretlendi", "Var olan bir claim ile çelişki tespit edildi")

        after: dict[str, float] = {}
        state: dict[str, str] = {}
        for cid, title in ((a_id, titles[0]), (b_id, titles[1])):
            result = _recompute_and_store(conn, cid)
            after[cid] = result.confidence
            state[cid] = result.knowledge_state
            about_entity, about_event = _claim_about(conn, cid)
            _notify_change(
                conn,
                claim_id=cid,
                about_entity_id=about_entity,
                about_event_id=about_event,
                result=result,
                title=title,
            )

        changed = True
        results.append(
            ClaimLinkResult(
                claim_a_id=a_id, claim_b_id=b_id, link=link, status="LINKED",
                confidence_before=before, confidence_after=after, state_after=state,
            )
        )

    if changed:
        safe_render_vault(conn)

    return ClaimLinkBatchResult(
        linked=sum(1 for r in results if r.status == "LINKED"),
        skipped=sum(1 for r in results if r.status == "SKIPPED"),
        results=results,
    )


@router.get("/{claim_id}", response_model=Claim)
def get_claim(claim_id: str) -> Claim:
    conn = get_connection()
    result = conn.execute(f"MATCH (c:Claim {{id: $id}}) RETURN {_FIELDS}", {"id": claim_id})
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return _row_to_claim(conn, row)


def _corroborating_claims(conn, claim_id: str) -> list[dict]:
    """Bu claim'i hangi claim'ler, hangi kaynaklardan doğruluyor.

    `counts_for_independence` alanı kritik: Q6 gereği aynı DERIVED_FROM köküne inen iki
    kaynak TEK bağımsız kaynak sayılır. Liste bunu göstermeseydi, kullanıcı "4 claim
    doğruluyor ama independence neden 0.5?" sorusuna cevap bulamazdı — yani skorun kaynağını
    göstermek, tek başına yeni bir açıklanamazlık üretirdi."""
    own_source = _claim_source_id(conn, claim_id)
    own_root = resolve_independent_root(conn, own_source["id"]) if own_source else None
    rows = fetch_all(
        conn.execute(
            "MATCH (s:Source)-[:ASSERTS]->(other:Claim)-[:CORROBORATES]->(c:Claim {id: $id}) "
            "RETURN DISTINCT other.id AS claim_id, other.text AS text, "
            "other.knowledge_state AS knowledge_state, other.confidence AS confidence, "
            "s.id AS source_id, s.name AS source_name",
            {"id": claim_id},
        )
    )
    seen_roots: set[str] = set()
    if own_root:
        seen_roots.add(own_root)
    out = []
    for row in rows:
        root = resolve_independent_root(conn, row["source_id"])
        counts = root not in seen_roots
        seen_roots.add(root)
        out.append({**row, "independent_root_id": root, "counts_for_independence": counts})
    return out


def _supporting_evidence(conn, claim_id: str) -> list[dict]:
    """Kanıt alt-skorunun KAYNAĞI. Faz 18'in corroboration için kapattığı boşluğun aynısı:
    Faz 26'ya kadar kanıt skoru 55 claim'in 54'ünde sıfırdı, yani gösterilecek bir şey yoktu.
    Artık sıfır olmadığına göre "hangi kanıt" sorusunun da bir cevabı olmalı — yoksa skor
    yükseldi ama açıklanabilirliği düştü olurdu.

    Arşiv kayıtları TÜRÜYLE ayrışıyor: bir arşivin skora girmesi doğrulanmış olmasına bağlı
    ve kullanıcı hangisinin ne olduğunu görmeden "kanıt 0.33" satırına güvenemez."""
    return fetch_all(
        conn.execute(
            "MATCH (ev:Evidence)-[:SUPPORTS]->(c:Claim {id: $id}) "
            "RETURN ev.id AS evidence_id, ev.evidence_type AS evidence_type, "
            "ev.archive_status AS archive_status, ev.archive_url AS archive_url, "
            "ev.content_hash AS content_hash",
            {"id": claim_id},
        )
    )


@router.get("/{claim_id}/explain")
def explain_claim(claim_id: str) -> dict:
    """Auditability: 'Sistem bunu neden düşünüyor?' — confidence'ın alt-skor kırılımı."""
    conn = get_connection()
    if not _node_exists(conn, "Claim", claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    result = _gather_confidence_inputs(conn, claim_id)
    return {
        "claim_id": claim_id,
        "source_quality": result.source_quality,
        "independence": result.independence,
        "evidence": result.evidence,
        "corroboration": result.corroboration,
        "confidence": result.confidence,
        "knowledge_state": result.knowledge_state,
        "weights": {
            "source_quality": 0.40,
            "independence": 0.25,
            "evidence": 0.20,
            "corroboration": 0.15,
        },
        # Faz 18 yan onarımı: skor vardı, skorun KAYNAĞI yoktu. "Neden bu confidence?"
        # sorusunun cevabı "corroboration 0.67" değil, "şu üç claim şu kaynaklardan
        # doğruluyor" — Auditability'nin (Q4) eksik yarısı buydu. Olay kümelerini
        # hesaplarken de aday-uçları farkını almak gibi dolambaçlı bir yol gerekmişti.
        "corroborated_by": _corroborating_claims(conn, claim_id),
        # Faz 26: kanıt artık gerçekten var, dolayısıyla kaynağı da gösteriliyor.
        "evidence_from": _supporting_evidence(conn, claim_id),
    }


@router.get("/{claim_id}/why-matters")
def claim_why_matters(claim_id: str) -> dict:
    """Q12: kural + graph tabanlı 'neden önemli' gerekçesi. AI bu listeyi akıcı cümleye
    çevirebilir (bkz. .claude/skills/osint-brain/) ama karar mantığı burada, deterministik."""
    conn = get_connection()
    row = fetch_one(conn.execute(f"MATCH (c:Claim {{id: $id}}) RETURN {_FIELDS}", {"id": claim_id}))
    if row is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    confidence_result = _gather_confidence_inputs(conn, claim_id)
    about_entity_id, about_event_id = _claim_about(conn, claim_id)
    reasons = why_matters(conn, claim_id, row, confidence_result, about_entity_id, about_event_id)
    return {"claim_id": claim_id, "reasons": reasons}


@router.patch("/{claim_id}/about", response_model=Claim)
def update_claim_about(claim_id: str, payload: ClaimAboutUpdate) -> Claim:
    """Faz 11 (F16): claim'in ABOUT_ENTITY/ABOUT_EVENT bağını düzeltir.

    Bir claim aynı anda hem bir entity hem bir event hakkında olamaz; ikisi de boş
    bırakılırsa bağ tamamen kaldırılır (claim silinmez — History Is Immutable)."""
    conn = get_connection()
    if not _node_exists(conn, "Claim", claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    if payload.about_entity_id and payload.about_event_id:
        raise HTTPException(
            status_code=422, detail="Bir claim ya bir entity ya da bir event hakkında olabilir, ikisi birden değil"
        )
    if payload.about_entity_id and not _node_exists(conn, "Entity", payload.about_entity_id):
        raise HTTPException(status_code=404, detail=f"Entity not found: {payload.about_entity_id}")
    if payload.about_event_id and not _node_exists(conn, "Event", payload.about_event_id):
        raise HTTPException(status_code=404, detail=f"Event not found: {payload.about_event_id}")

    # Faz 18: bir olayın confidence'ı claim'lerinden türetiliyor, dolayısıyla claim ESKİ
    # olayından koparken de yeni olayına bağlanırken de iki olayın da yeniden hesaplanması
    # gerekir — yoksa boşalan bir olay eski (yüksek) skorunu göstermeye devam ederdi.
    previous_event = fetch_one(
        conn.execute(
            "MATCH (c:Claim {id: $id})-[:ABOUT_EVENT]->(ev:Event) RETURN ev.id AS id", {"id": claim_id}
        )
    )
    conn.execute("MATCH (c:Claim {id: $id})-[r:ABOUT_ENTITY]->(:Entity) DELETE r", {"id": claim_id})
    conn.execute("MATCH (c:Claim {id: $id})-[r:ABOUT_EVENT]->(:Event) DELETE r", {"id": claim_id})

    if payload.about_entity_id:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (e:Entity {id: $eid}) CREATE (c)-[:ABOUT_ENTITY]->(e)",
            {"cid": claim_id, "eid": payload.about_entity_id},
        )
    if payload.about_event_id:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (e:Event {id: $eid}) CREATE (c)-[:ABOUT_EVENT]->(e)",
            {"cid": claim_id, "eid": payload.about_event_id},
        )
    conn.execute(
        "MATCH (c:Claim {id: $id}) SET c.updated_at = $now",
        {"id": claim_id, "now": datetime.now(timezone.utc)},
    )
    for affected in {previous_event["id"] if previous_event else None, payload.about_event_id} - {None}:
        recompute_event_confidence(conn, affected)
    safe_render_vault(conn)
    return get_claim(claim_id)


@router.post("/{claim_id}/contradicts", response_model=Claim)
def add_claim_contradiction(claim_id: str, payload: ClaimContradictionAdd) -> Claim:
    """Faz 11 (F26): var olan iki claim arasına sonradan çelişki ilişkisi kurar.

    Neden ayrı bir uç: çelişki şimdiye kadar SADECE `POST /claims` gövdesinde kurulabiliyordu,
    ama toplanan veriden gelen claim'lerin tamamı promote üzerinden yaratılıyor ve gerçek
    araştırma bu sırayla ilerlemiyor — çelişen ikinci haber ilk claim kaydedildikten sonra
    çıkıyor. Bu uç olmadan confidence.py'nin çelişki dalı gerçek boru hattında hiç
    tetiklenemiyordu.

    Çelişki simetriktir ama graf'ta tek yön saklanır: okuma tarafı (`_gather_confidence_inputs`)
    zaten hem gelen hem giden kenara bakıyor, iki yön birden yazmak çift sayıma yol açardı."""
    conn = get_connection()
    if not _node_exists(conn, "Claim", claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    if not _node_exists(conn, "Claim", payload.other_claim_id):
        raise HTTPException(status_code=404, detail=f"Claim not found: {payload.other_claim_id}")
    if claim_id == payload.other_claim_id:
        raise HTTPException(status_code=422, detail="Bir claim kendisiyle çelişemez")

    # Her iki yön de kontrol edilir (ilişki tek yön saklanıyor ama anlamı simetrik).
    existing = None
    for a, b in ((claim_id, payload.other_claim_id), (payload.other_claim_id, claim_id)):
        existing = fetch_one(
            conn.execute(
                "MATCH (a:Claim {id: $a})-[r:CLAIM_CONTRADICTS]->(b:Claim {id: $b}) "
                "RETURN r.status AS status",
                {"a": a, "b": b},
            )
        )
        if existing:
            break
    if existing:
        raise HTTPException(status_code=409, detail="Bu iki claim arasında zaten bir çelişki kaydı var")

    now = datetime.now(timezone.utc)
    conn.execute(
        "MATCH (a:Claim {id: $a}), (b:Claim {id: $b}) "
        "CREATE (a)-[:CLAIM_CONTRADICTS {status: 'UNRESOLVED', detected_at: $now}]->(b)",
        {"a": claim_id, "b": payload.other_claim_id, "now": now},
    )

    # İKİ claim de yeniden hesaplanır: çelişki her ikisinin de knowledge_state'ini
    # CONTRADICTED'a çeker (bkz. confidence.py) — tek taraflı bırakmak grafı tutarsız yapardı.
    for cid, title in (
        (claim_id, "Claim çelişkili olarak işaretlendi"),
        (payload.other_claim_id, "Var olan bir claim ile çelişki tespit edildi"),
    ):
        result = _recompute_and_store(conn, cid)
        about_entity, about_event = _claim_about(conn, cid)
        _notify_change(
            conn,
            claim_id=cid,
            about_entity_id=about_entity,
            about_event_id=about_event,
            result=result,
            title=title,
        )

    safe_render_vault(conn)
    return get_claim(claim_id)


def _apply_supersede(conn, *, new_claim_id: str, old_claim_id: str, new_valid_from, now) -> None:
    """Eski claim'in geçerliliğini kapatır ve SUPERSEDES kenarını kurar.

    Faz 11 (dogfooding F44): eskiden `old.valid_to = now` yazılıyordu — yani KAYIT anı.
    Doğrusu yeni claim'in `valid_from`'u, yani iddianın geçerli olmaya BAŞLADIĞI an: eski
    bilgi, yenisi yürürlüğe girdiğinde sona erer, biz onu kaydettiğimizde değil. Arşivden
    bir Ağustos haberi bugün promote edilip eski bir claim'i supersede ettiğinde, eskisinin
    geçerliliği bugün kapanıyordu. Bu, F1/F12'nin (yayın tarihi vs kayıt anı) aynı alan
    çiftinin diğer ucundaki tekrarıdır.

    `at` kenar özelliği KAYIT anı olarak kalır — "bu ilişkiyi ne zaman kurduk" ayrı bir soru
    ve denetlenebilirlik için gerekli."""
    conn.execute(
        "MATCH (c:Claim {id: $cid}), (old:Claim {id: $oid}) "
        "CREATE (c)-[:SUPERSEDES {at: $now}]->(old)",
        {"cid": new_claim_id, "oid": old_claim_id, "now": now},
    )
    conn.execute(
        "MATCH (old:Claim {id: $oid}) SET old.valid_to = $valid_to, old.updated_at = $now",
        {"oid": old_claim_id, "valid_to": new_valid_from, "now": now},
    )


@router.post("/{claim_id}/supersedes", response_model=Claim)
def add_claim_supersede(claim_id: str, payload: ClaimSupersedeAdd) -> Claim:
    """Faz 11 (F45): var olan bir claim'in, var olan başka bir claim'in yerini aldığını
    sonradan bildirir.

    F26'da bilerek ertelenmişti ("hangi an" bir modelleme sorusu). Oturum 4'te gerçek bir
    engel oldu: veride gerçek bir supersede vardı (OpenAI Ağustos'ta eşiği "dışlayamıyoruz"
    diyor, 1 Eylül'de doğruluyor) ama Eylül claim'i graf'ta ZATEN vardı — promote sırasında
    beyan etmeyi şart koşan tasarım, gerçek araştırma sırasına uymuyor. Aynı ders altıncı
    kez (F16, F23b, F26, F29, F38, bu).

    "Hangi an" sorusu F44 ile çözüldü: eski claim'in valid_to'su, yeni claim'in valid_from'u."""
    conn = get_connection()
    yeni = fetch_one(
        conn.execute(f"MATCH (c:Claim {{id: $id}}) RETURN {_FIELDS}", {"id": claim_id})
    )
    if yeni is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    eski = fetch_one(
        conn.execute(f"MATCH (c:Claim {{id: $id}}) RETURN {_FIELDS}", {"id": payload.supersedes_claim_id})
    )
    if eski is None:
        raise HTTPException(status_code=404, detail=f"Claim not found: {payload.supersedes_claim_id}")
    if claim_id == payload.supersedes_claim_id:
        raise HTTPException(status_code=422, detail="Bir claim kendi yerini alamaz")

    mevcut = fetch_one(
        conn.execute(
            "MATCH (a:Claim)-[:SUPERSEDES]->(b:Claim {id: $oid}) RETURN a.id AS id",
            {"oid": payload.supersedes_claim_id},
        )
    )
    if mevcut:
        raise HTTPException(
            status_code=409,
            detail=f"Bu claim'in yerini zaten başka bir claim almış (claim {mevcut['id'][:8]}…)",
        )

    # Zaman çizgisi tersine dönmesin: yerini alan bilgi, aldığı bilgiden önce başlayamaz.
    if yeni["valid_from"] < eski["valid_from"]:
        raise HTTPException(
            status_code=422,
            detail=(
                "Yerini alan claim daha ESKİ bir tarihte geçerli olmaya başlıyor "
                f"({yeni['valid_from']} < {eski['valid_from']}) — zaman çizgisi tersine dönerdi. "
                "Yön yanlış olabilir: hangisi yenisi?"
            ),
        )

    now = datetime.now(timezone.utc)
    _apply_supersede(
        conn,
        new_claim_id=claim_id,
        old_claim_id=payload.supersedes_claim_id,
        new_valid_from=yeni["valid_from"],
        now=now,
    )
    safe_render_vault(conn)
    return get_claim(claim_id)


# ---- Faz 21: Claim'in değdiği entity'ler (MENTIONS) -----------------------------------------
#
# DİKKAT: bu rotalar `/{claim_id}`den ÖNCE eşleşmeli. `claims.router` prefix'i `/claims`
# olduğu ve `/{claim_id}` yukarıda tanımlı olduğu için ayrı bir router kullanılıyor —
# `entities.same_as_router` ile aynı desen. main.py bunu claims.router'dan önce include eder.


@mentions_router.get("/candidates", response_model=list[ClaimMentionGroup])
def list_mention_candidates() -> list[ClaimMentionGroup]:
    """Faz 21 — claim metninde adı geçen ama bağı olmayan entity'ler (bkz. app/mentions.py).

    Yeni bir sinyal üretmez: Faz 12'den beri var olan entity eşleştiricisini claim eksenine
    taşır. Öneridir — metinde adın geçmesi, claim'in o entity hakkında bir şey söylediği
    anlamına gelmez (Design Principle #7)."""
    conn = get_connection()
    return [ClaimMentionGroup(**g) for g in mention_candidates(conn)]


@mentions_router.post("/batch", response_model=MentionBatchResult)
def decide_mentions(payload: MentionBatch) -> MentionBatchResult:
    """Toplu onay/ret. Reddedilen çift SİLİNMEZ, `REJECTED` olarak işaretlenir — yoksa aynı
    öneri bir sonraki aday hesabında geri gelirdi (Faz 20'nin EntityCandidate kararı)."""
    conn = get_connection()
    confirmed = rejected = 0
    for decision in payload.decisions:
        action = decision.action.upper()
        if action not in ("CONFIRM", "REJECT"):
            raise HTTPException(status_code=422, detail=f"Geçersiz aksiyon: {decision.action}")
        if not _node_exists(conn, "Claim", decision.claim_id):
            raise HTTPException(status_code=404, detail=f"Claim not found: {decision.claim_id}")
        if not _node_exists(conn, "Entity", decision.entity_id):
            raise HTTPException(status_code=404, detail=f"Entity not found: {decision.entity_id}")
        status = "CONFIRMED" if action == "CONFIRM" else "REJECTED"
        set_mention(conn, decision.claim_id, decision.entity_id, status, decision.matched_on)
        if status == "CONFIRMED":
            confirmed += 1
        else:
            rejected += 1
    safe_render_vault(conn)
    return MentionBatchResult(confirmed=confirmed, rejected=rejected)


@router.get("/{claim_id}/mentions", response_model=list[ClaimMention])
def list_claim_mentions(claim_id: str) -> list[ClaimMention]:
    conn = get_connection()
    if not _node_exists(conn, "Claim", claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    return [ClaimMention(**row) for row in claim_mentions(conn, claim_id)]


@router.delete("/{claim_id}/mentions/{entity_id}", status_code=204)
def remove_claim_mention(claim_id: str, entity_id: str) -> None:
    """Onaylanmış bir değmeyi geri alır. Kenar silinmez, REJECTED'a çekilir: hem History Is
    Immutable ile tutarlı, hem de aday listesine geri düşmesini engeller."""
    conn = get_connection()
    if not _node_exists(conn, "Claim", claim_id):
        raise HTTPException(status_code=404, detail="Claim not found")
    set_mention(conn, claim_id, entity_id, "REJECTED")
    safe_render_vault(conn)
