"""
Faz 19 + 22 — entity ilişki adayları ve graf okuması.

**Neden bu modül var (ölçüm, 2026-09-05).** 5 entity vardı ve aralarında **0 ilişki**.
`ENTITY_RELATION` yazan/okuyan uçlar Faz 10'da kurulmuştu ve gerçek kullanımda sıfır kenar
üretmişti — Faz 16/17/18'in tekrar eden deseni: mekanizma var, onu tetikleyecek iş akışı yok.
Eksik olan tek şey "hangi iki entity ilişkili olabilir?" sorusunun cevabının bir yerde
durmasıydı.

**Faz 22'de sinyalin KAYNAĞI değişti: metin taraması → karar kayıtları.** Faz 19'da adaylar
claim metnini yeniden tarayarak üretiliyordu. Faz 21'de `MENTIONS` kenarları kurulunca bu
gereksiz ve dahası YANLIŞ oldu: kullanıcı bir değmeyi reddettiyse ("bu claim Microsoft'a
değmiyor"), o reddedilen değmeden bir ilişki adayı üretmek kullanıcının kararını arkadan
dolanmak olurdu. Artık iki entity, aynı claim'e **karar verilmiş** bir bağla (özne ya da
onaylanmış değme) bağlıysa birlikte geçiyor sayılır.

**İki deterministik sinyal, bilerek ayrı tutuluyor:**

1. **Aynı claim'e bağlı olma** — zayıf: aynı haberde iki adın anılması olabilir.
2. **Aynı olaya karışma** (`INVOLVED_IN`) — güçlü: kullanıcının kendi kurduğu bir bağ.

Tek bir skora karıştırılmıyorlar; iki sayı ayrı gösteriliyor.

**İlişkinin TÜRÜNÜ bu modül vermez.** "OpenAI, Astra'yı geliştirdi" ile "Astra, OpenAI'ın
ürünü" arasındaki fark anlamsal bir karardır; birlikte geçme bunu söyleyemez, yalnızca "bu
ikisi birbiriyle ilgili" der. Türü kullanıcı yazar (Design Principle #7).

**Neden confidence önerilmiyor:** birlikte geçme sayısı ilişkinin GÜCÜ değil, kanıtın hacmi.
10 ortak claim ilişkinin doğru olduğu anlamına gelmez — aynı haber akışının 10 kez toplanmış
olması da olabilir. Sayı ham kanıt olarak gösteriliyor, skora çevrilmiyor.
"""
from app.db import fetch_all
from app.recall import same_as_group

# Bir çift için gösterilecek en fazla kanıt satırı. Amaç "neden bu aday" sorusunu cevaplamak,
# claim listesini tekrar etmek değil.
MAX_EVIDENCE = 3


def _pair(a: str, b: str) -> tuple[str, str]:
    """Yönsüz çift anahtarı. İlişki yönlü kurulur ama ADAYLIK yönsüzdür: A–B ile B–A aynı
    öneridir ve iki kez sorulmamalı."""
    return (a, b) if a < b else (b, a)


def _blocked_pairs(conn) -> set[tuple[str, str]]:
    """Aday olamayacak çiftler: zaten ACTIVE bir ilişkisi olanlar, reddedilmiş olanlar ve
    aynı olduğu onaylanmış (SAME_AS) kayıtlar.

    Sonuncusu önemli: aynı olduğu onaylanmış iki kayıt arasında "ilişki" kurmak, aynılığı
    ilişkiye çevirerek Q7 kararını bozardı."""
    blocked: set[tuple[str, str]] = set()
    for row in fetch_all(
        conn.execute(
            "MATCH (a:Entity)-[r:ENTITY_RELATION]->(b:Entity) WHERE r.status = 'ACTIVE' "
            "RETURN a.id AS a, b.id AS b"
        )
    ):
        blocked.add(_pair(row["a"], row["b"]))
    for row in fetch_all(
        conn.execute("MATCH (a:Entity)-[:RELATION_REJECTED]->(b:Entity) RETURN a.id AS a, b.id AS b")
    ):
        blocked.add(_pair(row["a"], row["b"]))
    for row in fetch_all(
        conn.execute(
            "MATCH (a:Entity)-[r:SAME_AS]->(b:Entity) WHERE r.status = 'CONFIRMED' "
            "RETURN a.id AS a, b.id AS b"
        )
    ):
        blocked.add(_pair(row["a"], row["b"]))
    return blocked


def _claim_links(conn) -> list[dict]:
    """Karar verilmiş claim ↔ entity bağları: ÖZNE (`ABOUT_ENTITY`) ve onaylanmış DEĞME
    (`MENTIONS`). İkisi birlikte, çünkü "birlikte geçiyor" sorusu için ikisi de aynı şeyi
    söylüyor: bu claim bu entity'ye dokunuyor."""
    subjects = fetch_all(
        conn.execute(
            "MATCH (c:Claim)-[:ABOUT_ENTITY]->(e:Entity) "
            "RETURN c.id AS claim_id, c.text AS text, e.id AS entity_id, 'ÖZNE' AS kind"
        )
    )
    mentions = fetch_all(
        conn.execute(
            "MATCH (c:Claim)-[m:MENTIONS]->(e:Entity) WHERE m.status = 'CONFIRMED' "
            "RETURN c.id AS claim_id, c.text AS text, e.id AS entity_id, 'DEĞME' AS kind"
        )
    )
    return subjects + mentions


def _shared_events(conn) -> dict[tuple[str, str], list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for row in fetch_all(
        conn.execute(
            "MATCH (a:Entity)-[:INVOLVED_IN]->(ev:Event)<-[:INVOLVED_IN]-(b:Entity) "
            "WHERE a.id < b.id "
            "RETURN DISTINCT a.id AS a, b.id AS b, ev.id AS event_id, ev.title AS title"
        )
    ):
        grouped.setdefault(_pair(row["a"], row["b"]), []).append(
            {"id": row["event_id"], "title": row["title"]}
        )
    return grouped


def _entity_meta(conn) -> dict[str, dict]:
    return {
        row["id"]: row
        for row in fetch_all(
            conn.execute("MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.entity_type AS entity_type")
        )
    }


def relation_pair_candidates(conn) -> list[dict]:
    """Graf'ın TAMAMI için ilişki adayı çiftleri — kanıtı çok olan önce.

    Faz 22'de eklendi. Faz 19 yalnızca entity başına aday veriyordu; 109 çiftin tamamını
    eritmek için entity entity gezmek gerekiyordu ve bu, kararı pahalı yapan şeyin ta
    kendisiydi (Faz 16'nın dersi)."""
    meta = _entity_meta(conn)
    blocked = _blocked_pairs(conn)
    same_as_cache: dict[str, set[str]] = {}

    def same_group(entity_id: str) -> set[str]:
        if entity_id not in same_as_cache:
            same_as_cache[entity_id] = {o["id"] for o in same_as_group(conn, entity_id)}
        return same_as_cache[entity_id]

    by_claim: dict[str, list[dict]] = {}
    claim_text: dict[str, str] = {}
    for row in _claim_links(conn):
        by_claim.setdefault(row["claim_id"], []).append(row)
        claim_text[row["claim_id"]] = row["text"]

    shared_claims: dict[tuple[str, str], list[dict]] = {}
    for claim_id, links in by_claim.items():
        # Aynı claim'e bağlı her entity ikilisi bir kanıt satırı üretir.
        for i, left in enumerate(links):
            for right in links[i + 1 :]:
                a, b = left["entity_id"], right["entity_id"]
                if a == b or b in same_group(a):
                    continue
                key = _pair(a, b)
                if key in blocked:
                    continue
                shared_claims.setdefault(key, []).append(
                    {
                        "claim_id": claim_id,
                        "excerpt": (claim_text.get(claim_id) or "").split("\n")[0].strip()[:160],
                        # Hangi tarafın ÖZNE hangisinin DEĞME olduğu, ilişkinin yönü hakkında
                        # kullanıcıya fikir verir — ama sistem yön ÖNERMEZ.
                        "kinds": f"{left['kind']}/{right['kind']}",
                    }
                )

    shared_events = {k: v for k, v in _shared_events(conn).items() if k not in blocked}

    candidates = []
    for key in set(shared_claims) | set(shared_events):
        a, b = key
        if a not in meta or b not in meta:
            continue
        claims = shared_claims.get(key, [])
        events = shared_events.get(key, [])
        candidates.append(
            {
                "a": {"entity_id": a, "name": meta[a]["name"], "entity_type": meta[a]["entity_type"]},
                "b": {"entity_id": b, "name": meta[b]["name"], "entity_type": meta[b]["entity_type"]},
                "shared_claim_count": len(claims),
                "shared_event_count": len(events),
                "shared_events": events,
                "evidence": claims[:MAX_EVIDENCE],
            }
        )
    # Ortak olay, ortak claim'den daha güçlü kanıt: metin birlikteliği aynı haberde iki adın
    # anılması olabilir, ortak olay kullanıcının kendi kurduğu bir bağdır.
    candidates.sort(
        key=lambda c: (-c["shared_event_count"], -c["shared_claim_count"], c["a"]["name"].lower())
    )
    return candidates


def relation_candidates(conn, entity_id: str) -> list[dict]:
    """Tek bir entity için ilişki adayları (Faz 19; entity detay sayfası kullanıyor).

    Faz 22'de global hesaplamanın üstüne bir filtreye indirgendi — iki ayrı aday tanımı
    olsaydı entity sayfası ile toplu ekran aynı çifte farklı cevap verebilirdi."""
    out = []
    for candidate in relation_pair_candidates(conn):
        if candidate["a"]["entity_id"] == entity_id:
            other = candidate["b"]
        elif candidate["b"]["entity_id"] == entity_id:
            other = candidate["a"]
        else:
            continue
        out.append(
            {
                "entity_id": other["entity_id"],
                "name": other["name"],
                "entity_type": other["entity_type"],
                "co_mention_count": candidate["shared_claim_count"],
                "shared_event_count": candidate["shared_event_count"],
                "shared_events": candidate["shared_events"],
                "evidence": [
                    {"claim_id": e["claim_id"], "excerpt": e["excerpt"], "matched_on": e["kinds"]}
                    for e in candidate["evidence"]
                ],
            }
        )
    return out


def entity_graph(conn) -> dict:
    """Graf görünümünün verisi: düğümler + kenarlar.

    Faz 8'in "Entity Graph paneli duruyor" notunun yanlış olduğu 2026-09-02'de bulunmuş ve o
    günden beri kapanmamıştı. Kenar iki türlü: entity–entity (`ENTITY_RELATION`) ve entity–olay
    (`INVOLVED_IN`). İkincisi olmadan graf, olay ekseni kurulmuş bir sistemde onu göstermezdi.

    Ağırlık/derece hesaplanıp döndürülüyor ki istemci düğüm boyutunu veriden türetsin —
    yerleşimi rastgele değil, graf'ın kendi yapısı belirlesin."""
    nodes = [
        {
            "id": row["id"],
            "kind": "entity",
            "label": row["name"],
            "entity_type": row["entity_type"],
        }
        for row in fetch_all(
            conn.execute("MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.entity_type AS entity_type ORDER BY e.name")
        )
    ]
    nodes += [
        {
            "id": row["id"],
            "kind": "event",
            "label": row["title"],
            "entity_type": row["event_type"],
            "knowledge_state": row["knowledge_state"],
            "confidence": row["confidence"],
        }
        for row in fetch_all(
            conn.execute(
                "MATCH (e:Event) RETURN e.id AS id, e.title AS title, e.event_type AS event_type, "
                "e.knowledge_state AS knowledge_state, e.confidence AS confidence ORDER BY e.title"
            )
        )
    ]

    edges = [
        {
            "source": row["a"],
            "target": row["b"],
            "kind": "relation",
            "label": row["relation_type"],
        }
        for row in fetch_all(
            conn.execute(
                "MATCH (a:Entity)-[r:ENTITY_RELATION]->(b:Entity) WHERE r.status = 'ACTIVE' "
                "RETURN a.id AS a, b.id AS b, r.relation_type AS relation_type"
            )
        )
    ]
    edges += [
        {"source": row["a"], "target": row["b"], "kind": "involved_in", "label": row["role"] or "ilgili"}
        for row in fetch_all(
            conn.execute(
                "MATCH (a:Entity)-[r:INVOLVED_IN]->(b:Event) RETURN a.id AS a, b.id AS b, r.role AS role"
            )
        )
    ]
    edges += [
        {"source": row["a"], "target": row["b"], "kind": "same_as", "label": "aynı kayıt"}
        for row in fetch_all(
            conn.execute(
                "MATCH (a:Entity)-[r:SAME_AS]->(b:Entity) WHERE r.status = 'CONFIRMED' "
                "RETURN a.id AS a, b.id AS b"
            )
        )
    ]

    degree: dict[str, int] = {}
    for edge in edges:
        degree[edge["source"]] = degree.get(edge["source"], 0) + 1
        degree[edge["target"]] = degree.get(edge["target"], 0) + 1
    for node in nodes:
        node["degree"] = degree.get(node["id"], 0)

    return {"nodes": nodes, "edges": edges}
