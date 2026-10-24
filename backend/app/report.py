"""Faz 35 — investigation raporu (Markdown ve yazdırılabilir HTML).

Bir araştırmanın son ürünü grafın kendisi değil, başkasının okuyup denetleyebileceği bir belge.
Rapor tamamen DETERMİNİSTİK üretilir — LLM yazmaz, özetlemez, yorum eklemez: araştırma sorusu,
kapsam, bulgular ve her bulgunun confidence dökümü, kaynağı, arşiv kopyasının hash'i, kanıt
dosyalarının hash'i, metinden çıkan seçiciler ve onların zenginleştirme sonuçları (KEV, EPSS,
RDAP...) ve kullanıcının kendi yazdığı analiz/sonuç. Her iddianın yanında "bunu ne kadar
biliyoruz" durur (Evidence First); kullanıcının yorumu ile kaynağın söylediği ayrı başlıklardadır
(Q15 provenance ayrımı).

**TLP (Traffic Light Protocol).** Profesyonel istihbarat paylaşımının standart dağıtım etiketi;
raporun başında ve sonunda yazılır. Seçim kullanıcınındır — sistem bir varsayılan dayatmaz,
yalnızca CLEAR'ı varsayar.

**Bütünlük.** Raporun gövdesinin SHA-256'sı alt bilgiye yazılır; rapor sonradan değiştirilirse
hash tutmaz. Kaynak metinler (claim metni, gözlem başlığı) güvenilmeyen veridir: HTML'de her alan
kaçırılır ve yanıt betik çalıştırmayı yasaklayan bir CSP ile döner.
"""
from __future__ import annotations

import hashlib
import html
import json
from datetime import datetime, timezone

from app import admiralty, pivot
from app.db import fetch_all, fetch_one, get_connection
from app.selectorindex import KIND_LABELS

TLP_LEVELS = {
    "CLEAR": "Sınırsız paylaşılabilir.",
    "GREEN": "Topluluk içinde paylaşılabilir, herkese açık kanallarda değil.",
    "AMBER": "Yalnızca kurum içinde ve bilmesi gerekenlerle.",
    "AMBER+STRICT": "Yalnızca alıcının kendi kurumu içinde.",
    "RED": "Yalnızca adı geçen alıcılar; başka kimseyle paylaşılmaz.",
}

STATE_LABELS = {
    "UNKNOWN": "Bilinmiyor", "OBSERVED": "Gözlendi", "REPORTED": "Bildirildi", "SUPPORTED": "Desteklendi",
    "CORROBORATED": "Doğrulandı", "HIGH_CONFIDENCE": "Yüksek güven", "CONTRADICTED": "Çelişkili",
}


def _enrichment_highlights(selector_id: str) -> list[str]:
    """Bir seçicinin en son başarılı koşularından rapora girecek kısa, olgusal satırlar."""
    rows = fetch_all(get_connection().execute(
        "MATCH (r:EnrichmentRun) WHERE r.selector_id = $id AND r.status = 'DONE' "
        "RETURN r.module AS module, r.summary AS summary, r.finished_at AS at, r.raw_sha256 AS sha "
        "ORDER BY r.finished_at DESC",
        {"id": selector_id},
    ))
    seen: set[str] = set()
    out: list[str] = []
    for row in rows:
        if row["module"] in seen or not row["summary"]:
            continue
        seen.add(row["module"])
        s = json.loads(row["summary"])
        stamp = row["at"].date().isoformat() if row["at"] else "?"
        line = None
        if row["module"] == "kev":
            line = (f"CISA KEV: {'SÖMÜRÜLÜYOR — ' + str(s.get('vendor')) + ' ' + str(s.get('product')) + ', eklenme ' + str(s.get('date_added')) if s.get('in_kev') else 'katalogda yok'}"
                    + (f", fidye yazılımı: {s.get('known_ransomware')}" if s.get("in_kev") else ""))
        elif row["module"] == "epss" and s.get("found"):
            line = f"EPSS: %{s['epss'] * 100:.1f} (yüzdelik %{s['percentile'] * 100:.1f}, {s.get('date')})"
        elif row["module"] == "nvd" and s.get("found"):
            top = next(iter(s.get("cvss") or []), None)
            line = f"NVD: {s.get('status')}" + (f", CVSS {top['version']} {top['score']} {top['severity']}" if top else "")
        elif row["module"] == "attack":
            line = f"ATT&CK: {s.get('name')} ({', '.join(s.get('tactics') or [])}); {len(s.get('groups') or [])} grup kullanıyor"
        elif row["module"] == "rdap":
            if s.get("registered") is False:
                line = "RDAP: şu an kayıtlı değil"
            else:
                ev = s.get("events") or {}
                line = f"RDAP: {s.get('registrar') or s.get('name')}, kayıt {str(ev.get('registration') or '?')[:10]}"
        elif row["module"] == "dns":
            recs = s.get("records") or {}
            line = "DNS: " + ("NXDOMAIN" if s.get("nxdomain") else ", ".join(f"{k} {len(v)}" for k, v in recs.items()) or "kayıt yok")
        elif row["module"] == "internetdb" and s.get("found"):
            line = f"Shodan InternetDB: portlar {s.get('ports')}, açıklar {len(s.get('vulns') or [])}"
        elif row["module"] == "ripestat-ip":
            asns = ", ".join(f"AS{a['asn']} {a['holder']}" for a in s.get("asns") or [])
            line = f"RIPEstat: {s.get('prefix')} {asns}"
        elif row["module"] == "crtsh":
            line = f"Sertifika şeffaflığı: {s.get('certificate_count')} sertifika, {s.get('subdomain_count')} alt alan adı"
        elif row["module"] in ("sanctions", "sanctions-crypto"):
            line = "OFAC SDN: " + ("LİSTEDE" if s.get("listed") else "listede yok")
        if line:
            out.append(f"{line} [{row['module']} · {stamp} · sha256 {str(row['sha'])[:12]}]")
    return out


def build(investigation_id: str) -> dict:
    # Geç import: routers.investigations → claims zinciri modül yüklenirken kurulmasın.
    from app.routers.claims import _gather_confidence_inputs
    from app.routers.investigations import get_workspace, list_findings

    ws = get_workspace(investigation_id)
    conn = get_connection()
    findings = {f["id"]: f for f in list_findings(investigation_id)}
    claims = []
    selector_ids: dict[str, dict] = {}
    for c in ws["claims"]:
        full = fetch_one(conn.execute(
            "MATCH (c:Claim {id: $id}) OPTIONAL MATCH (s:Source)-[:ASSERTS]->(c) "
            "OPTIONAL MATCH (ev:Evidence)-[:ARCHIVES]->(c) "
            "RETURN c.text AS text, s.name AS source, s.url AS source_url, s.reliability AS reliability, "
            "ev.content_hash AS archive_hash, ev.archive_url AS archive_url, ev.archive_status AS archive_status",
            {"id": c["id"]},
        )) or {}
        conf = _gather_confidence_inputs(conn, c["id"])
        sels = pivot.claim_selectors(c["id"])
        for s in sels:
            selector_ids.setdefault(s["id"], s)
        claims.append({
            **c,
            "text": full.get("text"),
            "source": full.get("source"),
            "source_url": full.get("source_url"),
            "reliability": full.get("reliability"),
            "archive_hash": full.get("archive_hash"),
            "archive_url": full.get("archive_url"),
            "archive_status": full.get("archive_status"),
            "validated": findings.get(c["id"], {}).get("validated", False),
            "breakdown": {
                "source_quality": conf.source_quality, "independence": conf.independence,
                "evidence": conf.evidence, "corroboration": conf.corroboration,
            },
            "selectors": [s["id"] for s in sels],
            "admiralty": admiralty.code(full.get("reliability"), c.get("knowledge_state")),
        })
    selectors = [
        {**s, "label": KIND_LABELS.get(s["kind"], s["kind"]), "highlights": _enrichment_highlights(s["id"])}
        for s in sorted(selector_ids.values(), key=lambda s: (s["kind"], s["value"]))
    ]
    return {
        **ws,
        "claims": claims,
        "selectors": selectors,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _pct(x) -> str:
    return f"%{round((x or 0) * 100)}"


def to_markdown(r: dict, tlp: str = "CLEAR") -> str:
    inv = r["investigation"]
    lines = [
        f"**TLP:{tlp}** — {TLP_LEVELS[tlp]}",
        "",
        f"# {inv['title']}",
        "",
        f"- Durum: {inv['status']}",
        f"- Açılış: {inv['created_at'][:10]}" + (f" · Sonuç: {inv['concluded_at'][:10]}" if inv.get("concluded_at") else ""),
        f"- Rapor: {r['generated_at']} (OsintLab · {len(r['claims'])} claim, {len(r['selectors'])} seçici, {len(r['evidence'])} kanıt)",
        "",
        "## Araştırma sorusu",
        "",
        inv.get("research_question") or "_(yazılmamış)_",
        "",
        "## Kapsam",
        "",
    ]
    ents = r["scope"].get("entities", [])
    evs = r["scope"].get("events", [])
    lines += [f"- Entity: {e['name']} ({e.get('entity_type', '')})" for e in ents]
    lines += [f"- Olay: {e['title']}" for e in evs]
    if not ents and not evs:
        lines.append("_(kapsam tanımlanmamış)_")

    findings = [c for c in r["claims"] if c["is_finding"]]
    others = [c for c in r["claims"] if not c["is_finding"]]

    def claim_block(i: int, c: dict) -> list[str]:
        b = c["breakdown"]
        out = [
            f"### {i}. {c['headline']}",
            "",
            f"> {(c.get('text') or '').strip().replace(chr(10), ' ')}",
            "",
            f"- **Durum:** {STATE_LABELS.get(c['knowledge_state'], c['knowledge_state'])} ({_pct(c['confidence'])})"
            + (" · kapanışta doğrulanmış bulgu" if c.get("validated") else "")
            + (" · **yerini daha yeni bir claim aldı**" if c.get("superseded") else ""),
            f"- **Confidence dökümü:** kaynak kalitesi {_pct(b['source_quality'])}, bağımsızlık {_pct(b['independence'])}, "
            f"kanıt {_pct(b['evidence'])}, doğrulama {_pct(b['corroboration'])}",
            f"- **Kaynak:** {c.get('source') or '?'}" + (f" ({c['source_url']})" if c.get("source_url") else ""),
            f"- **NATO/Admiralty:** {c['admiralty']['code']} ({c['admiralty']['source_label']} kaynak · "
            f"{c['admiralty']['info_label'].lower()} bilgi)",
        ]
        if c.get("archive_hash"):
            out.append(f"- **Arşiv:** {c.get('archive_status')} · sha256 `{c['archive_hash']}`" + (f" · {c['archive_url']}" if c.get("archive_url") else ""))
        if c["selectors"]:
            out.append("- **Seçiciler:** " + ", ".join(f"`{s.split(':', 1)[1]}`" for s in c["selectors"]))
        out.append("")
        return out

    lines += ["", "## Bulgular", ""]
    if findings:
        for i, c in enumerate(findings, 1):
            lines += claim_block(i, c)
    else:
        lines += ["_(bulgu ilan edilmemiş)_", ""]

    if r["hypotheses"]:
        lines += ["## Hipotezler", ""]
        lines += [f"- [{h['status']}] {h['text']}" for h in r["hypotheses"]]
        lines.append("")

    lines += ["## Analiz (araştırmacının yorumu)", "", inv.get("analysis") or "_(yazılmamış)_", "",
              "## Sonuç (araştırmacının yorumu)", "", inv.get("conclusion") or "_(yazılmamış)_", ""]

    if others:
        lines += ["## Kapsamdaki diğer claim'ler", ""]
        for i, c in enumerate(others, 1):
            lines += claim_block(i, c)

    if r["selectors"]:
        lines += ["## Teknik göstergeler (seçiciler)", "", "| Tür | Değer | Zenginleştirme |", "| --- | --- | --- |"]
        for s in r["selectors"]:
            hl = "<br>".join(s["highlights"]) or "—"
            lines.append(f"| {s['label']} | `{s['value']}` | {hl} |")
        lines.append("")

    if r["evidence"]:
        lines += ["## Kanıt dosyaları", "", "| Tür | Dosya | Duruş | SHA-256 |", "| --- | --- | --- | --- |"]
        for e in r["evidence"]:
            name = (e.get("file_path") or "").replace("\\", "/").split("/")[-1]
            digest = f"`{e['content_hash']}`" if e.get("content_hash") else "— (dosyasız kayıt)"
            lines.append(f"| {e.get('evidence_type')} | {name} | {e['stance']} | {digest} |")
        lines.append("")

    if r["sources"]:
        lines += ["## Kaynaklar", ""]
        lines += [f"- {s['name']} ({s.get('source_type')}) — güvenilirlik {_pct(s.get('reliability'))}" for s in r["sources"]]
        lines.append("")

    lines += [
        "## Yöntem",
        "",
        "Confidence deterministik bir formülle hesaplanır (kaynak kalitesi %40, bağımsızlık %25, kanıt %20, doğrulama %15); "
        "türetilmiş kaynaklar bağımsız sayılmaz. Zenginleştirme sonuçları herkese açık kaynaklardan alınmıştır ve her birinin "
        "ham yanıtı OsintLab'de SHA-256 ile saklanır. Claim metinleri kaynaklardan aynen alınmıştır; yorum yalnızca "
        "'Analiz' ve 'Sonuç' bölümlerindedir.",
        "",
    ]
    body = "\n".join(lines)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"{body}\n---\n**TLP:{tlp}** · gövde sha256 `{digest}`\n"


_CSS = """
body{font:15px/1.6 system-ui,-apple-system,"Segoe UI",Inter,sans-serif;color:#18181b;max-width:860px;margin:2rem auto;padding:0 1.25rem}
h1{font-size:1.8rem;margin:.4rem 0 1rem}h2{font-size:1.15rem;margin-top:2rem;border-bottom:1px solid #e4e4e7;padding-bottom:.25rem}
h3{font-size:1rem;margin:1.25rem 0 .25rem}blockquote{margin:.5rem 0;padding:.5rem .75rem;border-left:3px solid #a1a1aa;background:#f4f4f5;color:#3f3f46}
code{font:12px ui-monospace,"JetBrains Mono",monospace;background:#f4f4f5;padding:.1rem .25rem;border-radius:3px;word-break:break-all}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #e4e4e7;padding:.35rem .5rem;text-align:left;vertical-align:top}
.tlp{display:inline-block;font:600 12px ui-monospace,monospace;padding:.2rem .5rem;border-radius:3px;background:#000;letter-spacing:.04em}
.tlp-CLEAR{color:#fff}.tlp-GREEN{color:#33ff00}.tlp-AMBER,.tlp-AMBER\\+STRICT{color:#ffc000}.tlp-RED{color:#ff2b2b}
.meta{color:#52525b;font-size:13px}.foot{margin-top:2.5rem;font-size:12px;color:#71717a;border-top:1px solid #e4e4e7;padding-top:.5rem}
@media print{body{margin:0}a{color:inherit}}
"""


def _md_inline(text: str) -> str:
    """Kaçırılmış metinde yalnızca **kalın** ve `kod` biçimini uygular — başka hiçbir şey."""
    import re

    text = html.escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text.replace("&lt;br&gt;", "<br>")


def to_html(r: dict, tlp: str = "CLEAR") -> str:
    """Markdown'dan HTML'e küçük, kapalı bir dönüştürücü: başlık, alıntı, liste, tablo, paragraf.
    Bağımlılık eklenmedi; girdi bizim ürettiğimiz sabit biçimli Markdown."""
    md = to_markdown(r, tlp)
    out: list[str] = []
    in_list = in_table = False
    for raw in md.split("\n"):
        line = raw.rstrip()
        if in_list and not line.startswith("- "):
            out.append("</ul>")
            in_list = False
        if in_table and not line.startswith("|"):
            out.append("</table>")
            in_table = False
        if not line:
            continue
        if line.startswith("**TLP:"):
            out.append(f'<p><span class="tlp tlp-{html.escape(tlp)}">TLP:{html.escape(tlp)}</span> '
                       f'<span class="meta">{html.escape(TLP_LEVELS[tlp])}</span></p>')
        elif line.startswith("### "):
            out.append(f"<h3>{_md_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{_md_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{_md_inline(line[2:])}</h1>")
        elif line.startswith("> "):
            out.append(f"<blockquote>{html.escape(line[2:])}</blockquote>")
        elif line.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_md_inline(line[2:])}</li>")
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= {"-", " "} for c in cells):
                continue
            if not in_table:
                out.append("<table>")
                in_table = True
                out.append("<tr>" + "".join(f"<th>{_md_inline(c)}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{_md_inline(c)}</td>" for c in cells) + "</tr>")
        elif line == "---":
            out.append('<div class="foot">')
        elif line.startswith("_(") and line.endswith(")_"):
            out.append(f'<p class="meta">{html.escape(line[2:-2])}</p>')
        else:
            out.append(f"<p>{_md_inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    if in_table:
        out.append("</table>")
    out.append("</div>")
    title = html.escape(r["investigation"]["title"])
    return (
        f'<!doctype html><html lang="tr"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title} — OsintLab raporu</title>'
        f"<style>{_CSS}</style></head><body>{''.join(out)}</body></html>"
    )
