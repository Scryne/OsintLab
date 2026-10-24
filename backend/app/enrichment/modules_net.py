"""Faz 30 — altyapı modülleri: DNS, ters DNS, RDAP, sertifika şeffaflığı, Wayback, InternetDB,
RIPEstat, urlscan ve (aktif) HTTP parmak izi.

Her modülün kaynağı ve sınırı 2026-10-24'te canlı istekle doğrulandı (bkz. Roadmap Faz 30)."""
from __future__ import annotations

import base64
import ipaddress
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from app.collector import CollectorFetchError
from app.db import DATA_ROOT, atomic_write_text
from app.enrichment.base import ACTIVE, PASSIVE, Ctx, Module, ModuleError, Pivot, Result, Target
from app.selectorindex import registrable_domain, valid_domain, valid_public_ip

DNS_TYPES = ("A", "AAAA", "CNAME", "MX", "NS", "TXT", "CAA", "SOA")
_DNS_TYPE_CODES = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR", 15: "MX", 16: "TXT", 28: "AAAA", 257: "CAA"}
_DOH = [
    ("cloudflare-dns.com", "https://cloudflare-dns.com/dns-query"),
    ("dns.google", "https://dns.google/resolve"),
]
_VERIFICATION_RE = re.compile(
    r"^(google-site-verification|facebook-domain-verification|MS|apple-domain-verification|atlassian-domain-verification|"
    r"docusign|adobe-idp-site-verification|globalsign-domain-verification|stripe-verification|zoom-domain-verification|"
    r"onetrust-domain-verification|dropbox-domain-verification|slack-domain-verification|_?github-verification|"
    r"cisco-ci-domain-verification|openai-domain-verification|anthropic-domain-verification)[=:]\s*(\S+)",
    re.I,
)


def _domain_of(target: Target) -> str:
    if target.kind == "domain":
        return target.value
    if target.kind == "email":
        return target.value.rsplit("@", 1)[1]
    if target.kind == "url":
        return (urlparse(target.value).hostname or "").lower()
    raise ModuleError("Bu modül yalnızca alan adı, e-posta ya da URL alır.")


def _doh(ctx: Ctx, name: str, rtype: str) -> tuple[dict, str]:
    last: Exception | None = None
    for host, base in _DOH:
        try:
            data = ctx.get_json(base, {"name": name, "type": rtype}, headers={"Accept": "application/dns-json"})
            return data, host
        except (CollectorFetchError, ModuleError) as exc:
            last = exc
    raise ModuleError(f"DNS çözümleyicilerine ulaşılamadı: {last}")


def run_dns(ctx: Ctx, target: Target) -> Result:
    domain = _domain_of(target)
    if not valid_domain(domain):
        raise ModuleError(f"{domain!r} geçerli bir alan adı değil.")
    records: dict[str, list[str]] = {}
    status: dict[str, int] = {}
    dnssec = None
    resolver = None
    for rtype in DNS_TYPES:
        data, resolver = _doh(ctx, domain, rtype)
        status[rtype] = data.get("Status", -1)
        if rtype == "A":
            dnssec = bool(data.get("AD"))
        answers = [a for a in data.get("Answer", []) or [] if _DNS_TYPE_CODES.get(a.get("type")) == rtype]
        if answers:
            records[rtype] = sorted({str(a.get("data", "")).strip() for a in answers})
    if status.get("A") == 3:
        return Result({"domain": domain, "nxdomain": True, "resolver": resolver, "records": {}})

    pivots: list[Pivot] = []
    for rtype in ("A", "AAAA"):
        for ip in records.get(rtype, []):
            if valid_public_ip(ip):
                pivots.append(Pivot("resolves_to", "ip", str(ipaddress.ip_address(ip))))
    for value in records.get("CNAME", []):
        host = value.rstrip(".").lower()
        if valid_domain(host):
            pivots.append(Pivot("alias_of", "domain", host))
    for value in records.get("MX", []):
        host = value.split()[-1].rstrip(".").lower()
        if valid_domain(host):
            pivots.append(Pivot("mail_via", "domain", host))
    for value in records.get("NS", []):
        host = value.rstrip(".").lower()
        if valid_domain(host):
            pivots.append(Pivot("nameserver", "domain", host))

    spf_includes: list[str] = []
    verifications: list[dict] = []
    for raw in records.get("TXT", []):
        txt = raw.strip('"').replace('" "', "")
        if txt.lower().startswith("v=spf1"):
            for inc in re.findall(r"include:([^\s]+)", txt):
                inc = inc.lower().rstrip(".")
                spf_includes.append(inc)
                if valid_domain(inc):
                    pivots.append(Pivot("spf_include", "domain", inc))
            for ip4 in re.findall(r"ip4:([0-9.]+)(?!/)", txt):
                if valid_public_ip(ip4):
                    pivots.append(Pivot("spf_allows", "ip", ip4))
        m = _VERIFICATION_RE.match(txt)
        if m:
            verifications.append({"service": m.group(1), "token": m.group(2)})
    return Result(
        {
            "domain": domain,
            "resolver": resolver,
            "dnssec_validated": dnssec,
            "records": records,
            "spf_includes": spf_includes,
            "verification_tokens": verifications,
        },
        pivots,
    )


def _reverse_name(ip: str) -> str:
    return ipaddress.ip_address(ip).reverse_pointer


def run_ptr(ctx: Ctx, target: Target) -> Result:
    if not valid_public_ip(target.value):
        raise ModuleError("Genel (public) olmayan bir IP adresi zenginleştirilmez.")
    data, resolver = _doh(ctx, _reverse_name(target.value), "PTR")
    names = sorted({str(a.get("data", "")).rstrip(".").lower() for a in data.get("Answer", []) or [] if a.get("type") == 12})
    pivots = [Pivot("ptr", "domain", n) for n in names if valid_domain(n)]
    return Result({"ip": target.value, "resolver": resolver, "ptr": names}, pivots)


# --- RDAP ---------------------------------------------------------------------------

_BOOTSTRAP = {
    "domain": "https://data.iana.org/rdap/dns.json",
    "ip4": "https://data.iana.org/rdap/ipv4.json",
    "ip6": "https://data.iana.org/rdap/ipv6.json",
    "asn": "https://data.iana.org/rdap/asn.json",
}
_BOOTSTRAP_DIR = DATA_ROOT / "cache" / "rdap"


def _bootstrap(ctx: Ctx, key: str) -> dict:
    """IANA'nın RDAP bootstrap dosyası haftada bir yenilenir. Sorgu değil, genel bir dosya —
    hiçbir hedef bilgisi sızdırmaz; yine de her koşuda indirilmez."""
    path = _BOOTSTRAP_DIR / f"{key}.json"
    if path.is_file():
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        if age < timedelta(days=7):
            return json.loads(path.read_text(encoding="utf-8"))
    data = ctx.get_json(_BOOTSTRAP[key], record=False)
    atomic_write_text(path, json.dumps(data))
    return data


def _rdap_base(ctx: Ctx, target: Target) -> tuple[str, str]:
    if target.kind == "domain":
        data = _bootstrap(ctx, "domain")
        labels = target.value.split(".")
        for i in range(len(labels)):
            suffix = ".".join(labels[i:])
            for entry in data.get("services", []):
                if suffix in entry[0]:
                    return entry[1][0], f"domain/{target.value}"
        raise ModuleError(f".{labels[-1]} alan adları için IANA'da kayıtlı bir RDAP sunucusu yok (birçok ülke kodu yalnızca WHOIS sunuyor).")
    if target.kind == "ip":
        ip = ipaddress.ip_address(target.value)
        data = _bootstrap(ctx, "ip4" if ip.version == 4 else "ip6")
        best = None
        for entry in data.get("services", []):
            for prefix in entry[0]:
                net = ipaddress.ip_network(prefix, strict=False)
                if ip in net and (best is None or net.prefixlen > best[0]):
                    best = (net.prefixlen, entry[1][0])
        if best:
            return best[1], f"ip/{target.value}"
        raise ModuleError("Bu IP için RDAP sunucusu bulunamadı.")
    number = int(target.value[2:])
    data = _bootstrap(ctx, "asn")
    for entry in data.get("services", []):
        for rng in entry[0]:
            lo, _, hi = rng.partition("-")
            if int(lo) <= number <= int(hi or lo):
                return entry[1][0], f"autnum/{number}"
    raise ModuleError("Bu ASN için RDAP sunucusu bulunamadı.")


def _vcard_field(entity: dict, field: str) -> str | None:
    card = entity.get("vcardArray")
    if not (isinstance(card, list) and len(card) == 2):
        return None
    for item in card[1]:
        if isinstance(item, list) and item and item[0] == field:
            value = item[3]
            return " ".join(value) if isinstance(value, list) else str(value)
    return None


def _rdap_entities(entities: list[dict], depth: int = 0) -> list[dict]:
    out = []
    for ent in entities or []:
        roles = ent.get("roles", [])
        out.append({
            "roles": roles,
            "handle": ent.get("handle"),
            "name": _vcard_field(ent, "fn"),
            "org": _vcard_field(ent, "org"),
            "email": _vcard_field(ent, "email") if ({"abuse", "registrar"} & set(roles)) else None,
        })
        if depth < 1:
            out.extend(_rdap_entities(ent.get("entities", []), depth + 1))
    return out


def run_rdap(ctx: Ctx, target: Target) -> Result:
    if target.kind == "ip" and not valid_public_ip(target.value):
        raise ModuleError("Genel (public) olmayan bir IP adresi zenginleştirilmez.")
    queried = None
    if target.kind == "domain":
        # Kayıt kuruluşu yalnızca KAYITLI alan adını bilir: `www.cisa.gov` sorusu 404 döner ve
        # "kayıtlı değil" diye yanlış okunurdu (2026-10-24'te gerçek veride yakalandı).
        queried = registrable_domain(target.value)
        target = Target(target.type, target.id, target.kind, queried)
    base, path = _rdap_base(ctx, target)
    # Bootstrap'tan gelen sunucu güvenilir bir kaynaktan (IANA) geliyor; registry'ler sık sık
    # başka bir host'a yönlendiriyor (ARIN → RIPE), o yüzden bilinen RIR'ler de izinli.
    ctx.allow(urlparse(base).hostname or "", "rdap.arin.net", "rdap.db.ripe.net", "rdap.apnic.net",
              "rdap.lacnic.net", "rdap.afrinic.net")
    try:
        data = ctx.get_json(base.rstrip("/") + "/" + path, headers={"Accept": "application/rdap+json"})
    except CollectorFetchError as exc:
        if exc.status_code == 404 and target.kind == "domain":
            # Kayıt kuruluşu bu adı tanımıyor: alan adı kayıtlı değil (süresi dolmuş ya da silinmiş
            # olabilir). Bu bir HATA değil, başlı başına bir bulgu — eski bir C2 alanı için tipik.
            return Result({"server": urlparse(base).hostname, "queried": queried, "registered": False,
                           "note": "Kayıt kuruluşu bu alan adını tanımıyor — şu an kayıtlı değil."})
        raise
    events = {e.get("eventAction"): e.get("eventDate") for e in data.get("events", []) or []}
    entities = _rdap_entities(data.get("entities", []))
    summary: dict = {
        "server": urlparse(base).hostname,
        "queried": queried,
        "registered": True,
        "handle": data.get("handle"),
        "name": data.get("name") or data.get("ldhName"),
        "status": data.get("status", []),
        "events": events,
        "entities": entities,
        "port43": data.get("port43"),
    }
    pivots: list[Pivot] = []
    if target.kind == "domain":
        ns = sorted({(n.get("ldhName") or "").lower().rstrip(".") for n in data.get("nameservers", []) or []} - {""})
        summary["nameservers"] = ns
        summary["registrar"] = next((e["name"] or e["org"] for e in entities if "registrar" in e["roles"]), None)
        summary["secure_dns"] = bool((data.get("secureDNS") or {}).get("delegationSigned"))
        created = events.get("registration")
        if created:
            try:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(created.replace("Z", "+00:00"))
                summary["age_days"] = age.days
            except ValueError:
                pass
        pivots += [Pivot("nameserver", "domain", n) for n in ns if valid_domain(n)]
    elif target.kind == "ip":
        summary.update({
            "start": data.get("startAddress"),
            "end": data.get("endAddress"),
            "cidrs": [f"{c.get('v4prefix') or c.get('v6prefix')}/{c.get('length')}" for c in data.get("cidr0_cidrs", []) or []],
            "country": data.get("country"),
            "type": data.get("type"),
        })
    else:
        summary.update({"country": data.get("country"), "range": [data.get("startAutnum"), data.get("endAutnum")]})
    return Result(summary, pivots)


# --- Sertifika şeffaflığı -------------------------------------------------------------

CT_SUBDOMAIN_CAP = 500
CT_PIVOT_CAP = 100


def run_crtsh(ctx: Ctx, target: Target) -> Result:
    domain = _domain_of(target)
    try:
        # Kimlik araması (`q=alan`) apex'i ve alt alanları birlikte döndürür; `%.alan` apex'i
        # dışarıda bırakıyordu. crt.sh büyük alanlarda yavaş: okuma zaman aşımı 40 sn.
        rows = ctx.get_json("https://crt.sh/", {"q": domain, "output": "json"}, max_seconds=90, timeout=40,
                            max_bytes=40_000_000)
        provider = "crt.sh"
    except (CollectorFetchError, ModuleError) as exc:
        # crt.sh sık sık 502 veriyor; Cert Spotter'ın anonim katmanı yedek (bkz. Faz 30 notları).
        try:
            issuances = ctx.get_json("https://api.certspotter.com/v1/issuances",
                                     {"domain": domain, "include_subdomains": "true", "expand": "dns_names"})
        except (CollectorFetchError, ModuleError):
            raise ModuleError(f"crt.sh ve Cert Spotter'a ulaşılamadı: {exc}") from exc
        rows = [{"name_value": "\n".join(i.get("dns_names", [])), "not_before": i.get("not_before"),
                 "not_after": i.get("not_after"), "issuer_name": (i.get("issuer") or {}).get("name", "")} for i in issuances]
        provider = "Cert Spotter"
    if not isinstance(rows, list):
        raise ModuleError("Sertifika kaynağı beklenmeyen bir yanıt döndürdü.")
    names: set[str] = set()
    wildcard = False
    issuers: Counter = Counter()
    dates: list[str] = []
    for row in rows:
        for name in str(row.get("name_value", "")).split("\n"):
            name = name.strip().lower().rstrip(".")
            if name.startswith("*."):
                wildcard = True
                name = name[2:]
            if name == domain or name.endswith("." + domain):
                names.add(name)
        issuer = row.get("issuer_name") or ""
        org = re.search(r"O=([^,]+)", issuer)
        issuers[(org.group(1) if org else issuer).strip('" ')] += 1
        if row.get("not_before"):
            dates.append(str(row["not_before"]))
    subdomains = sorted(n for n in names if n != domain)
    pivots = [Pivot("subdomain_of", "domain", s, "in") for s in subdomains[:CT_PIVOT_CAP] if valid_domain(s)]
    return Result(
        {
            "domain": domain,
            "provider": provider,
            "certificate_count": len(rows),
            "first_issued": min(dates) if dates else None,
            "last_issued": max(dates) if dates else None,
            "wildcard": wildcard,
            "issuers": issuers.most_common(8),
            "subdomain_count": len(subdomains),
            "subdomains": subdomains[:CT_SUBDOMAIN_CAP],
            "pivots_capped": len(subdomains) > CT_PIVOT_CAP,
        },
        pivots,
    )


# --- Wayback --------------------------------------------------------------------------

def run_wayback(ctx: Ctx, target: Target) -> Result:
    if target.kind == "url":
        lookup, match = target.value, "exact"
    else:
        lookup, match = _domain_of(target), "domain"
    closest = ctx.get_json("https://archive.org/wayback/available", {"url": lookup}, timeout=30)
    snap = (closest.get("archived_snapshots") or {}).get("closest") or {}
    base = {"url": lookup, "output": "json", "fl": "timestamp,original,statuscode,mimetype"}
    if match == "domain":
        base["matchType"] = "domain"
    cdx = "https://web.archive.org/cdx/search/cdx"
    # Ölçüldü (2026-10-24): CDX'te `limit=1` (en eski) 29 sn, `filter=statuscode:200` 23 sn
    # sürerken `limit=-1` 2 sn ve filtresiz örnek 5 sn. En eski kopya bunun yerine Availability
    # API'sine 1996 tarihi verilerek bulunuyor: "1996'ya en yakın" = ilk kopya, bir saniyede.
    earliest = ctx.get_json("https://archive.org/wayback/available", {"url": lookup, "timestamp": "19960101"}, timeout=30)
    first_snap = (earliest.get("archived_snapshots") or {}).get("closest") or {}
    first = [["timestamp"], [first_snap.get("timestamp")]] if first_snap else None
    # CDX zaman zaman dakikalarca yanıt vermiyor. Bu iki çağrı özetin yalnızca bir kısmı; biri
    # düşerse modülün tamamı düşmesin, eksik kalan kısım özet içinde söylensin.
    notes = []
    try:
        last = ctx.get_json(cdx, {**base, "limit": "-1"}, timeout=30, max_seconds=45)
    except (CollectorFetchError, ModuleError) as exc:
        last, _ = None, notes.append(f"Son kopya sorgusu yanıt vermedi: {exc}")
    try:
        sample = ctx.get_json(cdx, {**base, "collapse": "urlkey", "limit": "150"}, timeout=30, max_seconds=45)
    except (CollectorFetchError, ModuleError) as exc:
        sample, _ = None, notes.append(f"Adres örneği alınamadı: {exc}")

    def row(data):
        return dict(zip(data[0], data[1], strict=False)) if isinstance(data, list) and len(data) > 1 else None

    urls = [dict(zip(sample[0], r, strict=False)) for r in sample[1:]] if isinstance(sample, list) and len(sample) > 1 else []
    urls = [u for u in urls if str(u.get("statuscode", "")).startswith(("2", "3"))]
    mimes = Counter(u.get("mimetype") for u in urls)

    def ts(value):
        if not value:
            return None
        try:
            return datetime.strptime(value[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            return value

    f, la = row(first), row(last)
    return Result({
        "query": lookup,
        "match": match,
        "first_capture": ts(f and f.get("timestamp")),
        "last_capture": ts(la and la.get("timestamp")),
        "closest": {"url": snap.get("url"), "timestamp": ts(snap.get("timestamp")), "status": snap.get("status")} if snap else None,
        "sample_urls": [{"url": u.get("original"), "timestamp": ts(u.get("timestamp")), "mimetype": u.get("mimetype")} for u in urls[:150]],
        "mimetypes": mimes.most_common(10),
        "sample_capped": len(urls) >= 150,
        "notes": notes,
    })


# --- IP katmanı ------------------------------------------------------------------------

def _public_ip(target: Target) -> str:
    if target.kind == "url":
        host = urlparse(target.value).hostname or ""
        if valid_public_ip(host):
            return host
    if target.kind == "ip" and valid_public_ip(target.value):
        return target.value
    raise ModuleError("Genel (public) bir IP adresi gerekiyor.")


def run_internetdb(ctx: Ctx, target: Target) -> Result:
    ip = _public_ip(target)
    try:
        data = ctx.get_json(f"https://internetdb.shodan.io/{ip}")
    except CollectorFetchError as exc:
        if exc.status_code == 404:
            return Result({"ip": ip, "found": False, "ports": [], "hostnames": [], "vulns": [], "cpes": [], "tags": []})
        raise
    pivots = [Pivot("hostname", "domain", h.lower()) for h in data.get("hostnames", []) if valid_domain(h)]
    pivots += [Pivot("exposes", "cve", v.upper()) for v in data.get("vulns", []) if v.upper().startswith("CVE-")]
    return Result({"ip": ip, "found": True, **{k: data.get(k, []) for k in ("ports", "hostnames", "vulns", "cpes", "tags")}}, pivots)


def _ripe(ctx: Ctx, call: str, resource: str) -> dict:
    data = ctx.get_json(f"https://stat.ripe.net/data/{call}/data.json", {"resource": resource, "sourceapp": "osintlab"})
    if data.get("status") != "ok":
        raise ModuleError(f"RIPEstat {call} başarısız: {data.get('messages')}")
    return data.get("data") or {}


def run_ripestat_ip(ctx: Ctx, target: Target) -> Result:
    ip = _public_ip(target)
    prefix = _ripe(ctx, "prefix-overview", ip)
    geo = _ripe(ctx, "maxmind-geo-lite", ip)
    abuse = _ripe(ctx, "abuse-contact-finder", ip)
    asns = [{"asn": a.get("asn"), "holder": a.get("holder")} for a in prefix.get("asns", []) or []]
    locations = []
    for res in geo.get("located_resources", []) or []:
        for loc in res.get("locations", []) or []:
            locations.append({k: loc.get(k) for k in ("country", "city", "latitude", "longitude", "covered_percentage")})
    pivots = [Pivot("announced_by", "asn", f"AS{a['asn']}") for a in asns if a.get("asn")]
    return Result({
        "ip": ip,
        "prefix": prefix.get("resource"),
        "announced": prefix.get("announced"),
        "asns": asns,
        "block": (prefix.get("block") or {}).get("desc"),
        "locations": locations,
        "abuse_contacts": abuse.get("abuse_contacts", []),
    }, pivots)


def run_ripestat_asn(ctx: Ctx, target: Target) -> Result:
    overview = _ripe(ctx, "as-overview", target.value)
    prefixes = _ripe(ctx, "announced-prefixes", target.value)
    items = prefixes.get("prefixes", []) or []
    v4 = [p["prefix"] for p in items if ":" not in p.get("prefix", "")]
    v6 = [p["prefix"] for p in items if ":" in p.get("prefix", "")]
    return Result({
        "asn": target.value,
        "holder": overview.get("holder"),
        "announced": overview.get("announced"),
        "block": (overview.get("block") or {}).get("desc"),
        "prefix_count": {"ipv4": len(v4), "ipv6": len(v6)},
        "prefixes_v4": v4[:200],
        "prefixes_v6": v6[:100],
    })


# --- urlscan ----------------------------------------------------------------------------

def run_urlscan(ctx: Ctx, target: Target) -> Result:
    if target.kind == "ip":
        query = f"ip:{target.value}"
    elif target.kind == "url":
        query = f'page.url:"{target.value}"'
    else:
        query = f"domain:{_domain_of(target)}"
    data = ctx.get_json("https://urlscan.io/api/v1/search/", {"q": query, "size": "50"})
    results = []
    pivots: list[Pivot] = []
    seen_ips: set[str] = set()
    for item in data.get("results", []) or []:
        page = item.get("page") or {}
        task = item.get("task") or {}
        results.append({
            "time": task.get("time"),
            "url": page.get("url"),
            "domain": page.get("domain"),
            "ip": page.get("ip"),
            "asn": page.get("asn"),
            "asnname": page.get("asnname"),
            "country": page.get("country"),
            "server": page.get("server"),
            "title": page.get("title"),
            "status": page.get("status"),
            "screenshot": item.get("screenshot"),
            "result": item.get("result"),
        })
        ip = page.get("ip")
        if target.kind != "ip" and ip and valid_public_ip(ip) and ip not in seen_ips:
            seen_ips.add(ip)
            pivots.append(Pivot("scanned_on", "ip", ip))
    return Result({"query": query, "total": data.get("total"), "has_more": data.get("has_more"), "results": results}, pivots[:30])


# --- Aktif: HTTP parmak izi ---------------------------------------------------------------

_SECURITY_HEADERS = (
    "strict-transport-security", "content-security-policy", "x-frame-options", "x-content-type-options",
    "referrer-policy", "permissions-policy",
)


def _mmh3_32(data: bytes, seed: int = 0) -> int:
    """MurmurHash3 x86_32 — Shodan'ın `http.favicon.hash` değeri bununla hesaplanıyor. Bağımlılık
    eklememek için saf Python."""
    c1, c2 = 0xCC9E2D51, 0x1B873593
    length = len(data)
    h = seed & 0xFFFFFFFF
    rounded = length & ~3
    for i in range(0, rounded, 4):
        k = int.from_bytes(data[i:i + 4], "little")
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
        h = ((h << 13) | (h >> 19)) & 0xFFFFFFFF
        h = (h * 5 + 0xE6546B64) & 0xFFFFFFFF
    k = 0
    tail = length & 3
    if tail == 3:
        k ^= data[rounded + 2] << 16
    if tail >= 2:
        k ^= data[rounded + 1] << 8
    if tail >= 1:
        k ^= data[rounded]
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
    h ^= length
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 16
    return h - 0x100000000 if h & 0x80000000 else h


def favicon_hash(content: bytes) -> int:
    return _mmh3_32(base64.encodebytes(content))


def run_http(ctx: Ctx, target: Target) -> Result:
    """Hedefin kendi sunucusuna istek atar — AKTİF. Yalnızca hedef host'a izin verilir ve SSRF
    katmanı yine çalışır: allowlist hedefi içerse bile özel bir IP'ye çözülen ad reddedilir."""
    if target.kind == "url":
        url = target.value
    else:
        url = f"https://{_domain_of(target)}/"
    host = urlparse(url).hostname or ""
    ctx.allow(host, f"www.{host}" if not host.startswith("www.") else host[4:])
    from bs4 import BeautifulSoup

    content, ctype = ctx.get(url, max_bytes=3_000_000)
    soup = BeautifulSoup(content, "html.parser")
    title = " ".join(soup.title.get_text().split()) if soup.title else None
    generator = soup.find("meta", attrs={"name": "generator"})
    icon_link = soup.find("link", rel=lambda v: v and "icon" in (v if isinstance(v, list) else [v]))
    icon_url = None
    if icon_link and icon_link.get("href") and not icon_link["href"].startswith("data:"):
        from urllib.parse import urljoin

        icon_url = urljoin(url, icon_link["href"])
    else:
        icon_url = f"{urlparse(url).scheme}://{host}/favicon.ico"
    icon_hash = None
    icon_note = None
    try:
        icon_host = urlparse(icon_url).hostname or ""
        if icon_host in ctx.hosts:
            icon_bytes, _ = ctx.get(icon_url, max_bytes=500_000, record=False)
            icon_hash = favicon_hash(icon_bytes)
        else:
            icon_note = f"favicon başka bir host'ta ({icon_host}) — aktif modül yalnızca hedef host'a istek atar."
    except (CollectorFetchError, ModuleError) as exc:
        icon_note = f"favicon alınamadı: {exc}"
    links = Counter()
    for a in soup.find_all(["a", "script", "link", "img", "iframe"], href=True) + soup.find_all(["script", "img", "iframe"], src=True):
        ref = a.get("href") or a.get("src")
        h = (urlparse(ref).hostname or "").lower()
        if h and h != host:
            links[h] += 1
    pivots = [Pivot("links_to", "domain", h) for h, _ in links.most_common(25) if valid_domain(h)]
    trackers = sorted(set(re.findall(r"\b(UA-\d{4,10}-\d{1,4}|G-[A-Z0-9]{6,12}|GTM-[A-Z0-9]{4,9}|ca-pub-\d{10,20})\b",
                                     content.decode("utf-8", errors="replace"))))
    return Result({
        "url": url,
        "content_type": ctype,
        "title": title,
        "generator": generator.get("content") if generator else None,
        "favicon_url": icon_url,
        "favicon_mmh3": icon_hash,
        "favicon_note": icon_note,
        "analytics_ids": trackers,
        "external_hosts": links.most_common(40),
        "security_headers_note": "Yanıt başlıkları toplayıcı katmanında saklanmıyor; yalnızca gövde analiz edildi.",
    }, pivots)


MODULES = [
    Module("dns", "DNS kayıtları", "Cloudflare / Google DoH",
           "A, AAAA, CNAME, MX, NS, TXT, CAA, SOA kayıtları; SPF içerikleri ve site doğrulama belirteçleri (ortak sahiplik pivotu).",
           "selector", ("domain", "email", "url"), PASSIVE, frozenset({"cloudflare-dns.com", "dns.google"}), run_dns,
           cache_hours=6, docs_url="https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/make-api-requests/dns-json/",
           terms_note="Çözümleyici hedefin ad sunucusuna sorar; sorgunun kaynağı sen değil, çözümleyicidir."),
    Module("ptr", "Ters DNS", "Cloudflare / Google DoH", "IP adresinin PTR kaydı.",
           "selector", ("ip",), PASSIVE, frozenset({"cloudflare-dns.com", "dns.google"}), run_ptr, cache_hours=24),
    Module("rdap", "RDAP (WHOIS)", "IANA bootstrap → kayıt kuruluşu",
           "Kayıt tarihi, kayıt şirketi, durum, ad sunucuları; IP bloğu sahibi; ASN sahibi. Alan adının yaşı taze kurulmuş altyapıyı ele verir.",
           "selector", ("domain", "ip", "asn"), PASSIVE, frozenset({"data.iana.org"}), run_rdap, cache_hours=72,
           docs_url="https://about.rdap.org/"),
    Module("crtsh", "Sertifika şeffaflığı", "crt.sh (yedek: Cert Spotter)",
           "Alan adı için yayımlanmış bütün TLS sertifikaları — gizli alt alan adlarını ve altyapının kuruluş tarihini gösterir.",
           "selector", ("domain", "email", "url"), PASSIVE, frozenset({"crt.sh", "api.certspotter.com"}), run_crtsh,
           cache_hours=72, docs_url="https://crt.sh/", terms_note="crt.sh dakikada ~5 isteği kaldırıyor; istekler 12 sn aralıkla atılır."),
    Module("wayback", "Wayback Machine", "Internet Archive",
           "İlk/son arşiv tarihi, en yakın kopya ve arşivlenmiş adres örneği — silinmiş sayfaların izi.",
           "selector", ("domain", "url", "email"), PASSIVE, frozenset({"archive.org", "web.archive.org"}), run_wayback,
           cache_hours=72, docs_url="https://archive.org/help/wayback_api.php"),
    Module("internetdb", "Shodan InternetDB", "Shodan",
           "Açık portlar, ana makine adları, bilinen açıklar (CVE), CPE ve etiketler. Haftalık güncellenir.",
           "selector", ("ip", "url"), PASSIVE, frozenset({"internetdb.shodan.io"}), run_internetdb, cache_hours=48,
           docs_url="https://internetdb.shodan.io/", terms_note="Yalnızca ticari olmayan kullanım."),
    Module("ripestat-ip", "RIPEstat: IP", "RIPE NCC",
           "IP'yi duyuran ASN ve önek, coğrafi konum (MaxMind GeoLite), kötüye kullanım iletişimi.",
           "selector", ("ip", "url"), PASSIVE, frozenset({"stat.ripe.net"}), run_ripestat_ip, cache_hours=48,
           docs_url="https://stat.ripe.net/docs/02.data-api/"),
    Module("ripestat-asn", "RIPEstat: ASN", "RIPE NCC", "ASN sahibi ve duyurduğu önekler.",
           "selector", ("asn",), PASSIVE, frozenset({"stat.ripe.net"}), run_ripestat_asn, cache_hours=72,
           docs_url="https://stat.ripe.net/docs/02.data-api/"),
    Module("urlscan", "urlscan.io araması", "urlscan.io",
           "Alan adı/IP için herkese açık tarama geçmişi: sayfa başlığı, sunucu, IP, ülke, ekran görüntüsü.",
           "selector", ("domain", "ip", "url"), PASSIVE, frozenset({"urlscan.io"}), run_urlscan, cache_hours=24,
           docs_url="https://urlscan.io/docs/search/", terms_note="Anonim arama yalnızca herkese açık taramaları ve son ~30 günü görür."),
    Module("http", "HTTP parmak izi", "Hedefin kendi sunucusu",
           "Sayfa başlığı, generator, favicon hash'i (Shodan `http.favicon.hash` pivotu), analytics kimlikleri, dış bağlantılar.",
           "selector", ("domain", "url"), ACTIVE, frozenset(), run_http, cache_hours=24,
           terms_note="AKTİF: hedef sunucu isteği loglarında görür."),
]
