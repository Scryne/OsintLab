import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.db import fetch_all, fetch_one, get_connection
from app.models import Claim, ClaimCreate, Observation, ObservationCreate, ObservationPromote
from app.recall import entity_recall, event_recall
from app.recall import why_matters as compute_why_matters
from app.routers.claims import _claim_about, _gather_confidence_inputs, create_claim, get_claim

router = APIRouter(prefix="/observations", tags=["observations"])

_FIELDS = (
    "o.id AS id, o.raw_content AS raw_content, o.observed_at AS observed_at, "
    "o.promoted AS promoted, o.source_url AS source_url, o.created_at AS created_at"
)

DAILY_LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "daily"

# Q1/Q8: Knowledge Graph'a promote edilmek için bir observation'dan türeyen claim'in
# ulaşması gereken minimum confidence eşiği. Altında kalan bilgi silinmez, sadece
# Observation olarak (promoted=false) ham log'da kalır.
PROMOTION_THRESHOLD = 0.45


def _append_daily_log(
    observation_id: str, raw_content: str, observed_at: datetime, created_at: datetime, source_url: str | None
) -> None:
    """AvenoxBeyin'in daily/ katmanına paralel: her observation, değiştirilemez (append-only)
    bir JSONL günlük dosyasına da düşer — Knowledge Graph'tan bağımsız, kalıcı bir ham kayıt."""
    DAILY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = DAILY_LOG_DIR / f"{created_at.date().isoformat()}.jsonl"
    entry = {
        "id": observation_id,
        "raw_content": raw_content,
        "observed_at": observed_at.isoformat(),
        "source_url": source_url,
        "created_at": created_at.isoformat(),
    }
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def create_observation_record(raw_content: str, observed_at: datetime | None = None, source_url: str | None = None) -> Observation:
    """create_observation'ın altındaki paylaşılan mantık — collector router'ı da bunu kullanır."""
    conn = get_connection()
    observation_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    observed_at = observed_at or created_at
    conn.execute(
        "CREATE (:Observation {id: $id, raw_content: $raw_content, observed_at: $observed_at, "
        "promoted: false, source_url: $source_url, created_at: $created_at})",
        {
            "id": observation_id,
            "raw_content": raw_content,
            "observed_at": observed_at,
            "source_url": source_url,
            "created_at": created_at,
        },
    )
    _append_daily_log(observation_id, raw_content, observed_at, created_at, source_url)
    return Observation(
        id=observation_id, promoted=False, created_at=created_at,
        raw_content=raw_content, observed_at=observed_at, source_url=source_url,
    )


@router.post("", response_model=Observation, status_code=201)
def create_observation(payload: ObservationCreate) -> Observation:
    return create_observation_record(payload.raw_content, payload.observed_at, payload.source_url)


@router.get("", response_model=list[Observation])
def list_observations(promoted: bool | None = None) -> list[Observation]:
    conn = get_connection()
    if promoted is None:
        result = conn.execute(f"MATCH (o:Observation) RETURN {_FIELDS} ORDER BY o.created_at")
    else:
        result = conn.execute(
            f"MATCH (o:Observation {{promoted: $promoted}}) RETURN {_FIELDS} ORDER BY o.created_at",
            {"promoted": promoted},
        )
    return [Observation(**row) for row in fetch_all(result)]


@router.get("/{observation_id}", response_model=Observation)
def get_observation(observation_id: str) -> Observation:
    conn = get_connection()
    result = conn.execute(f"MATCH (o:Observation {{id: $id}}) RETURN {_FIELDS}", {"id": observation_id})
    row = fetch_one(result)
    if row is None:
        raise HTTPException(status_code=404, detail="Observation not found")
    return Observation(**row)


@router.post("/{observation_id}/promote")
def promote_observation(observation_id: str, payload: ObservationPromote) -> dict:
    """Q1/Q8: ham observation değerlendirilir; deterministik confidence formülü eşiği
    (PROMOTION_THRESHOLD) geçerse Knowledge Graph'a (Claim olarak) yükselir ve
    observation.promoted=true işaretlenir. Geçmezse Observation ham haliyle kalır — silinmez.

    Faz 4 — OSINT Brain Memory Recall: about_entity_id/about_event_id verildiyse, YENİ claim
    oluşturulmadan ÖNCEKİ bilgi durumu ('daha önce ne biliyorduk') otomatik olarak dönülür,
    böylece kullanıcı/agent ayrı bir çağrı yapmak zorunda kalmadan geçmiş investigation/claim
    bağlamını görür (Research Relevance Recall dahil — investigation status'u ne olursa olsun
    listelenir)."""
    conn = get_connection()
    observation = get_observation(observation_id)
    # observation.promoted sadece eşiği GEÇEN durumu işaretliyor — eşiği geçmeyen bir
    # observation'ı tekrar promote etmeye çalışmak (promoted hâlâ false) bu kontrolü
    # atlayıp ikinci bir Claim daha üretebilirdi (idempotent değildi). Asıl garanti bu
    # observation'ın zaten bir PRODUCED ilişkisi olup olmadığı — eşiği geçse de geçmese de.
    already_produced = fetch_one(
        conn.execute(
            "MATCH (:Observation {id: $oid})-[:PRODUCED]->(c:Claim) RETURN c.id AS id",
            {"oid": observation_id},
        )
    )
    if already_produced:
        raise HTTPException(status_code=409, detail="Observation already processed (claim already produced)")

    recall_before: dict | None = None
    if payload.about_entity_id:
        recall_before = {"about": "entity", "id": payload.about_entity_id, **entity_recall(conn, payload.about_entity_id)}
    elif payload.about_event_id:
        recall_before = {"about": "event", "id": payload.about_event_id, **event_recall(conn, payload.about_event_id)}

    claim = create_claim(
        ClaimCreate(
            text=observation.raw_content,
            source_id=payload.source_id,
            about_entity_id=payload.about_entity_id,
            about_event_id=payload.about_event_id,
            evidence_ids=payload.evidence_ids,
            contradicting_evidence_ids=payload.contradicting_evidence_ids,
            corroborates=payload.corroborates,
        )
    )

    if claim.confidence >= PROMOTION_THRESHOLD:
        conn.execute(
            "MATCH (o:Observation {id: $oid}), (c:Claim {id: $cid}) "
            "SET o.promoted = true CREATE (o)-[:PRODUCED]->(c)",
            {"oid": observation_id, "cid": claim.id},
        )
    else:
        # Eşiği geçmedi: Claim yine de oluşturuldu (REPORTED gibi düşük bir state'te,
        # denetim/gelecekteki corroboration için erişilebilir) ama Observation
        # promoted=false kalır — Q1 katmanlı hafıza modeli.
        conn.execute(
            "MATCH (o:Observation {id: $oid}), (c:Claim {id: $cid}) CREATE (o)-[:PRODUCED]->(c)",
            {"oid": observation_id, "cid": claim.id},
        )

    final_claim = get_claim(claim.id)
    confidence_result = _gather_confidence_inputs(conn, claim.id)
    about_entity_id, about_event_id = _claim_about(conn, claim.id)
    reasons = compute_why_matters(conn, claim.id, {}, confidence_result, about_entity_id, about_event_id)

    return {
        "claim": final_claim.model_dump(mode="json"),
        "recall": recall_before,
        "why_matters": reasons,
    }
