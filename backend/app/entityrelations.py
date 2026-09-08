"""
Faz 19 — entity ilişki adayları: birlikte geçen entity çiftleri.

Ölçüm (2026-09-05): 5 entity, aralarında **0 ilişki**. "Knowledge Graph"in *graph* kısmı hiç
çalışmamıştı. `ENTITY_RELATION` yazan/okuyan uçlar Faz 10'da kurulmuştu ve gerçek kullanımda
sıfır kenar üretmişti — Faz 16/17/18'in tekrar eden deseni: mekanizma var, onu tetikleyecek
iş akışı yok. Bu modül o akışın eksik parçası: "hangi iki entity ilişkili olabilir?"

**İki deterministik sinyal, ikisi de açıklanabilir:**

1. **Claim metninde birlikte geçme.** Faz 12/16'nın entity eşleştiricisi
   (`scanning.match_entities_in_text`) zaten "bu metinde hangi entity'ler geçiyor" sorusunu
   cevaplıyor; burada aynı fonksiyon çift eksenine taşınıyor. Ayrı bir eşleştirici
   yazılsaydı iki farklı "bu metin bu entity hakkında mı" tanımı olurdu ve Inbox ile bu
   ekran aynı claim'e ters cevap verebilirdi.
2. **Aynı olaya karışma** (`INVOLVED_IN`). Faz 18'in yan ürünü: bir olaya birlikte bağlanan
   iki entity, o olayda ilişkilidir. Metin eşleşmesinden bağımsız bir kanıt — birinin adı
   diğerinin claim'inde geçmese bile aynı olayın tarafı olabilirler.

**İlişkinin TÜRÜNÜ bu modül vermez.** "OpenAI, Astra'yı geliştirdi" ile "Astra, OpenAI'ın
ürünü" arasındaki fark anlamsal bir karardır; birlikte geçme bunu söyleyemez, yalnızca
"bu ikisi birbiriyle ilgili" der. Türü kullanıcı yazar (Design Principle #7).

**Neden confidence önerilmiyor:** birlikte geçme sayısı ilişkinin GÜCÜ değil, yalnızca
kanıtın hacmi. 10 ortak claim, ilişkinin %100 doğru olduğu anlamına gelmez — aynı haber
akışının 10 kez toplanmış olması da olabilir. Sayı ham kanıt olarak gösteriliyor, skora
çevrilmiyor.
"""
from app.db import fetch_all
from app.recall import same_as_group
from app.scanning import load_entity_rows, match_entities_in_text

# Bir claim'den kanıt olarak gösterilecek en fazla alıntı sayısı. Amaç "neden bu aday"
# sorusunu cevaplamak, claim listesini tekrar etmek değil.
MAX_EVIDENCE = 3


def _active_relation_partners(conn, entity_id: str) -> set[str]:
    """Zaten ACTIVE bir ilişkisi olan karşı taraflar — aday listesinde durmaları gürültü.
    Yön önemsiz: A→B varken B→A'yı "yeni aday" diye önermek aynı ilişkiyi iki kez kurdururdu."""
    partners = set()
    for pattern in (
        "MATCH (:Entity {id: $id})-[r:ENTITY_RELATION]->(other:Entity) ",
        "MATCH (other:Entity)-[r:ENTITY_RELATION]->(:Entity {id: $id}) ",
    ):
        for row in fetch_all(
            conn.execute(pattern + "WHERE r.status = 'ACTIVE' RETURN other.id AS id", {"id": entity_id})
        ):
            partners.add(row["id"])
    return partners


def _shared_events(conn, entity_id: str) -> dict[str, list[dict]]:
    """entity_id ile aynı olaya karışan entity'ler → o olaylar."""
    rows = fetch_all(
        conn.execute(
            "MATCH (:Entity {id: $id})-[:INVOLVED_IN]->(ev:Event)<-[:INVOLVED_IN]-(other:Entity) "
            "WHERE other.id <> $id "
            "RETURN DISTINCT other.id AS other_id, ev.id AS event_id, ev.title AS title",
            {"id": entity_id},
        )
    )
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["other_id"], []).append({"id": row["event_id"], "title": row["title"]})
    return grouped


def relation_candidates(conn, entity_id: str) -> list[dict]:
    """Bu entity için ilişki adayları — kanıtı çok olan önce.

    Aday listesinden çıkarılanlar: entity'nin kendisi, zaten ACTIVE ilişkisi olanlar ve
    CONFIRMED `SAME_AS` grubundakiler. Sonuncusu önemli — aynı olduğu onaylanmış iki kayıt
    arasında "ilişki" kurmak, aynılığı ilişkiye çevirerek Q7 kararını bozardı."""
    entity_rows = load_entity_rows(conn)
    self_row = next((row for row in entity_rows if row["id"] == entity_id), None)
    if self_row is None:
        return []

    excluded = {entity_id}
    excluded |= _active_relation_partners(conn, entity_id)
    excluded |= {row["id"] for row in same_as_group(conn, entity_id)}

    claims = fetch_all(
        conn.execute(
            "MATCH (c:Claim) RETURN c.id AS id, c.text AS text, c.created_at AS created_at ORDER BY c.created_at DESC"
        )
    )

    co_mentions: dict[str, list[dict]] = {}
    for claim in claims:
        text = claim["text"] or ""
        # Önce bu entity metinde geçiyor mu — geçmiyorsa çift kurulamaz, diğer eşleştirmeyi
        # hiç yapmaya gerek yok. (Claim'in `ABOUT_ENTITY` bağına BAKILMIYOR bilerek: Faz
        # 18'den sonra claim'lerin bir kısmı entity'ye değil olaya bağlı, ama metinde adı
        # geçmeye devam ediyor — bağa göre filtrelemek o kanıtı görünmez kılardı.)
        if not match_entities_in_text([self_row], text):
            continue
        for match in match_entities_in_text(entity_rows, text):
            if match["id"] in excluded:
                continue
            co_mentions.setdefault(match["id"], []).append(
                {
                    "claim_id": claim["id"],
                    "excerpt": text.split("\n")[0].strip()[:160],
                    "matched_on": match["matched_on"],
                }
            )

    shared = _shared_events(conn, entity_id)
    names = {row["id"]: row["name"] for row in entity_rows}
    types = {
        row["id"]: row["entity_type"]
        for row in fetch_all(conn.execute("MATCH (e:Entity) RETURN e.id AS id, e.entity_type AS entity_type"))
    }

    candidates = []
    for other_id in set(co_mentions) | (set(shared) - excluded):
        mentions = co_mentions.get(other_id, [])
        events = shared.get(other_id, [])
        candidates.append(
            {
                "entity_id": other_id,
                "name": names.get(other_id, ""),
                "entity_type": types.get(other_id, ""),
                "co_mention_count": len(mentions),
                "shared_event_count": len(events),
                "shared_events": events,
                "evidence": mentions[:MAX_EVIDENCE],
            }
        )
    # Ortak olay, metinde birlikte geçmekten daha güçlü bir kanıt: metin eşleşmesi aynı
    # haberde iki adın anılması olabilir, ortak olay ise kullanıcının kendi kurduğu bir bağ.
    candidates.sort(key=lambda c: (c["shared_event_count"], c["co_mention_count"]), reverse=True)
    return candidates
