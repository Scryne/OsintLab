"""Faz 29/31 — seçici katmanının graf işlemleri: indeksleme, listeleme, ayrıntı, pivot.

Çıkarma mantığı `app/selectorindex.py`de (saf, grafa dokunmaz); burası onun sonucunu grafa yazar
ve okur. İndeksleme idempotent: `MERGE` hem düğümde hem kenarda, yani aynı gözlemi iki kez taramak
ikinci bir kenar üretmez. Toplu yazma `UNWIND` ile — 4.408 gözlemlik geriye dönük tarama tek tek
sorguyla ~dakikalar sürerdi, parça başına tek sorguyla saniyeler (ölçüldü: 5.000 kenar 0,3 sn).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from app import selectorindex
from app.archive import ARCHIVE_TYPE
from app.db import bump_data_version, fetch_all, fetch_one, get_connection, graph_lock

logger = logging.getLogger(__name__)

STATUSES = ("ACTIVE", "IGNORED")
REINDEX_CHUNK = 400


def _merge_rows(conn, rows: list[dict], target: str) -> int:
    """`rows`: {sid, kind, value, tid, ctx, defanged, occ}. Döndürür: yeni kenar sayısı."""
    if not rows:
        return 0
    rel, label = ("SEEN_IN", "Observation") if target == "observation" else ("SEEN_IN_EVIDENCE", "Evidence")
    now = datetime.now(timezone.utc)
    before = fetch_one(conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS n"))["n"]
    conn.execute(
        "UNWIND $rows AS r MERGE (s:Selector {id: r.sid}) "
        "ON CREATE SET s.kind = r.kind, s.value = r.value, s.status = 'ACTIVE', "
        "s.origin = 'extracted', s.note = '', s.created_at = $now",
        {"rows": rows, "now": now},
    )
    conn.execute(
        f"UNWIND $rows AS r MATCH (s:Selector {{id: r.sid}}), (t:{label} {{id: r.tid}}) "
        f"MERGE (s)-[e:{rel}]->(t) "
        "ON CREATE SET e.context = r.ctx, e.defanged = r.defanged, e.occurrences = r.occ, e.created_at = $now",
        {"rows": rows, "now": now},
    )
    after = fetch_one(conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS n"))["n"]
    return after - before


def _rows_for(target_id: str, text: str, source_url: str | None = None) -> list[dict]:
    own = selectorindex.registrable_domain(urlparse(source_url).hostname or "") if source_url else ""
    return [
        {
            "sid": s.id, "kind": s.kind, "value": s.value, "tid": target_id,
            "ctx": s.context, "defanged": s.defanged, "occ": s.occurrences,
        }
        for s in selectorindex.extract_unique(text or "")
        if not (own and selectorindex.is_self_reference(s.kind, s.value, own))
    ]


def index_observation(observation_id: str, text: str, source_url: str | None = None) -> int:
    """Yeni bir gözlemi tarar. Gözlem yaratma yolunu ASLA düşürmemeli — çağıran try/except'le sarar.

    Kaynağın kendine referansı gösterge değildir: CISA advisory'lerinin her birinin altındaki
    `cisa.gov/privacy-policy` bağlantısı, ilk ölçümde listenin ilk dört satırını (85'er geçiş)
    kaplıyordu. Gözlemin kaynak alan adıyla aynı kayıtlı alana ait alan adı/URL/e-posta atlanır."""
    rows = _rows_for(observation_id, text, source_url)
    if not rows:
        return 0
    with graph_lock:
        return _merge_rows(get_connection(), rows, "observation")


def index_evidence(evidence_id: str, text: str) -> int:
    rows = _rows_for(evidence_id, text)
    if not rows:
        return 0
    with graph_lock:
        return _merge_rows(get_connection(), rows, "evidence")


def reindex_all() -> dict:
    """Bütün gözlem ve belge metinlerini yeniden tarar (geriye dönük indeks ve kural değişikliği
    sonrası). Kilit parça başına alınır: tek kilitte tüm tur arayüzdeki her yazmayı bekletirdi."""
    conn = get_connection()
    started = datetime.now(timezone.utc)
    stats = {"observations_scanned": 0, "evidence_scanned": 0, "new_sightings": 0}
    # Yeniden tarama bir YENİDEN KURMA: görülme kenarları silinip baştan kuruluyor, çünkü kural
    # değişikliği (ör. kaynağın kendine referansının dışlanması) eski kenarları geçersiz kılabilir
    # ve MERGE yalnızca ekleyebilir. Seçici düğümleri, notları, durumları ve zenginleştirme
    # koşuları korunur; geriye hiçbir bağı kalmayan "metinden çıkarılmış" düğümler silinir.
    sightings_before = fetch_one(conn.execute("MATCH ()-[r:SEEN_IN]->() RETURN count(r) AS n"))["n"]
    with graph_lock:
        conn.execute("MATCH (:Selector)-[r:SEEN_IN]->(:Observation) DELETE r")
    observations = fetch_all(conn.execute(
        "MATCH (o:Observation) RETURN o.id AS id, o.raw_content AS text, o.source_url AS url"
    ))
    rows: list[dict] = []
    for obs in observations:
        rows.extend(_rows_for(obs["id"], obs["text"], obs["url"]))
        stats["observations_scanned"] += 1
        if len(rows) >= REINDEX_CHUNK:
            with graph_lock:
                _merge_rows(conn, rows, "observation")
            rows = []
    if rows:
        with graph_lock:
            _merge_rows(conn, rows, "observation")
    # Kaynak arşivleri (Faz 26) gözlem metninin birebir kopyası: indekslenseler her seçici "iki
    # yerde görüldü" sayılırdı. Yalnızca kullanıcının yüklediği belgeler taranır; önceki bir
    # taramanın arşivlere açtığı kenarlar temizlenir.
    with graph_lock:
        conn.execute(
            "MATCH (:Selector)-[r:SEEN_IN_EVIDENCE]->(e:Evidence) WHERE e.evidence_type = $t DELETE r",
            {"t": ARCHIVE_TYPE},
        )
    docs = fetch_all(conn.execute(
        "MATCH (e:Evidence) WHERE e.extracted_text IS NOT NULL AND e.extracted_text <> '' "
        "AND (e.evidence_type IS NULL OR e.evidence_type <> $t) "
        "RETURN e.id AS id, e.extracted_text AS text",
        {"t": ARCHIVE_TYPE},
    ))
    for doc in docs:
        doc_rows = _rows_for(doc["id"], doc["text"])
        stats["evidence_scanned"] += 1
        if doc_rows:
            with graph_lock:
                stats["new_sightings"] += _merge_rows(conn, doc_rows, "evidence")
    with graph_lock:
        orphans = fetch_all(conn.execute(
            "MATCH (s:Selector) WHERE s.origin = 'extracted' AND s.status = 'ACTIVE' "
            "AND NOT EXISTS { MATCH (s)-[:SEEN_IN]->() } AND NOT EXISTS { MATCH (s)-[:SEEN_IN_EVIDENCE]->() } "
            "AND NOT EXISTS { MATCH (s)-[:PIVOT]-() } AND NOT EXISTS { MATCH (s)-[:SELECTOR_OF]->() } "
            "AND NOT EXISTS { MATCH (:EnrichmentRun)-[:RAN_ON]->(s) } RETURN s.id AS id"
        ))
        for row in orphans:
            conn.execute("MATCH (s:Selector {id: $id}) DETACH DELETE s", {"id": row["id"]})
    stats["orphans_removed"] = len(orphans)
    # Net değişim: yeniden kurulumdan önceki ve sonraki gözlem geçişi farkı (+ belge geçişleri).
    after = fetch_one(conn.execute("MATCH ()-[r:SEEN_IN]->() RETURN count(r) AS n"))["n"]
    # Gözlem tarafında NET değişim (yeniden kurulumdan önce/sonra) + belgelerde yeni açılanlar:
    # ikinci bir tarama hiçbir şey değiştirmediyse 0.
    stats["new_sightings"] += after - sightings_before
    bump_data_version()
    stats["selectors_total"] = fetch_one(conn.execute("MATCH (s:Selector) RETURN count(s) AS n"))["n"]
    stats["duration_seconds"] = round((datetime.now(timezone.utc) - started).total_seconds(), 2)
    return stats


# --- Okuma ------------------------------------------------------------------------

_SEL = (
    "s.id AS id, s.kind AS kind, s.value AS value, s.status AS status, s.origin AS origin, "
    "s.note AS note, s.created_at AS created_at"
)


def list_selectors(
    kind: str | None = None,
    q: str | None = None,
    include_ignored: bool = False,
    sort: str = "sightings",
    limit: int = 200,
    offset: int = 0,
) -> dict:
    conn = get_connection()
    where = []
    params: dict = {}
    if kind:
        where.append("s.kind = $kind")
        params["kind"] = kind
    if q:
        where.append("lower(s.value) CONTAINS $q")
        params["q"] = q.strip().lower()
    if not include_ignored:
        where.append("s.status <> 'IGNORED'")
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = fetch_all(conn.execute(
        f"MATCH (s:Selector) {clause} "
        "OPTIONAL MATCH (s)-[:SEEN_IN]->(o:Observation) "
        "WITH s, count(o) AS obs, min(o.observed_at) AS first_seen, max(o.observed_at) AS last_seen "
        "OPTIONAL MATCH (s)-[:SEEN_IN_EVIDENCE]->(e:Evidence) "
        "WITH s, obs, first_seen, last_seen, count(e) AS docs "
        "OPTIONAL MATCH (r:EnrichmentRun)-[:RAN_ON]->(s) "
        "WITH s, obs, first_seen, last_seen, docs, count(r) AS runs "
        "OPTIONAL MATCH (s)-[:SELECTOR_OF]->(en:Entity) "
        f"RETURN {_SEL}, obs AS observation_count, docs AS evidence_count, runs AS enrichment_count, "
        "count(en) AS entity_count, first_seen, last_seen",
        params,
    ))
    if sort == "recent":
        rows.sort(key=lambda r: (r["last_seen"] or r["created_at"]), reverse=True)
    elif sort == "value":
        rows.sort(key=lambda r: r["value"])
    else:
        rows.sort(key=lambda r: (r["observation_count"] + r["evidence_count"], r["last_seen"] or r["created_at"]), reverse=True)
    total = len(rows)
    return {"total": total, "items": rows[offset:offset + limit]}


def kind_counts() -> list[dict]:
    conn = get_connection()
    return fetch_all(conn.execute(
        "MATCH (s:Selector) WHERE s.status <> 'IGNORED' "
        "RETURN s.kind AS kind, count(s) AS count ORDER BY count DESC"
    ))


def get_selector(selector_id: str) -> dict | None:
    conn = get_connection()
    return fetch_one(conn.execute(f"MATCH (s:Selector {{id: $id}}) RETURN {_SEL}", {"id": selector_id}))


def selector_detail(selector_id: str, sighting_limit: int = 100) -> dict | None:
    sel = get_selector(selector_id)
    if sel is None:
        return None
    conn = get_connection()
    sightings = fetch_all(conn.execute(
        "MATCH (s:Selector {id: $id})-[r:SEEN_IN]->(o:Observation) "
        "OPTIONAL MATCH (o)-[:PRODUCED]->(c:Claim) "
        "RETURN o.id AS observation_id, o.source_url AS source_url, o.observed_at AS observed_at, "
        "o.promoted AS promoted, r.context AS context, r.defanged AS defanged, "
        "r.occurrences AS occurrences, c.id AS claim_id, c.knowledge_state AS claim_state "
        "ORDER BY observed_at DESC",
        {"id": selector_id},
    ))
    from urllib.parse import urlparse

    hosts = sorted({(urlparse(s["source_url"] or "").hostname or "") for s in sightings} - {""})
    documents = fetch_all(conn.execute(
        "MATCH (s:Selector {id: $id})-[r:SEEN_IN_EVIDENCE]->(e:Evidence) "
        "RETURN e.id AS evidence_id, e.file_path AS file_path, e.evidence_type AS evidence_type, "
        "r.context AS context, r.defanged AS defanged, r.occurrences AS occurrences",
        {"id": selector_id},
    ))
    entities = fetch_all(conn.execute(
        "MATCH (s:Selector {id: $id})-[r:SELECTOR_OF]->(e:Entity) "
        "RETURN e.id AS id, e.name AS name, e.entity_type AS entity_type, r.note AS note, r.created_at AS linked_at",
        {"id": selector_id},
    ))
    pivots_out = fetch_all(conn.execute(
        "MATCH (s:Selector {id: $id})-[p:PIVOT]->(t:Selector) "
        "RETURN t.id AS id, t.kind AS kind, t.value AS value, p.relation AS relation, p.module AS module, "
        "p.run_id AS run_id, p.first_seen AS first_seen, p.last_seen AS last_seen, 'out' AS direction "
        "ORDER BY relation, value",
        {"id": selector_id},
    ))
    pivots_in = fetch_all(conn.execute(
        "MATCH (t:Selector)-[p:PIVOT]->(s:Selector {id: $id}) "
        "RETURN t.id AS id, t.kind AS kind, t.value AS value, p.relation AS relation, p.module AS module, "
        "p.run_id AS run_id, p.first_seen AS first_seen, p.last_seen AS last_seen, 'in' AS direction "
        "ORDER BY relation, value",
        {"id": selector_id},
    ))
    co = fetch_all(conn.execute(
        "MATCH (s:Selector {id: $id})-[:SEEN_IN]->(o:Observation)<-[:SEEN_IN]-(t:Selector) "
        "WHERE t.id <> $id AND t.status <> 'IGNORED' "
        "RETURN t.id AS id, t.kind AS kind, t.value AS value, count(DISTINCT o) AS shared "
        "ORDER BY shared DESC LIMIT 40",
        {"id": selector_id},
    ))
    return {
        "selector": sel,
        "label": selectorindex.KIND_LABELS.get(sel["kind"], sel["kind"]),
        "observation_count": len({s["observation_id"] for s in sightings}),
        "source_hosts": hosts,
        "sightings": sightings[:sighting_limit],
        "documents": documents,
        "entities": entities,
        "pivots": pivots_out + pivots_in,
        "co_occurring": co,
    }


# --- Yazma ----------------------------------------------------------------------------

def upsert_selector(kind: str, value: str, origin: str = "manual", note: str = "") -> tuple[dict, bool]:
    """Düğüm yoksa yaratır. Döndürür: (seçici, yeni mi)."""
    conn = get_connection()
    sid = selectorindex.selector_id(kind, value)
    with graph_lock:
        existing = get_selector(sid)
        if existing is not None:
            return existing, False
        conn.execute(
            "CREATE (:Selector {id: $id, kind: $kind, value: $value, status: 'ACTIVE', origin: $origin, "
            "note: $note, created_at: $now})",
            {"id": sid, "kind": kind, "value": value, "origin": origin, "note": note, "now": datetime.now(timezone.utc)},
        )
    return get_selector(sid), True


def update_selector(selector_id: str, status: str | None, note: str | None) -> dict | None:
    conn = get_connection()
    if get_selector(selector_id) is None:
        return None
    if status is not None:
        conn.execute("MATCH (s:Selector {id: $id}) SET s.status = $v", {"id": selector_id, "v": status})
    if note is not None:
        conn.execute("MATCH (s:Selector {id: $id}) SET s.note = $v", {"id": selector_id, "v": note})
    return get_selector(selector_id)


def link_entity(selector_id: str, entity_id: str, note: str = "") -> bool:
    conn = get_connection()
    with graph_lock:
        ok = fetch_one(conn.execute(
            "MATCH (s:Selector {id: $s}), (e:Entity {id: $e}) RETURN count(*) AS n", {"s": selector_id, "e": entity_id}
        ))["n"]
        if not ok:
            return False
        conn.execute(
            "MATCH (s:Selector {id: $s}), (e:Entity {id: $e}) MERGE (s)-[r:SELECTOR_OF]->(e) "
            "ON CREATE SET r.note = $note, r.created_at = $now",
            {"s": selector_id, "e": entity_id, "note": note, "now": datetime.now(timezone.utc)},
        )
    return True


def unlink_entity(selector_id: str, entity_id: str) -> bool:
    conn = get_connection()
    n = fetch_one(conn.execute(
        "MATCH (s:Selector {id: $s})-[r:SELECTOR_OF]->(e:Entity {id: $e}) RETURN count(r) AS n",
        {"s": selector_id, "e": entity_id},
    ))["n"]
    if not n:
        return False
    conn.execute(
        "MATCH (s:Selector {id: $s})-[r:SELECTOR_OF]->(e:Entity {id: $e}) DELETE r", {"s": selector_id, "e": entity_id}
    )
    return True


def entity_selectors(entity_id: str) -> list[dict]:
    conn = get_connection()
    return fetch_all(conn.execute(
        f"MATCH (s:Selector)-[r:SELECTOR_OF]->(e:Entity {{id: $id}}) RETURN {_SEL}, r.note AS link_note ORDER BY s.kind, s.value",
        {"id": entity_id},
    ))


def add_pivot(conn, from_id: str, to_id: str, relation: str, module: str, run_id: str) -> None:
    """Çağıran `graph_lock`u tutar. Aynı (kaynak, hedef, ilişki) için ikinci kenar açılmaz;
    tekrar görüldüğünde `last_seen` ve son koşu güncellenir — "bu IP o alan adına HÂLÂ çözülüyor
    mu" sorusunun cevabı bu iki tarih arasındaki farkta."""
    now = datetime.now(timezone.utc)
    existing = fetch_one(conn.execute(
        "MATCH (a:Selector {id: $a})-[p:PIVOT]->(b:Selector {id: $b}) WHERE p.relation = $rel RETURN count(p) AS n",
        {"a": from_id, "b": to_id, "rel": relation},
    ))["n"]
    if existing:
        conn.execute(
            "MATCH (a:Selector {id: $a})-[p:PIVOT]->(b:Selector {id: $b}) WHERE p.relation = $rel "
            "SET p.last_seen = $now, p.run_id = $run",
            {"a": from_id, "b": to_id, "rel": relation, "now": now, "run": run_id},
        )
        return
    conn.execute(
        "MATCH (a:Selector {id: $a}), (b:Selector {id: $b}) "
        "CREATE (a)-[:PIVOT {relation: $rel, module: $module, run_id: $run, first_seen: $now, last_seen: $now}]->(b)",
        {"a": from_id, "b": to_id, "rel": relation, "module": module, "run": run_id, "now": now},
    )


def ensure_selector(conn, kind: str, value: str, origin: str = "enrichment") -> str:
    """Çağıran `graph_lock`u tutar."""
    sid = selectorindex.selector_id(kind, value)
    conn.execute(
        "MERGE (s:Selector {id: $id}) ON CREATE SET s.kind = $kind, s.value = $value, s.status = 'ACTIVE', "
        "s.origin = $origin, s.note = '', s.created_at = $now",
        {"id": sid, "kind": kind, "value": value, "origin": origin, "now": datetime.now(timezone.utc)},
    )
    return sid


GRAPH_NODE_CAP = 150


def pivot_graph(selector_id: str, depth: int = 2) -> dict | None:
    """Seçicinin pivot komşuluğu (iki yönlü, `depth` adım) + bağlı entity'ler. Düğüm sayısı
    sınırlı: bir alan adının 100 alt alan adı ikinci adımda binlere çıkabilir."""
    if get_selector(selector_id) is None:
        return None
    conn = get_connection()
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    seen_edges: set[tuple[str, str, str]] = set()
    frontier = [selector_id]
    truncated = False
    for level in range(depth + 1):
        next_frontier: list[str] = []
        for sid in frontier:
            if sid in nodes:
                continue
            sel = get_selector(sid)
            if sel is None:
                continue
            nodes[sid] = {"id": sid, "kind": sel["kind"], "value": sel["value"], "level": level, "type": "selector"}
            if level == depth:
                continue
            rows = fetch_all(conn.execute(
                "MATCH (a:Selector {id: $id})-[p:PIVOT]->(b:Selector) RETURN a.id AS src, b.id AS dst, p.relation AS rel, p.module AS module "
                "UNION ALL MATCH (a:Selector)-[p:PIVOT]->(b:Selector {id: $id}) RETURN a.id AS src, b.id AS dst, p.relation AS rel, p.module AS module",
                {"id": sid},
            ))
            for row in rows:
                key = (row["src"], row["dst"], row["rel"])
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append({"source": row["src"], "target": row["dst"], "relation": row["rel"], "module": row["module"]})
                other = row["dst"] if row["src"] == sid else row["src"]
                if other not in nodes:
                    if len(nodes) + len(next_frontier) >= GRAPH_NODE_CAP:
                        truncated = True
                        continue
                    next_frontier.append(other)
        frontier = next_frontier
    # Kesilen kenarların ucundaki düğümler çizilemez.
    edges = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
    ents = fetch_all(conn.execute(
        "MATCH (s:Selector)-[:SELECTOR_OF]->(e:Entity) WHERE s.id IN $ids "
        "RETURN s.id AS sid, e.id AS eid, e.name AS name, e.entity_type AS etype",
        {"ids": list(nodes)},
    ))
    for row in ents:
        nid = f"entity:{row['eid']}"
        nodes.setdefault(nid, {"id": nid, "kind": "entity", "value": row["name"], "entity_type": row["etype"], "type": "entity", "level": -1})
        edges.append({"source": row["sid"], "target": nid, "relation": "belongs_to", "module": None})
    return {"root": selector_id, "nodes": list(nodes.values()), "edges": edges, "truncated": truncated}
