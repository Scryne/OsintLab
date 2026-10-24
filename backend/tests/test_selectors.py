"""Faz 29 — seçici katmanı: deterministik çıkarma kuralları ve graf indeksi."""
from urllib.parse import quote

from app.selectorindex import detect, extract_unique


def _kinds(text: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for s in extract_unique(text):
        out.setdefault(s.kind, set()).add(s.value)
    return out


# ---- Çıkarma: gerçek veriden gelen yanlış pozitifler --------------------------

def test_version_numbers_are_not_ips():
    # Gerçek CISA advisory'lerinden (2026-10-24 ölçümü, 17/17 sürüm numarasıydı).
    texts = [
        "EseeCloud Firmware: <=4.9.86.0",
        "Lion Controls 700 Series: <=Bootloader_2.0.6.1",
        "affecting Ivanti Connect Secure versions 25.1.1.1 and prior, 25.1.2.2 and prior",
        "Ability Edgenius >=3.2.0.0|<3.2.4.1, 3.2.4.1 (CVE-2026-31431)",
        "Anjvision firmware: 3.3.2.4_build_202",
        "release version 2.6.0.7R6 which",
        "log4net library is upgraded to version 3.3.1.0, and",
    ]
    for text in texts:
        assert "ip" not in _kinds(text), text


def test_defanged_indicators_are_extracted():
    found = _kinds("C2 at 149.28.132[.]137 and hxxps://upl.natcloudservice[.]com/x plus twimg.co[.]uk")
    assert found["ip"] == {"149.28.132.137"}
    assert "https://upl.natcloudservice.com/x" in found["url"]
    assert {"natcloudservice.com", "twimg.co.uk"} <= found["domain"] | {"natcloudservice.com"}
    assert "twimg.co.uk" in found["domain"]
    assert "twimg.co" not in found["domain"]


def test_plain_public_ip_outside_version_context_is_kept():
    assert _kinds("The actor connected from 8.8.8.8 repeatedly")["ip"] == {"8.8.8.8"}
    assert "ip" not in _kinds("internal host 192.168.1.10")


def test_file_names_are_not_domains():
    found = _kinds("Install Node.js and edit config.yaml then read README.md and run setup.py")
    assert "domain" not in found


def test_real_domains_and_emails():
    found = _kinds("Contact security@tyconsystems.com. or see www.cisa.gov for details; Hunt.io found it")
    assert found["email"] == {"security@tyconsystems.com"}
    assert {"tyconsystems.com", "www.cisa.gov", "hunt.io"} <= found["domain"]


def test_ids_and_hashes():
    found = _kinds(
        "CVE-2024-3400 exploited (T1190, T1059.004) from hosting network AS13335; sample "
        "BBDD3620A67AEDEC4B9A68B2C9CC880B6631215E129816AEA19902A6F4BC6F41 and d41d8cd98f00b204e9800998ecf8427e"
    )
    assert found["cve"] == {"CVE-2024-3400"}
    assert found["attack"] == {"T1190", "T1059.004"}
    assert found["asn"] == {"AS13335"}
    assert found["sha256"] == {"bbdd3620a67aedec4b9a68b2c9cc880b6631215e129816aea19902a6f4bc6f41"}
    assert found["md5"] == {"d41d8cd98f00b204e9800998ecf8427e"}


def test_crypto_addresses_require_valid_checksum():
    good = _kinds("pay 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa or bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq")
    assert good["btc"] == {"1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"}
    # Bir karakter değişince sağlama toplamı tutmaz.
    assert "btc" not in _kinds("pay 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb")


def test_detect_single_values():
    assert detect("hxxps://evil[.]com/a)") == ("url", "https://evil.com/a")
    assert detect("t1059.001") == ("attack", "T1059.001")
    assert detect("as 13335") == ("asn", "AS13335")
    assert detect("41.0082, 28.9784") == ("coord", "41.008200,28.978400")
    assert detect("user[@]example[.]org") == ("email", "user@example.org")
    assert detect("not a selector") is None


# ---- Graf indeksi ----------------------------------------------------------------

def test_new_observation_is_indexed_and_detail_shows_context(client):
    r = client.post("/observations", json={
        "raw_content": "Advisory: CVE-2031-11111 exploited from 45.33.32[.]156 against example-victim.com",
        "source_url": "https://www.cisa.gov/news/x",
    })
    assert r.status_code == 201
    obs_id = r.json()["id"]
    body = client.get(f"/selectors/{quote('cve:CVE-2031-11111', safe='')}/detail").json()
    assert body["selector"]["kind"] == "cve"
    assert body["observation_count"] == 1
    assert body["sightings"][0]["observation_id"] == obs_id
    assert "CVE-2031-11111" in body["sightings"][0]["context"]
    assert body["source_hosts"] == ["www.cisa.gov"]
    ip = client.get("/selectors/ip:45.33.32.156/detail").json()
    assert ip["sightings"][0]["defanged"] is True
    # Aynı gözlemde geçen diğer seçiciler birlikte görünür.
    assert "ip:45.33.32.156" in {c["id"] for c in body["co_occurring"]}


def test_reindex_is_idempotent(client):
    client.post("/observations", json={"raw_content": "Second report on CVE-2031-22222"})
    first = client.post("/selectors/reindex").json()
    second = client.post("/selectors/reindex").json()
    assert second["new_sightings"] == 0
    assert second["selectors_total"] == first["selectors_total"]


def test_manual_selector_detect_list_ignore_and_entity_link(client, make_entity):
    r = client.post("/selectors", json={"value": "hxxp://manual-example[.]org/path"})
    assert r.status_code == 201
    sel = r.json()
    assert sel["id"] == "url:http://manual-example.org/path" and sel["origin"] == "manual"
    assert client.post("/selectors", json={"value": "???"}).status_code == 422

    det = client.post("/selectors/detect", json={"value": "manual-example.org/../"}).json()
    assert det["kind"] is None or det["kind"] == "domain"
    det = client.post("/selectors/detect", json={"value": "hxxp://manual-example[.]org/path"}).json()
    assert det["exists"] is True

    listed = client.get("/selectors", params={"kind": "url", "q": "manual-example"}).json()
    assert [i["id"] for i in listed["items"]] == [sel["id"]]

    sid = quote(sel["id"], safe="")
    assert client.patch(f"/selectors/{sid}", json={"status": "IGNORED"}).json()["status"] == "IGNORED"
    assert client.get("/selectors", params={"kind": "url", "q": "manual-example"}).json()["total"] == 0

    entity = make_entity()
    assert client.post(f"/selectors/{sid}/entities", json={"entity_id": entity["id"]}).status_code == 201
    assert [s["id"] for s in client.get(f"/entities/{entity['id']}/selectors").json()] == [sel["id"]]
    assert client.delete(f"/selectors/{sid}/entities/{entity['id']}").status_code == 204
    assert client.delete(f"/selectors/{sid}/entities/{entity['id']}").status_code == 404


def test_extract_endpoint_does_not_write(client):
    before = client.get("/selectors", params={"q": "never-written-example"}).json()["total"]
    found = client.post("/selectors/extract", json={"text": "see never-written-example.net and CVE-2031-99999"}).json()
    assert {f["kind"] for f in found} == {"domain", "cve"}
    assert client.get("/selectors", params={"q": "never-written-example"}).json()["total"] == before


def test_source_self_reference_is_not_an_indicator(client):
    # CISA'nın kendi footer bağlantısı CISA advisory'sinde gösterge değildir; vendor bağlantısı öyledir.
    client.post("/observations", json={
        "raw_content": "See https://www.cisa.gov/privacy-policy-selftest and vendor https://selftest-vendor.example.com/fix",
        "source_url": "https://www.cisa.gov/news-events/ics-advisories/x",
    })
    assert client.get("/selectors", params={"q": "privacy-policy-selftest"}).json()["total"] == 0
    assert client.get("/selectors", params={"q": "selftest-vendor"}).json()["total"] >= 1


def test_registrable_domain():
    from app.selectorindex import registrable_domain
    assert registrable_domain("www.cisa.gov") == "cisa.gov"
    assert registrable_domain("support.example.co.uk") == "example.co.uk"
    assert registrable_domain("haber.sabah.com.tr") == "sabah.com.tr"


def test_search_groups_and_detection(client, make_entity, make_source, make_claim):
    entity = make_entity(name="Searchable Holding Zeta")
    src = make_source()
    make_claim(src["id"], text="Searchable Holding Zeta announced a breach")
    body = client.get("/search", params={"q": "holding zeta"}).json()
    keys = {g["key"] for g in body["groups"]}
    assert {"entities", "claims"} <= keys
    assert body["groups"][0]["items"][0]["href"] == f"/entities/{entity['id']}"
    det = client.get("/search", params={"q": "hxxps://pivot-search[.]example/x"}).json()["detected"]
    assert det["kind"] == "url" and det["value"] == "https://pivot-search.example/x"


def test_claim_selectors_come_from_producing_observation(client, make_source):
    src = make_source()
    obs = client.post("/observations", json={"raw_content": "Patch CVE-2031-77777 now", "source_url": "https://news.example/a"}).json()
    r = client.post(f"/observations/{obs['id']}/promote", json={"source_id": src["id"], "text": "Patch CVE-2031-77777 now"})
    assert r.status_code in (200, 201), r.text
    claim_id = r.json().get("claim_id") or r.json()["claim"]["id"]
    sels = client.get(f"/claims/{claim_id}/selectors").json()
    assert [s["id"] for s in sels] == ["cve:CVE-2031-77777"]


def test_unknown_tld_is_not_a_domain():
    # Gerçek bir CISA advisory'sindeki bozuk yazım: `.ews` IANA'da yok.
    found = _kinds("C2 at https://upl.natcloudservice[.]com.ews and https://ok.example.org/x")
    assert "upl.natcloudservice.com.ews" not in found.get("domain", set())
    assert "ok.example.org" in found["domain"]
    assert detect("something.notarealtld") is None


def test_plain_as_numbers_need_network_context():
    assert "asn" not in _kinds("Runs on IBM AS400 and is AS 9100 certified")
    assert _kinds("traffic from ASN 64600 and AS13335")["asn"] == {"AS13335"}  # 64600 özel aralık (RFC 6996)
    assert _kinds("announced by AS13335")["asn"] == {"AS13335"}


def test_bad_port_url_does_not_crash_extraction():
    found = _kinds("PoC: curl http://target:port/x and http://a.example.com:99999/ then https://ok.example.com:8443/a")
    assert found["url"] == {"https://ok.example.com:8443/a"}


def test_export_csv_and_stix(client):
    import json

    client.post("/selectors", json={"value": "export-me.example.org"})
    client.post("/selectors", json={"value": "CVE-2031-80808"})
    client.post("/selectors", json={"value": "AS13335"})
    csv_text = client.get("/selectors/export", params={"q": "export-me"}).text
    assert csv_text.splitlines()[0].startswith("kind,value") and "export-me.example.org" in csv_text
    bundle = json.loads(client.get("/selectors/export", params={"format": "stix"}).text)
    assert bundle["type"] == "bundle"
    by_name = {o.get("name"): o for o in bundle["objects"]}
    assert by_name["domain: export-me.example.org"]["pattern"] == "[domain-name:value = 'export-me.example.org']"
    assert by_name["CVE-2031-80808"]["type"] == "vulnerability"
    assert by_name["asn: AS13335"]["pattern"] == "[autonomous-system:number = 13335]"
    # Kimlikler seçiciden türetilir: ikinci dışa aktarım aynı kimliği verir.
    again = json.loads(client.get("/selectors/export", params={"format": "stix"}).text)
    ids = {o.get("name"): o["id"] for o in again["objects"]}
    assert ids["CVE-2031-80808"] == by_name["CVE-2031-80808"]["id"]
