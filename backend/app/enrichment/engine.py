"""Faz 30 — zenginleştirme motoru: modülü çalıştırır, sonucu değişmez bir kayda çevirir.

Bir koşunun izi üç yerde kalır ve üçü birbirini doğrular:
1. `data/enrichment/<yyyy-mm>/<run_id>.json` — ham yanıtlar + özet + pivotlar.
2. `EnrichmentRun` düğümü — dosyanın yolu ve SHA-256'sı, özet (JSON), durum, OPSEC sınıfı.
3. `PIVOT` kenarları — her biri `run_id` taşır; "bu IP o alan adına çözülüyordu" iddiası hangi
   koşudan, hangi ham yanıttan geldiğine kadar izlenebilir.

**Önbellek bir OPSEC kararıdır.** Aynı modül aynı hedefe `cache_hours` içinde ikinci kez
sorulmaz; kullanıcı açıkça "yeniden çalıştır" demedikçe eski koşu döner. Her tekrar sorgu,
araştırma ilgisini üçüncü tarafa bir kez daha gösterir.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app import pivot
from app.collector import CollectorFetchError, CollectorSecurityError
from app.db import DATA_ROOT, atomic_write_text, bump_data_version, fetch_all, fetch_one, get_connection, graph_lock
from app.enrichment import modules_net, modules_vuln, modules_world
from app.enrichment.base import ACTIVE, OPSEC_LABELS, Ctx, Module, ModuleError, Result, Target
from app.selectorindex import KIND_LABELS

logger = logging.getLogger(__name__)

REGISTRY: dict[str, Module] = {m.name: m for m in (*modules_net.MODULES, *modules_vuln.MODULES, *modules_world.MODULES)}
RAW_ROOT = DATA_ROOT / "enrichment"
SETTINGS_PATH = DATA_ROOT / "config" / "enrichment.json"


class EnrichmentError(Exception):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


# --- Ayarlar -------------------------------------------------------------------------

def load_settings() -> dict[str, list[str]]:
    if not SETTINGS_PATH.is_file():
        return {"disabled": [], "enabled_active": []}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.exception("Zenginleştirme ayarları okunamadı — varsayılanlar kullanılıyor")
        return {"disabled": [], "enabled_active": []}
    return {"disabled": list(data.get("disabled", [])), "enabled_active": list(data.get("enabled_active", []))}


def is_enabled(module: Module, settings: dict | None = None) -> bool:
    """Pasif/yerel modüller varsayılan AÇIK, aktif modüller varsayılan KAPALI: hedefin kendi
    sunucusuna istek atmak bilinçli bir tercih olmalı."""
    settings = settings or load_settings()
    if module.opsec == ACTIVE:
        return module.name in settings["enabled_active"]
    return module.name not in settings["disabled"]


def set_enabled(name: str, enabled: bool) -> dict:
    module = REGISTRY.get(name)
    if module is None:
        raise EnrichmentError(f"Bilinmeyen modül: {name}", 404)
    settings = load_settings()
    key = "enabled_active" if module.opsec == ACTIVE else "disabled"
    values = set(settings[key])
    if (module.opsec == ACTIVE) == enabled:
        values.add(name)
    else:
        values.discard(name)
    settings[key] = sorted(values)
    atomic_write_text(SETTINGS_PATH, json.dumps(settings, ensure_ascii=False, indent=2))
    return settings


def describe(module: Module, settings: dict | None = None) -> dict:
    return {
        "name": module.name,
        "label": module.label,
        "provider": module.provider,
        "description": module.description,
        "target": module.target,
        "kinds": list(module.kinds),
        "kind_labels": [KIND_LABELS[k] for k in module.kinds],
        "opsec": module.opsec,
        "opsec_note": OPSEC_LABELS[module.opsec],
        "hosts": sorted(module.hosts),
        "cache_hours": module.cache_hours,
        "docs_url": module.docs_url,
        "terms_note": module.terms_note,
        "datasets": list(module.datasets),
        "enabled": is_enabled(module, settings),
    }


def list_modules() -> list[dict]:
    settings = load_settings()
    return [describe(m, settings) for m in REGISTRY.values()]


# --- Hedef -----------------------------------------------------------------------------

def resolve_target(target_id: str) -> Target:
    conn = get_connection()
    if target_id.startswith("entity:"):
        row = fetch_one(conn.execute(
            "MATCH (e:Entity {id: $id}) RETURN e.id AS id, e.name AS name, e.entity_type AS type, e.aliases AS aliases",
            {"id": target_id[len("entity:"):]},
        ))
        if row is None:
            raise EnrichmentError("Entity bulunamadı", 404)
        return Target("entity", target_id, "entity", row["name"], row["type"], list(row["aliases"] or []))
    if target_id.startswith("claim:"):
        # Claim hedefi yalnızca haber araması için: "bu iddiayı başka kim söylüyor?" (Faz 28'in
        # açık bıraktığı ters arama). Sorgu claim'in başlık satırı.
        from app.monitoring import claim_headline

        row = fetch_one(conn.execute(
            "MATCH (c:Claim {id: $id}) RETURN c.text AS text", {"id": target_id[len("claim:"):]}
        ))
        if row is None:
            raise EnrichmentError("Claim bulunamadı", 404)
        return Target("claim", target_id, "claim", claim_headline(row["text"] or "", limit=160))
    sel = pivot.get_selector(target_id)
    if sel is None:
        raise EnrichmentError("Seçici bulunamadı", 404)
    return Target("selector", sel["id"], sel["kind"], sel["value"])


def modules_for(target_id: str) -> list[dict]:
    target = resolve_target(target_id)
    settings = load_settings()
    latest = {r["module"]: get_run(r["id"]) for r in runs_for(target_id, latest_only=True)}
    out = []
    for module in REGISTRY.values():
        if module.accepts(target):
            info = describe(module, settings)
            info["last_run"] = latest.get(module.name)
            out.append(info)
    return out


# --- Koşu kayıtları ---------------------------------------------------------------------

_RUN = (
    "r.id AS id, r.module AS module, r.selector_id AS target_id, r.target_type AS target_type, r.status AS status, "
    "r.opsec AS opsec, r.request_url AS request_url, r.raw_path AS raw_path, r.raw_sha256 AS raw_sha256, "
    "r.summary AS summary, r.error AS error, r.started_at AS started_at, r.finished_at AS finished_at"
)


def _hydrate(row: dict) -> dict:
    row = dict(row)
    try:
        row["summary"] = json.loads(row["summary"]) if row.get("summary") else None
    except ValueError:
        row["summary"] = None
    module = REGISTRY.get(row["module"])
    row["module_label"] = module.label if module else row["module"]
    return row


def get_run(run_id: str) -> dict | None:
    row = fetch_one(get_connection().execute(f"MATCH (r:EnrichmentRun {{id: $id}}) RETURN {_RUN}", {"id": run_id}))
    if row is None:
        return None
    run = _hydrate(row)
    run["pivots"] = fetch_all(get_connection().execute(
        "MATCH (a:Selector)-[p:PIVOT]->(b:Selector) WHERE p.run_id = $id "
        "RETURN a.id AS from_id, b.id AS to_id, b.kind AS to_kind, b.value AS to_value, a.value AS from_value, "
        "p.relation AS relation",
        {"id": run_id},
    ))
    return run


def runs_for(target_id: str, latest_only: bool = False, limit: int = 200) -> list[dict]:
    rows = fetch_all(get_connection().execute(
        f"MATCH (r:EnrichmentRun) WHERE r.selector_id = $id RETURN {_RUN} ORDER BY r.started_at DESC LIMIT $limit",
        {"id": target_id, "limit": limit},
    ))
    runs = [_hydrate(r) for r in rows]
    if not latest_only:
        return runs
    seen: dict[str, dict] = {}
    for run in runs:
        # En son BAŞARILI koşu esas; yoksa en son deneme (hata mesajı görünsün diye).
        current = seen.get(run["module"])
        if current is None or (current["status"] != "DONE" and run["status"] == "DONE"):
            seen[run["module"]] = run
    return list(seen.values())


def recent_runs(limit: int = 100) -> list[dict]:
    rows = fetch_all(get_connection().execute(
        f"MATCH (r:EnrichmentRun) RETURN {_RUN} ORDER BY r.started_at DESC LIMIT $limit", {"limit": limit}
    ))
    return [_hydrate(r) for r in rows]


def _cached_run(module: Module, target_id: str) -> dict | None:
    if module.cache_hours <= 0:
        return None
    row = fetch_one(get_connection().execute(
        f"MATCH (r:EnrichmentRun) WHERE r.module = $m AND r.selector_id = $t AND r.status = 'DONE' "
        f"RETURN {_RUN} ORDER BY r.finished_at DESC LIMIT 1",
        {"m": module.name, "t": target_id},
    ))
    if row is None or row["finished_at"] is None:
        return None
    if datetime.now(timezone.utc) - row["finished_at"] > timedelta(hours=module.cache_hours):
        return None
    return row


def _write_raw(run_id: str, payload: dict) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    rel = Path(now.strftime("%Y-%m")) / f"{run_id}.json"
    data = json.dumps(payload, ensure_ascii=False, indent=1, default=str).encode("utf-8")
    path = RAW_ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(rel).replace("\\", "/"), hashlib.sha256(data).hexdigest()


def raw_record(run_id: str) -> tuple[dict, bool] | None:
    """(ham kayıt, hash tutuyor mu). Hash tutmuyorsa dosya koşudan sonra değişmiş demektir."""
    run = get_run(run_id)
    if run is None or not run.get("raw_path"):
        return None
    path = (RAW_ROOT / run["raw_path"]).resolve()
    if RAW_ROOT.resolve() not in path.parents or not path.is_file():
        return None
    data = path.read_bytes()
    return json.loads(data.decode("utf-8")), hashlib.sha256(data).hexdigest() == run["raw_sha256"]


def run(name: str, target_id: str, *, force: bool = False, confirm_active: bool = False, wait: bool = True) -> dict:
    """Koşuyu başlatır. `wait=False`: kayıt RUNNING olarak hemen döner, modül arka planda çalışır
    (Wayback'in CDX'i ölçümde 2 dakikayı buldu; arayüz bunu beklememeli, yoklamalı)."""
    module = REGISTRY.get(name)
    if module is None:
        raise EnrichmentError(f"Bilinmeyen modül: {name}", 404)
    target = resolve_target(target_id)
    if not module.accepts(target):
        raise EnrichmentError(f"{module.label} bu hedef türünü ({KIND_LABELS.get(target.kind, target.kind)}) zenginleştirmez.")
    if not is_enabled(module):
        raise EnrichmentError(
            f"{module.label} kapalı. Zenginleştirme ayarlarından açabilirsin"
            + (" — aktif bir modül olduğu için hedefin sunucusuna doğrudan istek atar." if module.opsec == ACTIVE else "."),
            409,
        )
    if module.opsec == ACTIVE and not confirm_active:
        raise EnrichmentError(f"{module.label} AKTİF bir modül: hedefin sunucusuna doğrudan istek atar. Onaylayarak tekrar çalıştır.", 428)
    conn = get_connection()
    with graph_lock:
        running = fetch_one(conn.execute(
            "MATCH (r:EnrichmentRun) WHERE r.module = $m AND r.selector_id = $t AND r.status = 'RUNNING' "
            "RETURN r.id AS id, r.started_at AS started_at ORDER BY r.started_at DESC LIMIT 1",
            {"m": name, "t": target.id},
        ))
        if running and datetime.now(timezone.utc) - running["started_at"] < STALE_AFTER:
            out = get_run(running["id"])
            out["cached"] = False
            return out
        if not force:
            cached = _cached_run(module, target.id)
            if cached is not None:
                out = get_run(cached["id"])
                out["cached"] = True
                return out
        run_id = str(uuid.uuid4())
        started = datetime.now(timezone.utc)
        conn.execute(
            "CREATE (:EnrichmentRun {id: $id, module: $module, selector_id: $target, target_type: $ttype, "
            "status: 'RUNNING', opsec: $opsec, started_at: $started})",
            {"id": run_id, "module": name, "target": target.id, "ttype": target.type, "opsec": module.opsec, "started": started},
        )
        if target.type == "selector":
            conn.execute("MATCH (r:EnrichmentRun {id: $r}), (s:Selector {id: $s}) CREATE (r)-[:RAN_ON]->(s)",
                         {"r": run_id, "s": target.id})
        elif target.type == "entity":
            conn.execute("MATCH (r:EnrichmentRun {id: $r}), (e:Entity {id: $e}) CREATE (r)-[:RAN_ON_ENTITY]->(e)",
                         {"r": run_id, "e": target.id[len("entity:"):]})
        # Claim hedefli koşunun kenarı yok: hedef kimliği (`claim:<id>`) koşunun kendisinde.
    if wait:
        _execute(run_id, module, target, started)
    else:
        threading.Thread(target=_execute, args=(run_id, module, target, started), name=f"enrich-{name}", daemon=True).start()
    out = get_run(run_id)
    out["cached"] = False
    return out


def _execute(run_id: str, module: Module, target: Target, started: datetime) -> None:
    ctx = Ctx(module.hosts)
    status, error = "DONE", None
    result: Result | None = None
    try:
        result = module.run(ctx, target)
    except (ModuleError, CollectorFetchError, CollectorSecurityError, RuntimeError) as exc:
        status, error = "FAILED", str(exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Zenginleştirme %s / %s beklenmedik şekilde çöktü", module.name, target.id)
        status, error = "FAILED", f"Beklenmeyen hata ({type(exc).__name__}): {exc}"
    finished = datetime.now(timezone.utc)

    pivots = result.pivots if result else []
    raw_payload: dict[str, Any] = {
        "run_id": run_id,
        "module": module.name,
        "provider": module.provider,
        "opsec": module.opsec,
        "target": {"id": target.id, "type": target.type, "kind": target.kind, "value": target.value},
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "status": status,
        "error": error,
        "request_urls": ctx.request_urls,
        "responses": result.raw_override if (result and result.raw_override is not None) else ctx.responses,
        "summary": result.summary if result else None,
        "pivots": [p.__dict__ for p in pivots],
    }
    raw_path, raw_sha = _write_raw(run_id, raw_payload)

    conn = get_connection()
    with graph_lock:
        conn.execute(
            "MATCH (r:EnrichmentRun {id: $id}) SET r.status = $status, r.request_url = $url, r.raw_path = $raw_path, "
            "r.raw_sha256 = $raw_sha, r.summary = $summary, r.error = $error, r.finished_at = $finished",
            {
                "id": run_id, "status": status, "url": ctx.request_urls[0] if ctx.request_urls else None,
                "raw_path": raw_path, "raw_sha": raw_sha,
                "summary": json.dumps(result.summary, ensure_ascii=False, default=str) if result else None,
                "error": error, "finished": finished,
            },
        )
        if target.type == "selector":
            for p in pivots:
                other = pivot.ensure_selector(conn, p.kind, p.value)
                if other == target.id:
                    continue
                if p.direction == "in":
                    pivot.add_pivot(conn, other, target.id, p.relation, module.name, run_id)
                else:
                    pivot.add_pivot(conn, target.id, other, p.relation, module.name, run_id)
    bump_data_version()


STALE_AFTER = timedelta(minutes=15)


def recover_stale() -> int:
    """Backend koşu ortasında kapandıysa RUNNING kalan kayıtlar FAILED'a çekilir — yoksa arayüz
    sonsuza dek "çalışıyor" gösterir ve aynı modül o hedefe bir daha başlatılamazdı."""
    conn = get_connection()
    rows = fetch_all(conn.execute("MATCH (r:EnrichmentRun) WHERE r.status = 'RUNNING' RETURN r.id AS id"))
    for row in rows:
        conn.execute(
            "MATCH (r:EnrichmentRun {id: $id}) SET r.status = 'FAILED', r.error = $e, r.finished_at = $now",
            {"id": row["id"], "e": "Backend koşu sürerken yeniden başladı; sonuç alınamadı.", "now": datetime.now(timezone.utc)},
        )
    return len(rows)


# --- Toplu koşu (arka plan) ----------------------------------------------------------------

_job_lock = threading.Lock()
_job: dict[str, Any] = {"running": False}


def bulk_status() -> dict:
    return dict(_job)


def start_bulk(name: str, kind: str, *, only_missing: bool = True, limit: int = 1000, scope: str = "corpus") -> dict:
    """Bir türün bütün seçicilerine aynı modülü uygular (ör. 386 CVE'nin hepsine KEV). Arka
    planda, tek iş parçacığında ve modülün kendi hız sınırıyla — aynı anda tek toplu iş.

    `scope="corpus"` (varsayılan): yalnızca toplanan metinde/belgede görülen, elle eklenen ya da
    bir entity'ye bağlanan seçiciler. Zenginleştirmenin kendisinin açtığı pivotlar (bir SPF
    kaydındaki `*.hubspotemail.net`, bir CDN adı) toplu işe girmez — ilk denemede DNS'in açtığı
    212 pivot alan adı RDAP kuyruğunu ikiye katlamıştı. `scope="all"` hepsini alır."""
    module = REGISTRY.get(name)
    if module is None:
        raise EnrichmentError(f"Bilinmeyen modül: {name}", 404)
    entity_bulk = module.target == "entity"
    if entity_bulk and kind != "entity":
        raise EnrichmentError(f"{module.label} kurum (entity) düzeyinde çalışır; tür olarak 'entity' ver.")
    if not entity_bulk and kind not in module.kinds:
        raise EnrichmentError(f"{module.label} {KIND_LABELS.get(kind, kind)} türünü zenginleştirmez.")
    if module.opsec == ACTIVE:
        raise EnrichmentError("Aktif modüller toplu çalıştırılamaz — her hedef için ayrı onay gerekir.", 409)
    if not is_enabled(module):
        raise EnrichmentError(f"{module.label} kapalı.", 409)
    if entity_bulk:
        # Kurum modülleri (OFAC taraması, Wikidata, GLEIF) bütün entity'lere: ad eşleşmesi aday
        # üretir, hiçbir şeyi bağlamaz — toplu çalışması kararı kullanıcıdan almaz.
        ids = [f"entity:{r['id']}" for r in fetch_all(get_connection().execute(
            "MATCH (e:Entity) RETURN e.id AS id ORDER BY e.name"
        ))]
    else:
        origin_clause = "" if scope == "all" else "AND (s.origin <> 'enrichment' OR EXISTS { MATCH (s)-[:SELECTOR_OF]->() }) "
        ids = [r["id"] for r in fetch_all(get_connection().execute(
            f"MATCH (s:Selector) WHERE s.kind = $k AND s.status <> 'IGNORED' {origin_clause}RETURN s.id AS id ORDER BY s.id",
            {"k": kind},
        ))]
    if only_missing:
        done = {r["t"] for r in fetch_all(get_connection().execute(
            "MATCH (r:EnrichmentRun) WHERE r.module = $m AND r.status = 'DONE' RETURN DISTINCT r.selector_id AS t", {"m": name}
        ))}
        ids = [i for i in ids if i not in done]
    ids = ids[:limit]
    with _job_lock:
        if _job.get("running"):
            raise EnrichmentError("Zaten bir toplu zenginleştirme çalışıyor.", 409)
        _job.clear()
        _job.update({"running": True, "module": name, "kind": kind, "total": len(ids), "done": 0, "failed": 0,
                     "started_at": datetime.now(timezone.utc).isoformat(), "finished_at": None, "last_error": None,
                     "cancel": False})

    def work() -> None:
        try:
            for target_id in ids:
                if _job.get("cancel"):
                    break
                try:
                    result = run(name, target_id)
                    if result["status"] != "DONE":
                        _job["failed"] += 1
                        _job["last_error"] = result.get("error")
                except Exception as exc:  # noqa: BLE001
                    _job["failed"] += 1
                    _job["last_error"] = str(exc)
                _job["done"] += 1
        finally:
            _job["running"] = False
            _job["finished_at"] = datetime.now(timezone.utc).isoformat()

    threading.Thread(target=work, name=f"enrich-bulk-{name}", daemon=True).start()
    return bulk_status()


def cancel_bulk() -> dict:
    _job["cancel"] = True
    return bulk_status()


def stats() -> dict:
    """Ölçüm turu için (scripts/olcum.py): modül başına koşu sayısı ve KEV kapsamı.
    KEV sayımı seçici başına SON başarılı koşuya bakar — geçmiş koşular sayımı şişirmesin."""
    conn = get_connection()
    per_module = fetch_all(conn.execute(
        "MATCH (r:EnrichmentRun) RETURN r.module AS module, r.status AS status, count(*) AS n ORDER BY module"
    ))
    latest_kev: dict[str, tuple] = {}
    for row in fetch_all(conn.execute(
        "MATCH (r:EnrichmentRun) WHERE r.module = 'kev' AND r.status = 'DONE' "
        "RETURN r.selector_id AS sid, r.finished_at AS at, r.summary AS summary"
    )):
        prev = latest_kev.get(row["sid"])
        if prev is None or row["at"] > prev[0]:
            latest_kev[row["sid"]] = (row["at"], row["summary"])
    exploited = sum(1 for _, s in latest_kev.values() if s and '"in_kev": true' in s)
    return {
        "runs": [{"module": r["module"], "status": r["status"], "count": r["n"]} for r in per_module],
        "kev": {"checked": len(latest_kev), "exploited": exploited},
        "pivots": fetch_one(conn.execute("MATCH ()-[p:PIVOT]->() RETURN count(p) AS n"))["n"],
    }


def exploited_cves(limit: int = 50) -> list[dict]:
    """Korpusta geçen ve KEV'e göre gerçekte sömürülen CVE'ler; bilinen fidye yazılımı kullanımı
    önce, sonra EPSS'e göre. Her seçici için SON başarılı KEV/EPSS koşusu esas alınır."""
    conn = get_connection()

    def latest(module: str) -> dict[str, dict]:
        out: dict[str, tuple] = {}
        for row in fetch_all(conn.execute(
            "MATCH (r:EnrichmentRun) WHERE r.module = $m AND r.status = 'DONE' "
            "RETURN r.selector_id AS sid, r.finished_at AS at, r.summary AS summary",
            {"m": module},
        )):
            prev = out.get(row["sid"])
            if prev is None or row["at"] > prev[0]:
                out[row["sid"]] = (row["at"], row["summary"])
        return {sid: json.loads(s) for sid, (_, s) in out.items() if s}

    kev = {sid: s for sid, s in latest("kev").items() if s.get("in_kev")}
    if not kev:
        return []
    epss = latest("epss")
    counts = {r["sid"]: r for r in fetch_all(conn.execute(
        "MATCH (s:Selector)-[:SEEN_IN]->(o:Observation) WHERE s.id IN $ids "
        "RETURN s.id AS sid, count(o) AS n, max(o.observed_at) AS last_seen",
        {"ids": list(kev)},
    ))}
    rows = []
    for sid, s in kev.items():
        e = epss.get(sid) or {}
        c = counts.get(sid) or {}
        rows.append({
            "id": sid,
            "cve": s.get("cve") or sid.split(":", 1)[1],
            "vendor": s.get("vendor"),
            "product": s.get("product"),
            "name": s.get("name"),
            "date_added": s.get("date_added"),
            "known_ransomware": s.get("known_ransomware") == "Known",
            "epss": e.get("epss"),
            "epss_percentile": e.get("percentile"),
            "sightings": c.get("n", 0),
            "last_seen": c.get("last_seen"),
        })
    rows.sort(key=lambda r: (not r["known_ransomware"], -(r["epss"] or 0), r["cve"]))
    return rows[:limit]
