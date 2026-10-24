"""Faz 30 — yerel veri setleri: CISA KEV, MITRE ATT&CK, OFAC SDN.

Bu kaynaklara kayıt başına sormak yerine dosyanın tamamı indirilip yerelde aranıyor. İki sebep:

1. **OPSEC.** "CVE-2026-20079 KEV'de mi" sorusunu her seferinde CISA'ya sormak, hangi açıklarla
   ilgilendiğini sızdırır; kataloğu bir kez indirmek hiçbir şey söylemez.
2. **Hız ve kota.** 386 CVE'nin KEV durumu yerelde milisaniyede, ATT&CK'nın 55 MB'lık STIX
   paketi ise ancak bir kez indirilmeye değer.

Her veri seti indirildiğinde ham baytların SHA-256'sı ve indirme zamanı `meta.json`a yazılır:
bir zenginleştirme sonucu "KEV'de yok" dediğinde, hangi tarihli katalogla bakıldığı belli olmalı.
Ham büyük dosyalar saklanmaz, yalnızca türetilmiş küçük indeks (`index.json`) — indeks her an
aynı dosyadan yeniden üretilebilir, hash bunun kanıtı.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app.collector import safe_fetch
from app.db import DATA_ROOT, atomic_write_text

logger = logging.getLogger(__name__)

DATASET_ROOT = DATA_ROOT / "datasets"


def _kev_index(blobs: dict[str, bytes]) -> tuple[dict, int]:
    catalog = json.loads(blobs["kev"].decode("utf-8"))
    index = {item["cveID"]: item for item in catalog.get("vulnerabilities", [])}
    return {"catalogVersion": catalog.get("catalogVersion"), "dateReleased": catalog.get("dateReleased"),
            "items": index}, len(index)


def _attack_index(blobs: dict[str, bytes]) -> tuple[dict, int]:
    bundle = json.loads(blobs["attack"].decode("utf-8"))
    objects = bundle.get("objects", [])
    by_id: dict[str, dict] = {}
    techniques: dict[str, dict] = {}

    def ext_id(obj: dict) -> tuple[str | None, str | None]:
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                return ref.get("external_id"), ref.get("url")
        return None, None

    for obj in objects:
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        by_id[obj["id"]] = obj
        if obj.get("type") == "attack-pattern":
            tid, url = ext_id(obj)
            if not tid:
                continue
            techniques[tid] = {
                "id": tid,
                "name": obj.get("name"),
                "url": url,
                "tactics": [p["phase_name"] for p in obj.get("kill_chain_phases", []) if p.get("kill_chain_name") == "mitre-attack"],
                "platforms": obj.get("x_mitre_platforms", []),
                "is_subtechnique": bool(obj.get("x_mitre_is_subtechnique")),
                "description": (obj.get("description") or "")[:1500],
                "detection": (obj.get("x_mitre_detection") or "")[:800],
                "groups": [],
                "software": [],
                "mitigations": [],
                "_stix": obj["id"],
            }
    stix_to_tid = {t["_stix"]: tid for tid, t in techniques.items()}
    for obj in objects:
        if obj.get("type") != "relationship" or obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        target = stix_to_tid.get(obj.get("target_ref", ""))
        source = by_id.get(obj.get("source_ref", ""))
        if not target or not source:
            continue
        sid, _ = ext_id(source)
        entry = {"id": sid, "name": source.get("name")}
        rel = obj.get("relationship_type")
        if rel == "uses" and source.get("type") == "intrusion-set":
            techniques[target]["groups"].append(entry)
        elif rel == "uses" and source.get("type") in ("malware", "tool"):
            techniques[target]["software"].append(entry)
        elif rel == "mitigates" and source.get("type") == "course-of-action":
            techniques[target]["mitigations"].append(entry)
    for t in techniques.values():
        t.pop("_stix", None)
        for key in ("groups", "software", "mitigations"):
            t[key] = sorted({(e["id"] or "", e["name"]) for e in t[key]}, key=lambda x: x[1] or "")
            t[key] = [{"id": i, "name": n} for i, n in t[key]]
    return {"techniques": techniques}, len(techniques)


_LEGAL_SUFFIXES = {
    "ltd", "llc", "inc", "co", "corp", "corporation", "company", "limited", "plc", "gmbh", "ag", "sa", "jsc",
    "ojsc", "pjsc", "ooo", "oao", "zao", "llp", "lp", "bv", "nv", "srl", "spa", "as", "ab", "oy", "kft", "the",
}


def normalize_name(value: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", value.lower().replace("&", " and "))
    return [t for t in tokens if t not in _LEGAL_SUFFIXES]


_CRYPTO_RE = re.compile(r"Digital Currency Address - (\w+) ([A-Za-z0-9]+)")


def _ofac_index(blobs: dict[str, bytes]) -> tuple[dict, int]:
    def rows(name: str):
        text = blobs[name].decode("latin-1")
        return csv.reader(io.StringIO(text))

    def clean(value: str) -> str:
        value = (value or "").strip()
        return "" if value == "-0-" else value

    entries: dict[str, dict] = {}
    names: list[list[Any]] = []
    crypto: dict[str, dict] = {}
    for row in rows("sdn"):
        if len(row) < 12 or not row[0].strip().isdigit():
            continue
        ent = row[0].strip()
        remarks = clean(row[11])
        entries[ent] = {
            "ent_num": ent,
            "name": clean(row[1]),
            "type": clean(row[2]) or "entity",
            "programs": clean(row[3]),
            "remarks": remarks[:600],
        }
        names.append([" ".join(normalize_name(clean(row[1]))), ent, clean(row[1])])
        for currency, address in _CRYPTO_RE.findall(remarks):
            crypto[address.lower() if address.lower().startswith(("0x", "bc1")) else address] = {"ent_num": ent, "currency": currency}
    for row in rows("alt"):
        if len(row) < 4 or not row[0].strip().isdigit():
            continue
        alt = clean(row[3])
        if alt:
            names.append([" ".join(normalize_name(alt)), row[0].strip(), alt])
    return {"entries": entries, "names": names, "crypto": crypto}, len(entries)


DATASETS: dict[str, dict[str, Any]] = {
    "kev": {
        "label": "CISA Known Exploited Vulnerabilities",
        "provider": "CISA",
        "files": {"kev": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"},
        "hosts": {"www.cisa.gov"},
        "refresh_hours": 24,
        "max_bytes": 20_000_000,
        "build": _kev_index,
        "license": "Kamu malı (ABD hükümeti eseri).",
    },
    "attack": {
        "label": "MITRE ATT&CK Enterprise",
        "provider": "MITRE",
        "files": {"attack": "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/enterprise-attack/enterprise-attack.json"},
        "hosts": {"raw.githubusercontent.com"},
        "refresh_hours": 24 * 30,
        "max_bytes": 120_000_000,
        "build": _attack_index,
        "license": "ATT&CK® MITRE kullanım koşulları — atıfla serbest kullanım.",
    },
    "ofac": {
        "label": "OFAC SDN (ABD yaptırım listesi)",
        "provider": "U.S. Treasury OFAC",
        "files": {
            "sdn": "https://www.treasury.gov/ofac/downloads/sdn.csv",
            "alt": "https://www.treasury.gov/ofac/downloads/alt.csv",
        },
        "hosts": {"www.treasury.gov", "sanctionslistservice.ofac.treas.gov", "sanctionslist.ofac.treas.gov",
                  # OFAC dosyaları bir GovCloud S3 kovasına yönlendiriyor (2026-10-24).
                  "wc2h-sls-prod-public-published.s3.us-gov-west-1.amazonaws.com"},
        "refresh_hours": 24,
        "max_bytes": 60_000_000,
        "build": _ofac_index,
        "license": "Kamu malı (ABD hükümeti eseri).",
    },
}

_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()
_download_locks = {name: threading.Lock() for name in DATASETS}


def _dir(name: str) -> Path:
    return DATASET_ROOT / name


def meta(name: str) -> dict | None:
    path = _dir(name) / "meta.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def status() -> list[dict]:
    out = []
    now = datetime.now(timezone.utc)
    for name, spec in DATASETS.items():
        m = meta(name)
        stale = True
        if m:
            fetched = datetime.fromisoformat(m["downloaded_at"])
            stale = now - fetched > timedelta(hours=spec["refresh_hours"])
        out.append({
            "name": name,
            "label": spec["label"],
            "provider": spec["provider"],
            "license": spec["license"],
            "sources": list(spec["files"].values()),
            "refresh_hours": spec["refresh_hours"],
            "downloaded": m is not None,
            "stale": stale,
            **({k: m[k] for k in ("downloaded_at", "records", "bytes", "sha256")} if m else {}),
        })
    return out


def download(name: str) -> dict:
    """Veri setini indirip indeksini kurar. Aynı anda iki indirme başlamaz."""
    spec = DATASETS[name]
    lock = _download_locks[name]
    if not lock.acquire(blocking=False):
        raise RuntimeError(f"{spec['label']} zaten indiriliyor.")
    try:
        blobs: dict[str, bytes] = {}
        hashes: dict[str, str] = {}
        for key, url in spec["files"].items():
            _, content, _ = safe_fetch(url, set(spec["hosts"]), max_bytes=spec["max_bytes"], max_seconds=300)
            blobs[key] = content
            hashes[key] = hashlib.sha256(content).hexdigest()
        build: Callable = spec["build"]
        index, records = build(blobs)
        target = _dir(name)
        target.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target / "index.json", json.dumps(index, ensure_ascii=False))
        info = {
            "name": name,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "records": records,
            "bytes": sum(len(b) for b in blobs.values()),
            "sha256": hashes if len(hashes) > 1 else next(iter(hashes.values())),
            "sources": spec["files"],
        }
        atomic_write_text(target / "meta.json", json.dumps(info, ensure_ascii=False, indent=2))
        with _lock:
            _cache.pop(name, None)
        logger.info("Veri seti %s indirildi: %s kayıt", name, records)
        return info
    finally:
        lock.release()


def load(name: str, *, auto_refresh: bool = False) -> tuple[dict, dict]:
    """(indeks, meta). Hiç indirilmemişse ya da `auto_refresh` açık ve eskimişse indirir."""
    m = meta(name)
    spec = DATASETS[name]
    needs = m is None
    if m is not None and auto_refresh:
        needs = datetime.now(timezone.utc) - datetime.fromisoformat(m["downloaded_at"]) > timedelta(hours=spec["refresh_hours"])
    if needs:
        try:
            m = download(name)
        except Exception:
            if m is None:
                raise
            logger.exception("%s yenilenemedi, eski kopya kullanılıyor", name)
    path = _dir(name) / "index.json"
    mtime = path.stat().st_mtime
    with _lock:
        cached = _cache.get(name)
        if cached and cached[0] == mtime:
            return cached[1], m
        index = json.loads(path.read_text(encoding="utf-8"))
        _cache[name] = (mtime, index)
    return index, m
