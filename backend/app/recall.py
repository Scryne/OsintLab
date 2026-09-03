"""
OSINT Brain — Memory Recall + Why This Matters (Q12: kural + graph tabanlı, AI sadece yazım).

Bu modül LLM çağırmaz. Çıktısı yapılandırılmış, kaynağı her zaman gösterilebilen (Auditability)
gerekçelerdir. Akıcı/doğal dile çevirme işi Claude Code Agent katmanına (bkz.
.claude/skills/osint-brain/) bırakılır — SOURCE FACT/SYSTEM INFERENCE ayrımı burada korunur.
"""
from app.db import fetch_all


def same_as_group(conn, entity_id: str) -> list[dict]:
    """Faz 11 (dogfooding F31): bir entity ile CONFIRMED SAME_AS ile bağlanmış diğer entity'ler.

    Bulgu: `SAME_AS`'in CONFIRMED durumu graf'a yazılıyordu ve **hiçbir yerde okunmuyordu** —
    ne recall'da, ne vault'ta, ne de başka bir uçta. Kullanıcı birleştirmeyi onaylıyor, "Eşleşme
    onaylandı" bildirimini alıyor ve sistemde fiilen hiçbir şey değişmiyordu. Birleştirmenin
    TEK anlamı, iki kaydın bilgisinin birlikte hatırlanmasıdır.

    Q7 gereği node'lar fiziksel olarak birleştirilmez/silinmez, dolayısıyla "aynılık" okuma
    zamanında çözülmek zorunda. Kenar tek yön saklanır ama anlamı simetriktir, ve aynılık
    geçişlidir (A=B, B=C ⇒ A=C) — bu yüzden düz bir komşu sorgusu değil, CONFIRMED kenarlar
    üzerinde genişlik-öncelikli bir gezinti yapılır. Başlangıç entity'si sonuca dahil DEĞİL."""
    seen = {entity_id}
    queue = [entity_id]
    group: list[dict] = []
    while queue:
        current = queue.pop(0)
        for pattern in (
            "MATCH (a:Entity {id: $id})-[r:SAME_AS]->(b:Entity) ",
            "MATCH (b:Entity)-[r:SAME_AS]->(a:Entity {id: $id}) ",
        ):
            for row in fetch_all(
                conn.execute(
                    pattern + "WHERE r.status = 'CONFIRMED' "
                    "RETURN b.id AS id, b.name AS name, b.entity_type AS entity_type",
                    {"id": current},
                )
            ):
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                queue.append(row["id"])
                group.append(row)
    return group


def entity_recall(conn, entity_id: str) -> dict:
    # F31: birleştirilmiş kayıtlar da hatırlanır. `via` alanı, satırın hangi entity üzerinden
    # geldiğini söyler — kendi kaydıysa None. Bu olmadan kullanıcı, ekranda gördüğü bir
    # claim'in neden burada olduğunu anlayamazdı (sistemin kendini anlatması ilkesi).
    merged = same_as_group(conn, entity_id)
    targets = [{"id": entity_id, "name": None}] + [{"id": m["id"], "name": m["name"]} for m in merged]

    investigations, claims, events = [], [], []
    for t in targets:
        for row in fetch_all(
            conn.execute(
                "MATCH (i:Investigation)-[:INCLUDES]->(e:Entity {id: $id}) "
                "RETURN i.id AS id, i.title AS title, i.status AS status, i.created_at AS created_at "
                "ORDER BY i.created_at",
                {"id": t["id"]},
            )
        ):
            investigations.append({**row, "via_entity_name": t["name"]})
        for row in fetch_all(
            conn.execute(
                "MATCH (c:Claim)-[:ABOUT_ENTITY]->(e:Entity {id: $id}) "
                "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
                "c.confidence AS confidence, c.created_at AS created_at ORDER BY c.created_at",
                {"id": t["id"]},
            )
        ):
            claims.append({**row, "via_entity_name": t["name"]})
        for row in fetch_all(
            conn.execute(
                "MATCH (e:Entity {id: $id})-[:INVOLVED_IN]->(ev:Event) "
                "RETURN ev.id AS id, ev.title AS title, ev.event_type AS event_type, "
                "ev.created_at AS created_at ORDER BY ev.created_at",
                {"id": t["id"]},
            )
        ):
            events.append({**row, "via_entity_name": t["name"]})

    return {
        "related_investigations": investigations,
        "related_claims": claims,
        "related_events": events,
        "same_as": merged,
    }


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
    reported_by = fetch_all(
        conn.execute(
            "MATCH (ev:Event {id: $id})-[:REPORTED_BY]->(s:Source) "
            "RETURN s.id AS id, s.name AS name, s.source_type AS source_type "
            "ORDER BY s.name",
            {"id": event_id},
        )
    )
    return {
        "related_investigations": investigations,
        "related_claims": claims,
        "related_entities": entities,
        "reported_by": reported_by,
    }


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
        # Faz 11 (dogfooding F27): bu gerekçenin detail'i BOŞTU — sistem "bir çelişki var"
        # diyor ama "neyle" sorusunu hiçbir uçtan cevaplayamıyordu. Araştırmada asıl soru
        # tam olarak o: "OpenAI böyle diyor, peki aksini kim söylüyor?" Kardeş gerekçe
        # (PRIOR_KNOWLEDGE_EXISTS) claim id'lerini zaten dolduruyordu, bu tutarsızlıktı.
        #
        # İlişki graf'ta tek yön saklanıyor ama anlamı simetrik — iki yön de taranır.
        others: list[dict] = []
        seen_ids: set[str] = set()
        for pattern in (
            "MATCH (c:Claim {id: $id})-[r:CLAIM_CONTRADICTS]->(o:Claim) ",
            "MATCH (o:Claim)-[r:CLAIM_CONTRADICTS]->(c:Claim {id: $id}) ",
        ):
            for row in fetch_all(
                conn.execute(
                    pattern + "WHERE r.status = 'UNRESOLVED' RETURN o.id AS id, o.text AS text",
                    {"id": claim_id},
                )
            ):
                if row["id"] not in seen_ids:
                    seen_ids.add(row["id"])
                    others.append(row)

        # Metnin kendisi de karşı tarafı adlandırıyor: arayüz `detail`'i hiçbir yerde
        # göstermiyordu, dolayısıyla sadece detail'i doldurmak gerekçeyi görünür yapmazdı.
        excerpts = [o["text"].splitlines()[0][:80] if o["text"] else "" for o in others]
        if excerpts:
            liste = "; ".join(f"«{e}»" for e in excerpts)
            text = f"Bu bilgi {len(excerpts)} claim ile çelişiyor, çözülmemiş: {liste}"
        else:
            text = "Bu bilgi başka bir claim ile çelişiyor, çözülmemiş."
        reasons.append({
            "code": "CONTRADICTED",
            "text": text,
            "detail": {
                "contradicting_claim_ids": [o["id"] for o in others],
                "contradicting_claims": [
                    {"id": o["id"], "excerpt": e} for o, e in zip(others, excerpts)
                ],
            },
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
