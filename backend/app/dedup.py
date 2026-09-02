"""
Entity dedup / SAME_AS aday tespiti — Q7: asla otomatik merge yok, sadece öneri.

Heuristic: isim+alias'ların kelime kümesi üzerinde containment (Szymkiewicz–Simpson) —
app/lineage.py'de Q6 için doğrulanmış aynı yöntem (embedding gerektirmez, deterministik,
her zaman açıklanabilir). Sadece AYNI entity_type'taki entity'ler karşılaştırılır (bir
Person bir Organization'la asla aynı gerçek varlık olamaz).
"""
from dataclasses import dataclass

from app.db import fetch_all, fetch_one
from app.lineage import containment_similarity, normalize_text

SAME_AS_CANDIDATE_THRESHOLD = 0.5


def _token_set(name: str, aliases: list[str]) -> set[str]:
    tokens: set[str] = set()
    for text in [name, *aliases]:
        tokens |= set(normalize_text(text).split())
    return tokens


@dataclass
class SameAsCandidate:
    entity_id: str
    name: str
    entity_type: str
    score: float


def find_candidates(conn, entity_id: str, *, threshold: float = SAME_AS_CANDIDATE_THRESHOLD) -> list[SameAsCandidate]:
    target = fetch_one(
        conn.execute(
            "MATCH (e:Entity {id: $id}) RETURN e.name AS name, e.entity_type AS entity_type, e.aliases AS aliases",
            {"id": entity_id},
        )
    )
    if target is None:
        return []
    target_tokens = _token_set(target["name"], target["aliases"] or [])
    others = fetch_all(
        conn.execute(
            "MATCH (e:Entity) WHERE e.id <> $id AND e.entity_type = $et "
            "RETURN e.id AS id, e.name AS name, e.entity_type AS entity_type, e.aliases AS aliases",
            {"id": entity_id, "et": target["entity_type"]},
        )
    )
    candidates = []
    for row in others:
        score = containment_similarity(target_tokens, _token_set(row["name"], row["aliases"] or []))
        if score >= threshold:
            candidates.append(
                SameAsCandidate(entity_id=row["id"], name=row["name"], entity_type=row["entity_type"], score=round(score, 4))
            )
    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def pair_score(conn, a_id: str, b_id: str) -> float:
    a = fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.name AS name, e.aliases AS aliases", {"id": a_id}))
    b = fetch_one(conn.execute("MATCH (e:Entity {id: $id}) RETURN e.name AS name, e.aliases AS aliases", {"id": b_id}))
    return round(containment_similarity(_token_set(a["name"], a["aliases"] or []), _token_set(b["name"], b["aliases"] or [])), 4)
