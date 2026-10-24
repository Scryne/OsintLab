"""Investigation durum makinesi: kapanmış defter ve bulguların yükselmesi."""


def _walk(client, inv_id, *statuses):
    for status in statuses:
        r = client.post(f"/investigations/{inv_id}/transition", json={"to_status": status})
        assert r.status_code == 200, r.text


def _supported_claim(client, make_source, make_claim):
    a, b = make_source(reliability=1.0), make_source(reliability=1.0)
    first = make_claim(a["id"])
    make_claim(b["id"], corroborates=[first["id"]])
    claim = client.get(f"/claims/{first['id']}").json()
    assert claim["knowledge_state"] in ("SUPPORTED", "CORROBORATED", "HIGH_CONFIDENCE")
    return claim


def test_archive_does_not_promote_findings(client, make_investigation, make_source, make_claim):
    inv = make_investigation()
    claim = _supported_claim(client, make_source, make_claim)
    assert client.put(f"/investigations/{inv['id']}/findings/{claim['id']}").status_code == 204
    _walk(client, inv["id"], "ARCHIVED")
    findings = client.get(f"/investigations/{inv['id']}/findings").json()
    assert findings and not any(f["validated"] for f in findings)


def test_close_promotes_verified_findings(client, make_investigation, make_source, make_claim):
    inv = make_investigation()
    claim = _supported_claim(client, make_source, make_claim)
    client.put(f"/investigations/{inv['id']}/findings/{claim['id']}")
    _walk(client, inv["id"], "ACTIVE", "RESOLVED")
    client.patch(f"/investigations/{inv['id']}/narrative", json={"conclusion": "Doğrulandı."})
    _walk(client, inv["id"], "CLOSED")
    assert all(f["validated"] for f in client.get(f"/investigations/{inv['id']}/findings").json())


def test_closed_investigation_is_read_only(client, make_investigation, make_entity):
    inv = make_investigation()
    _walk(client, inv["id"], "ACTIVE", "RESOLVED")
    client.patch(f"/investigations/{inv['id']}/narrative", json={"conclusion": "Sonuç"})
    _walk(client, inv["id"], "CLOSED")
    assert client.patch(f"/investigations/{inv['id']}/narrative", json={"conclusion": ""}).status_code == 409
    assert client.put(f"/investigations/{inv['id']}/entities/{make_entity()['id']}").status_code == 409
    assert client.post(f"/investigations/{inv['id']}/hypotheses", json={"text": "H"}).status_code == 409


def test_hypothesis_evidence_stance_is_replaced_not_stacked(client, make_investigation):
    inv = make_investigation()
    hyp = client.post(f"/investigations/{inv['id']}/hypotheses", json={"text": "H1"}).json()
    ev = client.post("/evidence", json={"evidence_type": "belge"}).json()
    url = f"/hypotheses/{hyp['id']}/evidence"
    assert client.put(url, json={"evidence_id": ev["id"], "stance": "SUPPORTS"}).json()["status"] == "SUPPORTED"
    # Aynı kanıtı ikinci kez bağlamak çift destek sayılmamalı; duruş değişince yer değiştirmeli.
    client.put(url, json={"evidence_id": ev["id"], "stance": "SUPPORTS"})
    assert len(client.get(url).json()) == 1
    assert client.put(url, json={"evidence_id": ev["id"], "stance": "WEAKENS"}).json()["status"] == "WEAKENED"
    assert client.delete(f"{url}/{ev['id']}").json()["status"] == "PROPOSED"


def test_report_markdown_and_html_are_deterministic_and_safe(client, make_investigation, make_source, make_claim):
    inv = make_investigation(title="Rapor <script>alert(1)</script>")
    src = make_source()
    claim = make_claim(src["id"], text="Vendor confirmed CVE-2031-44444 exploitation <img src=x onerror=alert(1)>")
    client.put(f"/investigations/{inv['id']}/findings/{claim['id']}")
    md = client.get(f"/investigations/{inv['id']}/report", params={"tlp": "amber"}).text
    assert md.startswith("**TLP:AMBER**")
    assert "## Bulgular" in md and "CVE-2031-44444" in md
    assert "gövde sha256" in md
    r = client.get(f"/investigations/{inv['id']}/report", params={"format": "html"})
    assert "script-src" not in r.headers["content-security-policy"] and "default-src 'none'" in r.headers["content-security-policy"]
    assert "<script>" not in r.text and "&lt;script&gt;" in r.text
    assert "<img" not in r.text
    assert client.get(f"/investigations/{inv['id']}/report", params={"tlp": "purple"}).status_code == 422
