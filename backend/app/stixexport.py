"""v6 — seçicilerin dışa aktarımı: CSV ve STIX 2.1 paketi.

Tehdit istihbaratı paylaşımının ortak dili STIX 2.1: SOC/TIP araçları (MISP, OpenCTI, SIEM'ler)
bir göstergeyi `indicator` nesnesi ve STIX desen diliyle (`[domain-name:value = 'x']`) alır. CVE
bir `vulnerability`, ATT&CK tekniği bir `attack-pattern` olarak gider.

Nesne kimlikleri `uuid5` ile seçici kimliğinden türetilir: aynı seçici her dışa aktarımda aynı
STIX kimliğini taşır, alıcı taraf tekrar içe aktarınca kopya üretmez. Paket deterministik değil
yalnızca `created` zamanında.

Kişi seçicisi zaten yok; e-posta ve koordinat dışa aktarılmaz (gösterge değil, bağlam).
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone

NAMESPACE = uuid.UUID("6f0c1c1e-7f0a-4b8e-9a51-0e5f1b7c2d10")  # OsintLab'e özgü, sabit

_PATTERNS = {
    "domain": "[domain-name:value = '{v}']",
    "ip": "[ipv4-addr:value = '{v}']",
    "url": "[url:value = '{v}']",
    "md5": "[file:hashes.MD5 = '{v}']",
    "sha1": "[file:hashes.'SHA-1' = '{v}']",
    "sha256": "[file:hashes.'SHA-256' = '{v}']",
    "btc": "[cryptocurrency-wallet:address = '{v}']",
    "eth": "[cryptocurrency-wallet:address = '{v}']",
    "asn": "[autonomous-system:number = {n}]",
}


def _stix_id(kind: str, selector_id: str) -> str:
    return f"{kind}--{uuid.uuid5(NAMESPACE, selector_id)}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _ts(value) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def stix_bundle(selectors: list[dict], *, flags: dict[str, list[str]] | None = None) -> dict:
    now = _ts(None)
    identity = {
        "type": "identity", "spec_version": "2.1", "id": _stix_id("identity", "osintlab"),
        "created": now, "modified": now, "name": "OsintLab", "identity_class": "system",
    }
    objects: list[dict] = [identity]
    for s in selectors:
        kind, value = s["kind"], s["value"]
        created = _ts(s.get("created_at"))
        labels = [f"osintlab-origin:{s.get('origin')}"] + [f"osintlab:{f.lower()}" for f in (flags or {}).get(s["id"], [])]
        base = {"spec_version": "2.1", "created": created, "modified": created, "created_by_ref": identity["id"]}
        if kind == "cve":
            objects.append({**base, "type": "vulnerability", "id": _stix_id("vulnerability", s["id"]), "name": value,
                            "labels": labels,
                            "external_references": [{"source_name": "cve", "external_id": value}]})
        elif kind == "attack":
            objects.append({**base, "type": "attack-pattern", "id": _stix_id("attack-pattern", s["id"]), "name": value,
                            "external_references": [{"source_name": "mitre-attack", "external_id": value,
                                                     "url": f"https://attack.mitre.org/techniques/{value.replace('.', '/')}/"}]})
        elif kind in _PATTERNS:
            if kind == "ip" and ":" in value:
                pattern = f"[ipv6-addr:value = '{_escape(value)}']"
            elif kind == "asn":
                pattern = _PATTERNS[kind].format(n=int(value[2:]))
            else:
                pattern = _PATTERNS[kind].format(v=_escape(value))
            objects.append({**base, "type": "indicator", "id": _stix_id("indicator", s["id"]),
                            "name": f"{kind}: {value}", "pattern": pattern, "pattern_type": "stix",
                            "valid_from": created, "labels": labels,
                            **({"description": s["note"]} if s.get("note") else {})})
    return {"type": "bundle", "id": f"bundle--{uuid.uuid4()}", "objects": objects}


def to_csv(selectors: list[dict], *, flags: dict[str, list[str]] | None = None) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["kind", "value", "origin", "status", "observations", "first_seen", "last_seen", "flags", "note"])
    for s in selectors:
        writer.writerow([
            s["kind"], s["value"], s.get("origin"), s.get("status"), s.get("observation_count", 0),
            _ts(s["first_seen"]) if s.get("first_seen") else "", _ts(s["last_seen"]) if s.get("last_seen") else "",
            "|".join((flags or {}).get(s["id"], [])), (s.get("note") or "").replace("\n", " "),
        ])
    return buf.getvalue()


def dumps(bundle: dict) -> str:
    return json.dumps(bundle, ensure_ascii=False, indent=1)
