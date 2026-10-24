"""Faz 33 — genel arama (komut paleti).

Tek kutudan her şey: yapıştırılan değer bir seçiciyse türü tanınır (hızlı pivot), değilse
entity, olay, investigation, kaynak, seçici ve claim metinlerinde aranır. Sonuçlar türe göre
gruplu ve her grup sınırlı — palet bir gezinme aracı, liste sayfalarının yerine geçmiyor.

Eşleşme bilerek basit (büyük/küçük harf duyarsız içerme): ölçek yüzlerce kayıt, bir tam metin
indeksi bu ölçekte kazandırdığından fazlasını karmaşıklaştırırdı."""
from urllib.parse import quote

from fastapi import APIRouter, Query

from app import pivot, selectorindex
from app.db import fetch_all, get_connection
from app.report import STATE_LABELS

router = APIRouter(prefix="/search", tags=["search"])

GROUP_LIMIT = 8


def _norm(value: str | None) -> str:
    return (value or "").casefold()


@router.get("")
def search(q: str = Query(..., min_length=1, max_length=500)) -> dict:
    needle = q.strip().casefold()
    conn = get_connection()
    out: dict = {"query": q, "detected": None, "groups": []}

    found = selectorindex.detect(q)
    if found:
        kind, value = found
        sid = selectorindex.selector_id(kind, value)
        out["detected"] = {
            "id": sid, "kind": kind, "value": value, "label": selectorindex.KIND_LABELS[kind],
            "exists": pivot.get_selector(sid) is not None,
        }

    def group(key: str, label: str, items: list[dict]) -> None:
        if items:
            out["groups"].append({"key": key, "label": label, "items": items[:GROUP_LIMIT], "total": len(items)})

    entities = fetch_all(conn.execute(
        "MATCH (e:Entity) RETURN e.id AS id, e.name AS name, e.entity_type AS type, e.aliases AS aliases"
    ))
    group("entities", "Entity'ler", [
        {"id": e["id"], "title": e["name"], "subtitle": e["type"], "href": f"/entities/{e['id']}"}
        for e in entities
        if needle in _norm(e["name"]) or any(needle in _norm(a) for a in (e["aliases"] or []))
    ])

    sels = pivot.list_selectors(q=needle, limit=GROUP_LIMIT * 2)
    group("selectors", "Seçiciler", [
        {"id": s["id"], "title": s["value"], "subtitle": selectorindex.KIND_LABELS.get(s["kind"], s["kind"]),
         "kind": s["kind"], "href": f"/selectors/view?id={quote(s['id'], safe='')}"}
        for s in sels["items"]
    ])

    events = fetch_all(conn.execute("MATCH (e:Event) RETURN e.id AS id, e.title AS title, e.event_type AS type"))
    group("events", "Olaylar", [
        {"id": e["id"], "title": e["title"], "subtitle": e["type"], "href": f"/events/{e['id']}"}
        for e in events if needle in _norm(e["title"])
    ])

    invs = fetch_all(conn.execute(
        "MATCH (i:Investigation) RETURN i.id AS id, i.title AS title, i.research_question AS question, i.status AS status"
    ))
    group("investigations", "Investigation'lar", [
        {"id": i["id"], "title": i["title"], "subtitle": i["status"], "href": f"/investigations/{i['id']}"}
        for i in invs if needle in _norm(i["title"]) or needle in _norm(i["question"])
    ])

    sources = fetch_all(conn.execute("MATCH (s:Source) RETURN s.id AS id, s.name AS name, s.url AS url"))
    group("sources", "Kaynaklar", [
        {"id": s["id"], "title": s["name"], "subtitle": s["url"], "href": f"/sources/{s['id']}"}
        for s in sources if needle in _norm(s["name"]) or needle in _norm(s["url"])
    ])

    claims = fetch_all(conn.execute(
        "MATCH (c:Claim) RETURN c.id AS id, c.text AS text, c.knowledge_state AS state ORDER BY c.created_at DESC"
    ))
    hits = []
    for c in claims:
        text = c["text"] or ""
        pos = _norm(text).find(needle)
        if pos < 0:
            continue
        start = max(0, pos - 40)
        snippet = ("…" if start else "") + " ".join(text[start:pos + len(needle) + 80].split()) + "…"
        hits.append({"id": c["id"], "title": snippet, "subtitle": STATE_LABELS.get(c["state"], c["state"]),
                     "href": f"/claims/view?id={c['id']}"})
    group("claims", "Claim'ler", hits)
    return out
