"""
Faz 18 — olay katmanının graf mantığı: olay adayı türetme + olay confidence'ının claim'lerden
türetilmesi. (Router'dan ayrı bir modül, `app/corroboration.py` ile aynı gerekçeyle: bu mantığı
claims router'ı da çağırıyor ve router'lar birbirini import etmemeli.)

**Olay adayı türetme** — doğrulama (`CORROBORATES`) bağlarının bağlantılı bileşenleri.

Bu modül LLM çağırmaz ve yeni bir sinyal İCAT ETMEZ. Faz 17'de kullanıcı elleriyle kurduğu
her `CORROBORATES` bağıyla "bu iki claim aynı olayı anlatıyor" demişti; burada yapılan tek
şey o bağların geçişli kapanışını (transitive closure) okumak. Ölçüldüğünde (2026-09-05) 4
temiz küme çıkmıştı ve dördü de gerçek, AYRI olaylardı — ikisi aynı şirket hakkında olmasına
rağmen doğru bölünmüştü.

Küme bir ÖNERİdir, karar değil (Design Principle #7): başlığı insan verir, kümeyi bölebilir,
tek claim'lik bir olay da elle kurulabilir. Bu yüzden burada eşik/otomatik oluşturma yok —
yalnızca okuma.

Neden `SUPERSEDES`/`CLAIM_CONTRADICTS` bileşene dahil edilmiyor: ikisi de "aynı olay" demez.
Çelişen iki claim genellikle aynı olay hakkındadır ama bağı kuran kullanıcı orada "bunlar
uyuşmuyor" demiştir, "bunlar aynı şeydir" değil — çelişkiyi olay birleştirmesine girdi
yapmak, kullanıcının reddettiği bir eşitliği arka kapıdan kurmak olurdu.
"""
from datetime import datetime, timezone

from app.confidence import (
    CORROBORATED_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD,
    SUPPORTED_THRESHOLD,
)
from app.db import fetch_all, fetch_one
from app.lineage import resolve_independent_root

# Bir claim'in olay adayına girmesi için ABOUT_EVENT'i olmamalı: zaten bir olaya bağlıysa
# öneri listesinde durması gürültüdür (Faz 16'nın kuyruk dersi — liste eritilebilir olmalı).
_UNASSIGNED_CLAIMS = """
MATCH (c:Claim)
WHERE NOT EXISTS { MATCH (c)-[:ABOUT_EVENT]->(:Event) }
OPTIONAL MATCH (s:Source)-[:ASSERTS]->(c)
OPTIONAL MATCH (c)-[:ABOUT_ENTITY]->(e:Entity)
OPTIONAL MATCH (yeni:Claim)-[:SUPERSEDES]->(c)
RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state,
       c.confidence AS confidence, c.created_at AS created_at, c.valid_to AS valid_to,
       s.id AS source_id, s.name AS source_name,
       e.id AS about_entity_id, e.name AS about_entity_name,
       yeni.id AS superseded_by_claim_id
ORDER BY c.created_at
"""


def _corroboration_edges(conn, claim_ids: set[str]) -> list[tuple[str, str]]:
    rows = fetch_all(
        conn.execute("MATCH (a:Claim)-[:CORROBORATES]->(b:Claim) RETURN a.id AS a, b.id AS b")
    )
    # CORROBORATES simetrik kurulur (Faz 2) ama tek yönlü yazılmış eski kayıtlara karşı
    # yön burada zaten önemsiz — bileşen hesabı yönsüz.
    return [(r["a"], r["b"]) for r in rows if r["a"] in claim_ids and r["b"] in claim_ids]


def _components(nodes: list[str], edges: list[tuple[str, str]]) -> list[list[str]]:
    """Union-find yerine düz BFS — küme sayısı onlarca mertebesinde, karmaşıklık ödemeye
    değmez ve okunabilirlik burada daha kıymetli."""
    adjacency: dict[str, set[str]] = {n: set() for n in nodes}
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    seen: set[str] = set()
    order = {n: i for i, n in enumerate(nodes)}
    components = []
    for node in nodes:
        if node in seen:
            continue
        seen.add(node)
        queue = [node]
        group = []
        while queue:
            current = queue.pop(0)
            group.append(current)
            for neighbour in adjacency[current]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
        components.append(sorted(group, key=lambda n: order[n]))
    return components


def event_candidates(conn, *, min_size: int = 2) -> list[dict]:
    """Olay adayları — büyükten küçüğe, sonra en yeni claim'i en yeni olan önce.

    `min_size=1` verilirse tek başına duran claim'ler de aday olarak döner; varsayılan 2,
    çünkü tek claim'lik bir "küme" bir öneri değil, sadece bağlanmamış bir claim'dir — onun
    yolu event detayındaki "mevcut claim'i bağla".
    """
    claims = {row["id"]: row for row in fetch_all(conn.execute(_UNASSIGNED_CLAIMS))}
    if not claims:
        return []
    edges = _corroboration_edges(conn, set(claims))
    roots: dict[str, str] = {}

    candidates = []
    for group in _components(list(claims), edges):
        if len(group) < min_size:
            continue
        members = [claims[cid] for cid in group]
        source_ids = {m["source_id"] for m in members if m["source_id"]}
        # Q6: "kaç farklı kaynak" sorusunun dürüst cevabı ham Source sayısı değil, bağımsız
        # kök sayısı. Bir olayı 4 site bildirdi ama hepsi aynı ajanstan türediyse, o olayın
        # arkasında tek bir bağımsız kaynak var — küme kartında yanlış sayı göstermek,
        # Faz 17'nin bütün derdi olan "sahte bağımsızlık" hatasını buraya taşırdı.
        for sid in source_ids:
            if sid not in roots:
                roots[sid] = resolve_independent_root(conn, sid)
        entities = {}
        for m in members:
            if m["about_entity_id"]:
                entities[m["about_entity_id"]] = m["about_entity_name"]
        timestamps = [m["created_at"] for m in members if m["created_at"]]
        candidates.append(
            {
                "claims": members,
                "claim_count": len(members),
                "source_count": len(source_ids),
                "independent_source_count": len({roots[sid] for sid in source_ids}),
                "entities": [{"id": eid, "name": name} for eid, name in entities.items()],
                "first_seen": min(timestamps) if timestamps else None,
                "last_seen": max(timestamps) if timestamps else None,
            }
        )
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    candidates.sort(key=lambda c: (c["claim_count"], c["last_seen"] or epoch), reverse=True)
    return candidates


def recompute_event_confidence(conn, event_id: str) -> tuple[float, str]:
    """Bir olayın confidence'ı claim'lerinden TÜRETİLİR (Faz 2'de not düşülmüştü: "Event.
    confidence claim'lerden türetilecek"; Faz 18'de yapıldı).

    Kural, olabilecek en açıklanabilir hali: **en iyi desteklenen claim'inin confidence'ı.**

    - Ortalama alınmadı: bir olaya sonradan eklenen zayıf bir ayrıntı claim'i, iyi
      doğrulanmış bir olayın güvenilirliğini DÜŞÜRÜRDÜ — oysa yeni bilgi eklemek bilineni
      azaltmaz.
    - Toplama yapılmadı: 5 zayıf claim bir olayı gerçekleşmiş yapmaz. Toplam, Faz 17'nin
      engellemek için kurulduğu sahte-bağımsızlık yükselmesinin olay seviyesindeki
      karşılığı olurdu — üstelik claim confidence'ı zaten corroboration'ı sayıyor, yani
      aynı sinyal iki kez ödüllendirilirdi.

    Çelişki bulaşıcı: claim'lerinden biri UNRESOLVED bir çelişkiyle CONTRADICTED ise olayın
    kendisi de CONTRADICTED gösterilir — sayısal değer korunur, etiket uyarır (Q3 hibrit
    model: sayı ile durum ayrı tutulur)."""
    rows = fetch_all(
        conn.execute(
            "MATCH (c:Claim)-[:ABOUT_EVENT]->(ev:Event {id: $id}) "
            "RETURN c.confidence AS confidence, c.knowledge_state AS knowledge_state",
            {"id": event_id},
        )
    )
    if not rows:
        confidence, state = 0.0, "OBSERVED"
    else:
        confidence = round(max(r["confidence"] or 0.0 for r in rows), 4)
        if any(r["knowledge_state"] == "CONTRADICTED" for r in rows):
            state = "CONTRADICTED"
        elif confidence >= HIGH_CONFIDENCE_THRESHOLD:
            state = "HIGH_CONFIDENCE"
        elif confidence >= CORROBORATED_THRESHOLD:
            state = "CORROBORATED"
        elif confidence >= SUPPORTED_THRESHOLD:
            state = "SUPPORTED"
        elif confidence > 0:
            state = "REPORTED"
        else:
            state = "OBSERVED"
    conn.execute(
        "MATCH (ev:Event {id: $id}) SET ev.confidence = $confidence, ev.knowledge_state = $state",
        {"id": event_id, "confidence": confidence, "state": state},
    )
    return confidence, state


# Bir claim'in öznesi değişirken taşınan entity'nin olaydaki rolü — `PATCH /claims/{id}/about`
# ve `PUT /events/{id}/claims/{claim_id}` rol sormuyor; olay adayından kurulan olayın
# varsayılanıyla (`EventFromCluster.entity_role`) aynı.
DEFAULT_CARRY_ROLE = "ilgili"


def set_claim_about(
    conn,
    claim_id: str,
    *,
    entity_id: str | None = None,
    event_id: str | None = None,
    carry_entity: bool = True,
    carry_role: str = DEFAULT_CARRY_ROLE,
    recompute_new_event: bool = True,
) -> dict:
    """Claim'in öznesini (ABOUT_ENTITY / ABOUT_EVENT) değiştirmenin TEK yolu.

    Değişmezler, hepsi burada ve bir kez:

    1. **Bir claim ya entity ya event hakkındadır, ikisi birden değil.** İkisi birden
       verilirse ValueError.
    2. **Claim olaya taşınırken entity fakirleşmez.** Claim'i olaya bağlamak ABOUT_ENTITY'yi
       siler; önceki entity olaya INVOLVED_IN ile taşınır (`carry_entity`). 2026-10-18
       denetimine kadar bu telafiyi yalnızca `POST /events/from-cluster` yapıyordu —
       `PUT /events/{id}/claims/{claim_id}` ve `PATCH /claims/{id}/about` entity bağını
       sessizce düşürüyordu (CLAUDE.md'nin "bu telafiyi atlama" uyarısının tam karşılığı).
    3. **Olay confidence'ı türetilmiş kalır.** Claim'in ESKİ olayı da yeniden hesaplanır;
       yoksa boşalan bir olay, giden claim'in (belki en yüksek) skorunu göstermeye devam
       ederdi.

    Dönen: {"previous_entity_id", "previous_event_id", "carried_entity_id"}."""
    if entity_id and event_id:
        raise ValueError("Bir claim ya bir entity ya da bir event hakkında olabilir, ikisi birden değil")

    previous = fetch_one(
        conn.execute(
            "MATCH (c:Claim {id: $id}) "
            "OPTIONAL MATCH (c)-[:ABOUT_ENTITY]->(en:Entity) "
            "OPTIONAL MATCH (c)-[:ABOUT_EVENT]->(ev:Event) "
            "RETURN en.id AS entity_id, ev.id AS event_id",
            {"id": claim_id},
        )
    ) or {}
    previous_entity_id = previous.get("entity_id")
    previous_event_id = previous.get("event_id")

    conn.execute("MATCH (c:Claim {id: $id})-[r:ABOUT_ENTITY]->(:Entity) DELETE r", {"id": claim_id})
    conn.execute("MATCH (c:Claim {id: $id})-[r:ABOUT_EVENT]->(:Event) DELETE r", {"id": claim_id})
    if entity_id:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (e:Entity {id: $eid}) CREATE (c)-[:ABOUT_ENTITY]->(e)",
            {"cid": claim_id, "eid": entity_id},
        )
    carried = None
    if event_id:
        conn.execute(
            "MATCH (c:Claim {id: $cid}), (ev:Event {id: $evid}) CREATE (c)-[:ABOUT_EVENT]->(ev)",
            {"cid": claim_id, "evid": event_id},
        )
        if carry_entity and previous_entity_id:
            already = fetch_one(
                conn.execute(
                    "MATCH (e:Entity {id: $eid})-[:INVOLVED_IN]->(ev:Event {id: $evid}) RETURN e.id AS id",
                    {"eid": previous_entity_id, "evid": event_id},
                )
            )
            if already is None:
                conn.execute(
                    "MATCH (e:Entity {id: $eid}), (ev:Event {id: $evid}) "
                    "CREATE (e)-[:INVOLVED_IN {role: $role}]->(ev)",
                    {"eid": previous_entity_id, "evid": event_id, "role": carry_role},
                )
                carried = previous_entity_id
    conn.execute(
        "MATCH (c:Claim {id: $id}) SET c.updated_at = $now",
        {"id": claim_id, "now": datetime.now(timezone.utc)},
    )
    if previous_event_id and previous_event_id != event_id:
        recompute_event_confidence(conn, previous_event_id)
    if event_id and recompute_new_event:
        recompute_event_confidence(conn, event_id)
    return {
        "previous_entity_id": previous_entity_id,
        "previous_event_id": previous_event_id,
        "carried_entity_id": carried,
    }
