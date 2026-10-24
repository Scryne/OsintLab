"""Faz 30 — kurum ve dünya modülleri: GDELT haber araması, Wikidata, GLEIF, OFAC yaptırım
taraması, Nominatim ters coğrafi kodlama, ADS-B anlık hava trafiği.

**Eşleşme kimlik değildir.** Wikidata, GLEIF ve yaptırım modülleri bir ADA bakıyor; aynı adı taşıyan
farklı kurumlar olabilir. Sonuçlar "aday" olarak sunulur, hiçbiri otomatik olarak entity'ye
bağlanmaz (Design Principle #7). Yaptırım eşleşmesi özellikle ağır bir iddiadır: arayüz bunu
"olası eşleşme — doğrulanmadı" diye gösterir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.enrichment import datasets
from app.enrichment.base import LOCAL, PASSIVE, Ctx, Module, ModuleError, Pivot, Result, Target
from app.selectorindex import KIND_LABELS, normalize_domain, valid_domain


# --- GDELT ---------------------------------------------------------------------------

def _gdelt_query(target: Target) -> str:
    value = target.value
    if target.type == "entity" or target.kind in ("cve", "attack", "domain", "ip", "asn"):
        return f'"{value}"'
    raise ModuleError("GDELT araması bu seçici türü için anlamlı değil.")


def run_gdelt(ctx: Ctx, target: Target) -> Result:
    query = _gdelt_query(target)
    data = ctx.get_json(
        "https://api.gdeltproject.org/api/v2/doc/doc",
        {"query": query, "mode": "artlist", "format": "json", "maxrecords": "75", "timespan": "3months", "sort": "datedesc"},
        max_seconds=40,
    )
    articles = []
    for a in (data.get("articles") if isinstance(data, dict) else None) or []:
        seen = a.get("seendate")
        try:
            seen = datetime.strptime(seen, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat() if seen else None
        except ValueError:
            pass
        articles.append({
            "title": a.get("title"),
            "url": a.get("url"),
            "domain": a.get("domain"),
            "seen_at": seen,
            "language": a.get("language"),
            "source_country": a.get("sourcecountry"),
        })
    domains = sorted({a["domain"] for a in articles if a.get("domain")})
    return Result({"query": query, "window": "3 ay", "count": len(articles), "distinct_sources": len(domains),
                   "articles": articles})


# --- Wikidata -------------------------------------------------------------------------

_WD_PROPS = {
    "P856": "official_website",
    "P17": "country",
    "P571": "inception",
    "P749": "parent_organization",
    "P1278": "lei",
    "P452": "industry",
    "P159": "headquarters",
    "P112": "founded_by",
    "P1128": "employees",
    "P414": "stock_exchange",
    "P2002": "twitter",
    "P31": "instance_of",
}


def run_wikidata(ctx: Ctx, target: Target) -> Result:
    search = ctx.get_json("https://www.wikidata.org/w/api.php", {
        "action": "wbsearchentities", "search": target.value, "language": "en", "uselang": "en",
        "format": "json", "limit": "6", "type": "item",
    })
    candidates = [{"qid": c.get("id"), "label": c.get("label"), "description": c.get("description"),
                   "url": c.get("concepturi")} for c in search.get("search", []) or []]
    if not candidates:
        return Result({"query": target.value, "candidates": [], "best": None})
    qid = candidates[0]["qid"]
    entity = ctx.get_json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json")
    body = (entity.get("entities") or {}).get(qid, {})
    claims = body.get("claims", {}) or {}
    facts: dict[str, list] = {}
    linked: set[str] = set()
    for prop, key in _WD_PROPS.items():
        for st in claims.get(prop, [])[:8]:
            value = ((st.get("mainsnak") or {}).get("datavalue") or {}).get("value")
            if isinstance(value, dict) and "id" in value:
                linked.add(value["id"])
                facts.setdefault(key, []).append({"qid": value["id"]})
            elif isinstance(value, dict) and "time" in value:
                facts.setdefault(key, []).append(value["time"].lstrip("+")[:10])
            elif isinstance(value, dict) and "amount" in value:
                facts.setdefault(key, []).append(value["amount"].lstrip("+"))
            elif value is not None:
                facts.setdefault(key, []).append(value)
    if linked:
        labels = ctx.get_json("https://www.wikidata.org/w/api.php", {
            "action": "wbgetentities", "ids": "|".join(sorted(linked)[:50]), "props": "labels",
            "languages": "en", "format": "json",
        })
        names = {k: ((v.get("labels") or {}).get("en") or {}).get("value") for k, v in (labels.get("entities") or {}).items()}
        for items in facts.values():
            for item in items:
                if isinstance(item, dict) and "qid" in item:
                    item["label"] = names.get(item["qid"])
    suggestions = []
    for site in facts.get("official_website", []):
        if isinstance(site, str):
            from urllib.parse import urlparse

            host = normalize_domain(urlparse(site).hostname or "")
            if valid_domain(host):
                suggestions.append({"kind": "domain", "value": host, "label": KIND_LABELS["domain"], "why": "Wikidata P856 (resmi web sitesi)"})
    best = {
        "qid": qid,
        "label": ((body.get("labels") or {}).get("en") or {}).get("value"),
        "description": ((body.get("descriptions") or {}).get("en") or {}).get("value"),
        "aliases": [a.get("value") for a in ((body.get("aliases") or {}).get("en") or [])][:15],
        "facts": facts,
        "url": f"https://www.wikidata.org/wiki/{qid}",
    }
    return Result({"query": target.value, "candidates": candidates, "best": best, "suggested_selectors": suggestions})


# --- GLEIF ----------------------------------------------------------------------------

def run_gleif(ctx: Ctx, target: Target) -> Result:
    # `filter[fulltext]` adresler dahil her alanda arıyor ve "Siemens" için ilk sırada alakasız bir
    # İsveç vakfı döndürdü (2026-10-24). Yasal ad üzerinden bulanık tamamlama doğru adayları veriyor;
    # kayıtlar sonra LEI listesiyle tek istekte alınıyor.
    completions = ctx.get_json("https://api.gleif.org/api/v1/fuzzycompletions",
                               {"field": "entity.legalName", "q": target.value},
                               headers={"Accept": "application/vnd.api+json"})
    leis = []
    for c in completions.get("data", []) or []:
        lei = (((c.get("relationships") or {}).get("lei-records") or {}).get("data") or {}).get("id")
        if lei and lei not in leis:
            leis.append(lei)
    if not leis:
        return Result({"query": target.value, "total": 0, "records": []})
    data = ctx.get_json("https://api.gleif.org/api/v1/lei-records",
                        {"filter[lei]": ",".join(leis[:10]), "page[size]": "10"},
                        headers={"Accept": "application/vnd.api+json"})
    records = []
    for item in data.get("data", []) or []:
        attrs = item.get("attributes", {}) or {}
        ent = attrs.get("entity", {}) or {}
        reg = attrs.get("registration", {}) or {}
        addr = ent.get("legalAddress", {}) or {}
        hq = ent.get("headquartersAddress", {}) or {}
        records.append({
            "lei": attrs.get("lei"),
            "legal_name": (ent.get("legalName") or {}).get("name"),
            "other_names": [n.get("name") for n in ent.get("otherNames", []) or []][:5],
            "jurisdiction": ent.get("jurisdiction"),
            "legal_form": (ent.get("legalForm") or {}).get("id"),
            "status": ent.get("status"),
            "category": ent.get("category"),
            "legal_address": ", ".join(filter(None, [addr.get("city"), addr.get("country")])),
            "hq_address": ", ".join(filter(None, [hq.get("city"), hq.get("country")])),
            "registered_at": reg.get("initialRegistrationDate"),
            "registration_status": reg.get("status"),
            "url": f"https://search.gleif.org/#/record/{attrs.get('lei')}",
        })
    order = {lei: i for i, lei in enumerate(leis)}
    records.sort(key=lambda r: order.get(r["lei"], 99))
    return Result({"query": target.value, "total": len(records), "records": records})


# --- Yaptırım (OFAC SDN) --------------------------------------------------------------------

def _match_names(index: dict, query: str) -> list[dict]:
    tokens = datasets.normalize_name(query)
    if not tokens:
        return []
    qset = set(tokens)
    joined = " ".join(tokens)
    scored: dict[str, tuple[float, str]] = {}
    for norm, ent, raw in index["names"]:
        if not norm:
            continue
        if norm == joined:
            score = 1.0
        else:
            nset = set(norm.split())
            if not qset <= nset and not nset <= qset:
                continue
            overlap = len(qset & nset) / len(qset | nset)
            if overlap < 0.6:
                continue
            score = round(0.6 + 0.35 * overlap, 3)
        if score > scored.get(ent, (0, ""))[0]:
            scored[ent] = (score, raw)
    out = []
    for ent, (score, matched) in sorted(scored.items(), key=lambda kv: -kv[1][0])[:15]:
        entry = index["entries"].get(ent, {})
        out.append({**entry, "score": score, "matched_name": matched})
    return out


def run_sanctions(ctx: Ctx, target: Target) -> Result:
    index, meta = datasets.load("ofac", auto_refresh=True)
    if target.type == "entity":
        queries = [target.value, *target.aliases]
        matches: dict[str, dict] = {}
        for q in queries:
            for m in _match_names(index, q):
                if m["ent_num"] not in matches or m["score"] > matches[m["ent_num"]]["score"]:
                    matches[m["ent_num"]] = {**m, "query": q}
        found = sorted(matches.values(), key=lambda m: -m["score"])
        summary = {"queries": queries, "match_count": len(found), "matches": found,
                   "caution": "Ad eşleşmesi kimlik değildir — aynı adı taşıyan farklı kişi/kurumlar olabilir. Doğrulamadan iddia olarak kullanma."}
    else:
        key = target.value.lower() if target.value.lower().startswith(("0x", "bc1")) else target.value
        hit = index["crypto"].get(key)
        entry = index["entries"].get(hit["ent_num"]) if hit else None
        summary = {"address": target.value, "listed": bool(hit), "currency": hit and hit["currency"], "entry": entry}
    summary["list_downloaded_at"] = meta["downloaded_at"]
    return Result(summary, raw_override={"dataset": "ofac", "dataset_sha256": meta["sha256"],
                                         "dataset_downloaded_at": meta["downloaded_at"], "summary": summary})


# --- Koordinat: Nominatim ve ADS-B ------------------------------------------------------------

def _coord(target: Target) -> tuple[float, float]:
    lat, lon = (float(x) for x in target.value.split(","))
    return lat, lon


def run_nominatim(ctx: Ctx, target: Target) -> Result:
    lat, lon = _coord(target)
    data = ctx.get_json("https://nominatim.openstreetmap.org/reverse",
                        {"lat": f"{lat:.6f}", "lon": f"{lon:.6f}", "format": "jsonv2", "addressdetails": "1", "zoom": "18"})
    if data.get("error"):
        return Result({"lat": lat, "lon": lon, "found": False, "error": data["error"]})
    return Result({
        "lat": lat, "lon": lon, "found": True,
        "display_name": data.get("display_name"),
        "category": data.get("category"),
        "type": data.get("type"),
        "address": data.get("address", {}),
        "osm": {"type": data.get("osm_type"), "id": data.get("osm_id")},
        "osm_url": f"https://www.openstreetmap.org/{data.get('osm_type')}/{data.get('osm_id')}" if data.get("osm_type") else None,
        "attribution": data.get("licence"),
    })


def run_adsb(ctx: Ctx, target: Target) -> Result:
    lat, lon = _coord(target)
    data = ctx.get_json(f"https://api.adsb.lol/v2/point/{lat:.4f}/{lon:.4f}/50")
    aircraft = []
    for ac in data.get("ac", []) or []:
        aircraft.append({
            "hex": ac.get("hex"),
            "flight": (ac.get("flight") or "").strip() or None,
            "registration": ac.get("r"),
            "type": ac.get("t"),
            "description": ac.get("desc"),
            "altitude_ft": ac.get("alt_baro"),
            "ground_speed_kt": ac.get("gs"),
            "track": ac.get("track"),
            "lat": ac.get("lat"),
            "lon": ac.get("lon"),
            "squawk": ac.get("squawk"),
            "military": bool((ac.get("dbFlags") or 0) & 1),
            "category": ac.get("category"),
        })
    aircraft.sort(key=lambda a: (not a["military"], a["flight"] or a["hex"] or ""))
    return Result({
        "lat": lat, "lon": lon, "radius_nm": 50,
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "count": len(aircraft),
        "military_count": sum(1 for a in aircraft if a["military"]),
        "aircraft": aircraft[:200],
        "note": "Anlık görüntü — yalnızca sorgu anındaki ADS-B yayınları. Askeri/devlet uçakları çoğu zaman yayın yapmaz.",
    })


MODULES = [
    Module("gdelt", "GDELT haber araması", "GDELT Project",
           "Son 3 ayda dünya basınında bu değeri geçiren haberler — bağımsız doğrulayıcı kaynak bulmak için.",
           "selector", ("cve", "attack", "domain", "ip", "asn"), PASSIVE, frozenset({"api.gdeltproject.org"}), run_gdelt,
           cache_hours=12, docs_url="https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/",
           terms_note="GDELT sık sık 429 döndürüyor; istekler 6 sn aralıkla atılır."),
    Module("gdelt-entity", "GDELT haber araması", "GDELT Project",
           "Son 3 ayda dünya basınında bu adı geçiren haberler — bağımsız doğrulayıcı kaynak bulmak için.",
           "entity", (), PASSIVE, frozenset({"api.gdeltproject.org"}), run_gdelt, cache_hours=12,
           docs_url="https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"),
    Module("wikidata", "Wikidata", "Wikimedia",
           "Ad eşleşen Wikidata öğeleri; en iyi adayın resmi sitesi, ülkesi, kuruluş tarihi, ana şirketi, LEI'si.",
           "entity", (), PASSIVE, frozenset({"www.wikidata.org"}), run_wikidata, cache_hours=24 * 7,
           docs_url="https://www.wikidata.org/w/api.php"),
    Module("gleif", "GLEIF (LEI)", "Global Legal Entity Identifier Foundation",
           "Tüzel kişi kayıtları: yasal ad, yargı alanı, adres, kayıt durumu.",
           "entity", (), PASSIVE, frozenset({"api.gleif.org"}), run_gleif, cache_hours=24 * 7,
           docs_url="https://api.gleif.org/docs"),
    Module("sanctions", "Yaptırım taraması (OFAC SDN)", "ABD Hazinesi OFAC (yerel veri seti)",
           "Ad ve diğer adlarla OFAC SDN listesinde olası eşleşmeler. Eşleşme kimlik değildir.",
           "entity", (), LOCAL, frozenset(), run_sanctions, cache_hours=24, datasets=("ofac",),
           docs_url="https://ofac.treasury.gov/specially-designated-nationals-and-blocked-persons-list-sdn-human-readable-lists"),
    Module("sanctions-crypto", "Yaptırımlı kripto adresi", "ABD Hazinesi OFAC (yerel veri seti)",
           "Adres OFAC SDN listesinde 'Digital Currency Address' olarak geçiyor mu?",
           "selector", ("btc", "eth"), LOCAL, frozenset(), run_sanctions, cache_hours=24, datasets=("ofac",)),
    Module("nominatim", "Ters coğrafi kodlama", "OpenStreetMap Nominatim",
           "Koordinatın adresi ve OSM nesnesi.",
           "selector", ("coord",), PASSIVE, frozenset({"nominatim.openstreetmap.org"}), run_nominatim, cache_hours=24 * 30,
           docs_url="https://operations.osmfoundation.org/policies/nominatim/",
           terms_note="Saniyede en fazla 1 istek; veri ODbL, atıf gerekir."),
    Module("adsb", "Hava trafiği (ADS-B)", "adsb.lol",
           "Koordinatın 50 deniz mili çevresinde şu an yayın yapan uçaklar.",
           "selector", ("coord",), PASSIVE, frozenset({"api.adsb.lol"}), run_adsb, cache_hours=0.05,
           docs_url="https://api.adsb.lol/docs", terms_note="Veri ODbL. Anlık görüntü; önbellek 3 dk."),
]

__all__ = ["MODULES", "Pivot"]
