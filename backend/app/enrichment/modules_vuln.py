"""Faz 30 — zafiyet ve teknik modülleri: CISA KEV, FIRST EPSS, NVD, MITRE ATT&CK.

Gerçek verideki en büyük seçici sınıfı CVE (386 farklı, çoğu CISA ICS advisory'lerinden). Bir
analistin bir CVE için sorduğu üç soru: "sömürülüyor mu" (KEV), "sömürülme olasılığı ne" (EPSS),
"ne kadar ciddi ve neyi etkiliyor" (NVD). ATT&CK tekniği için ise: "bu ne, hangi taktik, kimler
kullanıyor, nasıl önlenir".
"""
from __future__ import annotations

from app.enrichment import datasets
from app.enrichment.base import LOCAL, PASSIVE, Ctx, Module, ModuleError, Result, Target


def run_kev(ctx: Ctx, target: Target) -> Result:
    index, meta = datasets.load("kev", auto_refresh=True)
    item = index["items"].get(target.value)
    summary = {
        "cve": target.value,
        "in_kev": item is not None,
        "catalog_version": index.get("catalogVersion"),
        "catalog_released": index.get("dateReleased"),
    }
    if item:
        summary.update({
            "vendor": item.get("vendorProject"),
            "product": item.get("product"),
            "name": item.get("vulnerabilityName"),
            "date_added": item.get("dateAdded"),
            "due_date": item.get("dueDate"),
            "known_ransomware": item.get("knownRansomwareCampaignUse"),
            "required_action": item.get("requiredAction"),
            "short_description": item.get("shortDescription"),
            "cwes": item.get("cwes", []),
            "notes": item.get("notes"),
        })
    return Result(summary, raw_override={"dataset": "kev", "dataset_sha256": meta["sha256"],
                                         "dataset_downloaded_at": meta["downloaded_at"], "record": item})


def run_epss(ctx: Ctx, target: Target) -> Result:
    data = ctx.get_json("https://api.first.org/data/v1/epss", {"cve": target.value})
    rows = data.get("data", []) or []
    if not rows:
        return Result({"cve": target.value, "found": False})
    row = rows[0]
    return Result({
        "cve": target.value,
        "found": True,
        "epss": float(row.get("epss", 0)),
        "percentile": float(row.get("percentile", 0)),
        "date": row.get("date"),
    })


def run_nvd(ctx: Ctx, target: Target) -> Result:
    data = ctx.get_json("https://services.nvd.nist.gov/rest/json/cves/2.0", {"cveId": target.value})
    vulns = data.get("vulnerabilities", []) or []
    if not vulns:
        return Result({"cve": target.value, "found": False})
    cve = vulns[0].get("cve", {})
    description = next((d["value"] for d in cve.get("descriptions", []) if d.get("lang") == "en"), "")
    metrics = cve.get("metrics", {}) or {}
    cvss = []
    for key, version in (("cvssMetricV40", "4.0"), ("cvssMetricV31", "3.1"), ("cvssMetricV30", "3.0"), ("cvssMetricV2", "2.0")):
        for m in metrics.get(key, []) or []:
            d = m.get("cvssData", {})
            cvss.append({
                "version": version,
                "source": m.get("source"),
                "type": m.get("type"),
                "score": d.get("baseScore"),
                "severity": d.get("baseSeverity") or m.get("baseSeverity"),
                "vector": d.get("vectorString"),
            })
    cwes = sorted({d["value"] for w in cve.get("weaknesses", []) or [] for d in w.get("description", []) if d.get("value", "").startswith("CWE-")})
    cpes: list[str] = []
    for conf in cve.get("configurations", []) or []:
        for node in conf.get("nodes", []) or []:
            for match in node.get("cpeMatch", []) or []:
                parts = (match.get("criteria") or "").split(":")
                if len(parts) > 5:
                    label = f"{parts[3]} {parts[4]}"
                    if label not in cpes:
                        cpes.append(label)
    refs = [{"url": r.get("url"), "tags": r.get("tags", [])} for r in cve.get("references", []) or []]
    return Result({
        "cve": target.value,
        "found": True,
        "status": cve.get("vulnStatus"),
        "published": cve.get("published"),
        "last_modified": cve.get("lastModified"),
        "source": cve.get("sourceIdentifier"),
        "description": description.replace("&nbsp;", " ").strip()[:3000],
        "cvss": cvss,
        "cwes": cwes,
        "affected": cpes[:40],
        "references": refs[:40],
        "kev_in_nvd": bool(cve.get("cisaExploitAdd")),
    })


def run_attack(ctx: Ctx, target: Target) -> Result:
    index, meta = datasets.load("attack")
    technique = index["techniques"].get(target.value)
    if technique is None:
        raise ModuleError(f"{target.value} ATT&CK Enterprise veri setinde yok (iptal edilmiş ya da başka bir matriste olabilir).")
    parent = None
    if technique.get("is_subtechnique"):
        parent_id = target.value.split(".")[0]
        p = index["techniques"].get(parent_id)
        parent = {"id": parent_id, "name": p.get("name")} if p else None
    return Result({**technique, "parent": parent},
                  raw_override={"dataset": "attack", "dataset_sha256": meta["sha256"],
                                "dataset_downloaded_at": meta["downloaded_at"], "record": technique})


MODULES = [
    Module("kev", "CISA KEV", "CISA (yerel veri seti)",
           "Bu açık gerçekte sömürülüyor mu? Eklenme tarihi, son tarih, fidye yazılımı kullanımı, yapılması gereken.",
           "selector", ("cve",), LOCAL, frozenset(), run_kev, cache_hours=12, datasets=("kev",),
           docs_url="https://www.cisa.gov/known-exploited-vulnerabilities-catalog"),
    Module("epss", "EPSS", "FIRST",
           "Önümüzdeki 30 günde sömürülme olasılığı ve diğer CVE'ler arasındaki yüzdelik dilimi.",
           "selector", ("cve",), PASSIVE, frozenset({"api.first.org"}), run_epss, cache_hours=24,
           docs_url="https://www.first.org/epss/api"),
    Module("nvd", "NVD", "NIST",
           "Açıklama, CVSS puanları, CWE, etkilenen ürünler ve referanslar.",
           "selector", ("cve",), PASSIVE, frozenset({"services.nvd.nist.gov"}), run_nvd, cache_hours=72,
           docs_url="https://nvd.nist.gov/developers/vulnerabilities",
           terms_note="Anahtarsız sınır 30 sn'de 5 istek; istekler 6,5 sn aralıkla atılır."),
    Module("attack", "MITRE ATT&CK", "MITRE (yerel veri seti)",
           "Teknik adı, taktikler, platformlar, açıklama, tespit, onu kullanan gruplar/yazılımlar ve önlemler.",
           "selector", ("attack",), LOCAL, frozenset(), run_attack, cache_hours=24 * 30, datasets=("attack",),
           docs_url="https://attack.mitre.org/"),
]
