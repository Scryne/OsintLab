"""
Faz 21 — claim'in DEĞDİĞİ entity'ler (`MENTIONS`), öznesinden (`ABOUT_ENTITY`) ayrı.

**Ölçüm (2026-09-08).** 58 entity'nin 52'si claim metinlerinde geçiyordu ve hiçbirinin tek
bir claim bağı yoktu; `ABOUT_ENTITY` bağı olan entity sayısı 5'ti. Gerçek claim↔entity değme
sayısı **134** (claim başına 2.48) ölçüldü, oysa graf'ta en fazla 54'ü temsil edilebiliyordu.
"OpenAI'ın 27 claim'i var, Microsoft'un 0" tablosunun tek sebebi buydu.

**Neden yeni bir ilişki, neden `ABOUT_ENTITY` çoğullaştırılmadı.** `ABOUT_ENTITY` claim'in
ÖZNESİ ve tekil olması bir kusur değil, üç mekanizmanın dayanağı: confidence hesabı, recall
ve Faz 18'in olay türetmesi "bu claim neyin hakkında" sorusunun TEK cevabı olduğunu varsayar.
Çoğullaştırmak üçünün de anlamını bozardı. Ayrım şu: *"OpenAI, Astra'yı duyurdu"* claim'inin
ÖZNESİ OpenAI'dır, ama claim Astra'ya da DEĞER. İkisi farklı ilişkiler.

**Aday üretimi yeni bir sinyal icat etmiyor.** `scanning.match_entities_in_text` Faz 12'den
beri "bu metinde hangi entity'ler geçiyor" sorusunu cevaplıyor ve ölçüm de onunla alındı;
burada aynı fonksiyon claim eksenine taşınıyor — Faz 19'daki kararın aynısı. Ayrı bir
eşleştirici yazılsaydı iki farklı "bu metin bu entity'ye değiyor mu" tanımı olurdu ve Inbox
ile bu ekran aynı claim'e ters cevap verirdi.

**Karar insanın (Design Principle #7).** Metinde adın geçmesi, claim'in o entity hakkında bir
şey SÖYLEDİĞİ anlamına gelmez — "OpenAI, Microsoft'a dava açan gazeteleri savundu" cümlesinde
üç ad geçer ve üçü aynı ağırlıkta değildir. Sistem çifti önerir, kullanıcı onaylar veya
reddeder. Reddedilen çift silinmez, `status='REJECTED'` ile işaretlenir; yoksa aynı öneri her
aday hesabında geri gelirdi (Faz 20'nin `EntityCandidate` kararı).
"""
from datetime import datetime, timezone

from app.db import fetch_all
from app.recall import same_as_group
from app.scanning import load_entity_rows, match_entities_in_text

MENTION_STATUSES = ("CONFIRMED", "REJECTED")


def _decided_pairs(conn) -> set[tuple[str, str]]:
    """Hakkında zaten karar verilmiş (claim, entity) çiftleri — onaylanmış da reddedilmiş de."""
    return {
        (row["claim_id"], row["entity_id"])
        for row in fetch_all(
            conn.execute(
                "MATCH (c:Claim)-[m:MENTIONS]->(e:Entity) "
                "RETURN c.id AS claim_id, e.id AS entity_id"
            )
        )
    }


def _subject_entities(conn) -> dict[str, set[str]]:
    """claim_id -> öznesi olan entity ve onunla AYNI olduğu onaylanmış kayıtlar.

    Aynılık grubu da dışlanıyor: bir claim "Chaotic Eclipse" hakkındaysa, metinde geçen
    "INFINITE NIGHTMARE" (aynı aktörün diğer adı) bir DEĞME önerisi olarak sunulmamalı —
    o zaten öznenin kendisi (Q7: kayıtlar birleştirilmez, aynılık okuma zamanında çözülür)."""
    subjects: dict[str, set[str]] = {}
    for row in fetch_all(
        conn.execute("MATCH (c:Claim)-[:ABOUT_ENTITY]->(e:Entity) RETURN c.id AS claim_id, e.id AS entity_id")
    ):
        group = {row["entity_id"]}
        group |= {other["id"] for other in same_as_group(conn, row["entity_id"])}
        subjects.setdefault(row["claim_id"], set()).update(group)
    return subjects


def mention_candidates(conn) -> list[dict]:
    """Bekleyen (claim, entity) değme adayları — claim başına gruplanmış.

    Gruplama claim ekseninde, çünkü karar orada ucuz: bir claim'in metnine bakıp "evet bu üçü
    de geçiyor" demek, aynı 3 çifti üç ayrı satırda görmekten hızlıdır (Faz 16'nın dersi:
    sorun insanın karar vermesi değil, kararın pahalı olması)."""
    entity_rows = load_entity_rows(conn)
    if not entity_rows:
        return []
    decided = _decided_pairs(conn)
    subjects = _subject_entities(conn)
    types = {
        row["id"]: row["entity_type"]
        for row in fetch_all(conn.execute("MATCH (e:Entity) RETURN e.id AS id, e.entity_type AS entity_type"))
    }
    subject_names = {
        row["claim_id"]: row["name"]
        for row in fetch_all(
            conn.execute(
                "MATCH (c:Claim)-[:ABOUT_ENTITY]->(e:Entity) RETURN c.id AS claim_id, e.name AS name"
            )
        )
    }

    claims = fetch_all(
        conn.execute(
            "MATCH (c:Claim) OPTIONAL MATCH (s:Source)-[:ASSERTS]->(c) "
            "RETURN c.id AS id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence, c.created_at AS created_at, s.name AS source_name "
            "ORDER BY c.created_at DESC"
        )
    )

    groups = []
    for claim in claims:
        text = claim["text"] or ""
        own = subjects.get(claim["id"], set())
        candidates = [
            {
                "entity_id": match["id"],
                "name": match["name"],
                "entity_type": types.get(match["id"], ""),
                "matched_on": match["matched_on"],
            }
            for match in match_entities_in_text(entity_rows, text)
            if match["id"] not in own and (claim["id"], match["id"]) not in decided
        ]
        if not candidates:
            continue
        groups.append(
            {
                "claim_id": claim["id"],
                "text": text,
                "knowledge_state": claim["knowledge_state"],
                "confidence": claim["confidence"],
                "source_name": claim["source_name"],
                "subject_name": subject_names.get(claim["id"]),
                "candidates": candidates,
            }
        )
    groups.sort(key=lambda g: len(g["candidates"]), reverse=True)
    return groups


def set_mention(conn, claim_id: str, entity_id: str, status: str, matched_on: str = "") -> None:
    """Çifti onayla veya reddet. Kenar bir kez yazılır, sonra durumu güncellenir — reddedilen
    bir öneri de graf'ta kalır (kararın kendisi kayıttır)."""
    now = datetime.now(timezone.utc)
    exists = fetch_all(
        conn.execute(
            "MATCH (c:Claim {id: $cid})-[m:MENTIONS]->(e:Entity {id: $eid}) RETURN m.status AS status",
            {"cid": claim_id, "eid": entity_id},
        )
    )
    if exists:
        conn.execute(
            "MATCH (c:Claim {id: $cid})-[m:MENTIONS]->(e:Entity {id: $eid}) SET m.status = $status",
            {"cid": claim_id, "eid": entity_id, "status": status},
        )
        return
    conn.execute(
        "MATCH (c:Claim {id: $cid}), (e:Entity {id: $eid}) "
        "CREATE (c)-[:MENTIONS {matched_on: $matched_on, status: $status, created_at: $now}]->(e)",
        {"cid": claim_id, "eid": entity_id, "matched_on": matched_on, "status": status, "now": now},
    )


def claim_mentions(conn, claim_id: str) -> list[dict]:
    return fetch_all(
        conn.execute(
            "MATCH (c:Claim {id: $id})-[m:MENTIONS]->(e:Entity) WHERE m.status = 'CONFIRMED' "
            "RETURN e.id AS entity_id, e.name AS name, e.entity_type AS entity_type, "
            "m.matched_on AS matched_on ORDER BY e.name",
            {"id": claim_id},
        )
    )


def entity_mentioned_in(conn, entity_id: str) -> list[dict]:
    """Bu entity'nin ADININ GEÇTİĞİ ama öznesi olmadığı claim'ler.

    Entity sayfasının "bu kayıt hakkında hiçbir şey bilmiyoruz" görüntüsünden çıktığı yer
    burası: 52 entity metinlerde geçiyordu ve sayfaları bomboştu."""
    return fetch_all(
        conn.execute(
            "MATCH (c:Claim)-[m:MENTIONS]->(e:Entity {id: $id}) WHERE m.status = 'CONFIRMED' "
            "OPTIONAL MATCH (c)-[:ABOUT_ENTITY]->(subject:Entity) "
            "OPTIONAL MATCH (c)-[:ABOUT_EVENT]->(event:Event) "
            "RETURN c.id AS claim_id, c.text AS text, c.knowledge_state AS knowledge_state, "
            "c.confidence AS confidence, c.created_at AS created_at, m.matched_on AS matched_on, "
            "subject.id AS subject_entity_id, subject.name AS subject_entity_name, "
            "event.id AS about_event_id, event.title AS about_event_title "
            "ORDER BY c.created_at DESC",
            {"id": entity_id},
        )
    )
