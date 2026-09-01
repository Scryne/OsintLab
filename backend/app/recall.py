"""
OSINT Brain — Memory Recall + Why This Matters (Q12: kural + graph tabanlı, AI sadece yazım).

Bu modül LLM çağırmaz. Çıktısı yapılandırılmış, kaynağı her zaman gösterilebilen (Auditability)
gerekçelerdir. Akıcı/doğal dile çevirme işi Claude Code Agent katmanına (bkz.
.claude/skills/osint-brain/) bırakılır — SOURCE FACT/SYSTEM INFERENCE ayrımı burada korunur.
"""
from app.db import fetch_all


def entity_recall(conn, entity_id: str) -> dict:
    investigations = fetch_all(
        conn.execute(
            "MATCH (i:Investigation)-[:INCLUDES]->(e:Entity {id: $id}) "
            "RETURN i.id AS id, i.title AS title, i.status AS status, i.created_at AS created_at "
            "ORDER BY i.created_at",
            {"id": entity_id},
        )
    )
    claims = fetch_all(
        conn.execute(
            "MATCH (c:Claim)-[:ABOUT_ENTITY]->(e:Entity {id: $id}) "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence, c.created_at AS created_at ORDER BY c.created_at",
            {"id": entity_id},
        )
    )
    events = fetch_all(
        conn.execute(
            "MATCH (e:Entity {id: $id})-[:INVOLVED_IN]->(ev:Event) "
            "RETURN ev.id AS id, ev.title AS title, ev.event_type AS event_type, "
            "ev.created_at AS created_at ORDER BY ev.created_at",
            {"id": entity_id},
        )
    )
    return {"related_investigations": investigations, "related_claims": claims, "related_events": events}


def event_recall(conn, event_id: str) -> dict:
    investigations = fetch_all(
        conn.execute(
            "MATCH (i:Investigation)-[:INVESTIGATES]->(ev:Event {id: $id}) "
            "RETURN i.id AS id, i.title AS title, i.status AS status, i.created_at AS created_at "
            "ORDER BY i.created_at",
            {"id": event_id},
        )
    )
    claims = fetch_all(
        conn.execute(
            "MATCH (c:Claim)-[:ABOUT_EVENT]->(ev:Event {id: $id}) "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence, c.created_at AS created_at ORDER BY c.created_at",
            {"id": event_id},
        )
    )
    entities = fetch_all(
        conn.execute(
            "MATCH (e:Entity)-[:INVOLVED_IN]->(ev:Event {id: $id}) "
            "RETURN e.id AS id, e.name AS name, e.entity_type AS entity_type "
            "ORDER BY e.name",
            {"id": event_id},
        )
    )
    return {"related_investigations": investigations, "related_claims": claims, "related_entities": entities}


def why_matters(conn, claim_id: str, claim_row: dict, confidence_result, about_entity_id: str | None, about_event_id: str | None) -> list[dict]:
    """Yapılandırılmış gerekçe listesi. Her reason: {code, text, detail}."""
    reasons: list[dict] = []

    if confidence_result.independence >= 0.5:
        n = round(confidence_result.independence * 2)  # INDEPENDENCE_SATURATION = 2
        reasons.append({
            "code": "INDEPENDENT_SOURCES",
            "text": f"En az {n} bağımsız kaynak tarafından destekleniyor.",
            "detail": {"independence_score": confidence_result.independence},
        })

    if confidence_result.corroboration > 0:
        reasons.append({
            "code": "CORROBORATED",
            "text": "Başka claim'ler tarafından bağımsız olarak doğrulanıyor.",
            "detail": {"corroboration_score": confidence_result.corroboration},
        })

    if confidence_result.knowledge_state == "CONTRADICTED":
        reasons.append({
            "code": "CONTRADICTED",
            "text": "Bu bilgi başka bir claim ile çelişiyor, çözülmemiş.",
            "detail": {},
        })

    recall = None
    if about_entity_id:
        recall = entity_recall(conn, about_entity_id)
    elif about_event_id:
        recall = event_recall(conn, about_event_id)

    if recall:
        active_investigations = [
            i for i in recall["related_investigations"] if i["status"] in ("OPEN", "ACTIVE", "PAUSED")
        ]
        if active_investigations:
            titles = ", ".join(f"\"{i['title']}\" ({i['status']})" for i in active_investigations)
            reasons.append({
                "code": "ACTIVE_INVESTIGATION",
                "text": f"İlgili entity/event aktif bir investigation'da yer alıyor: {titles}.",
                "detail": {"investigation_ids": [i["id"] for i in active_investigations]},
            })

        resolved_investigations = [
            i for i in recall["related_investigations"] if i["status"] in ("RESOLVED", "CLOSED", "ARCHIVED")
        ]
        if resolved_investigations:
            titles = ", ".join(f"\"{i['title']}\"" for i in resolved_investigations)
            reasons.append({
                "code": "PAST_INVESTIGATION_RELEVANCE",
                "text": f"Bu gelişme daha önce yürütülen bir investigation ile ilişkili olabilir: {titles}.",
                "detail": {"investigation_ids": [i["id"] for i in resolved_investigations]},
            })

        prior_claims = [c for c in recall["related_claims"] if c["id"] != claim_id]
        if not prior_claims:
            reasons.append({
                "code": "NEWLY_DISCOVERED",
                "text": "Bu entity/event hakkında daha önce bilgi yoktu — yeni keşfedildi.",
                "detail": {},
            })
        else:
            reasons.append({
                "code": "PRIOR_KNOWLEDGE_EXISTS",
                "text": f"Bu entity/event hakkında zaten {len(prior_claims)} bilinen claim var.",
                "detail": {"prior_claim_ids": [c["id"] for c in prior_claims]},
            })

    if not reasons:
        reasons.append({
            "code": "LOW_SIGNAL",
            "text": "Tek kaynaklı, doğrulanmamış, bilinen bir bağlamı yok.",
            "detail": {},
        })

    return reasons
