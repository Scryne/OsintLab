"""Faz 30 — zenginleştirme motoru: değişmez kayıt, pivot, önbellek, OPSEC kapıları, veri setleri.

Ağa çıkılmaz: gerçek modüller yerine sahte modüller kaydedilir."""
import time
from urllib.parse import quote

import pytest

from app.enrichment import datasets, engine
from app.enrichment.base import ACTIVE, PASSIVE, Module, ModuleError, Pivot, Result
from app.enrichment.modules_net import _mmh3_32
from app.enrichment.modules_world import _match_names

CALLS = {"n": 0}


def _fake_dns(ctx, target):
    CALLS["n"] += 1
    ctx.responses.append({"url": "https://fake/dns", "body": {"A": ["93.184.216.34"]}})
    ctx.request_urls.append("https://fake/dns")
    return Result(
        {"domain": target.value, "records": {"A": ["93.184.216.34"]}},
        [Pivot("resolves_to", "ip", "93.184.216.34"), Pivot("subdomain_of", "domain", f"www.{target.value}", "in")],
    )


def _failing(ctx, target):
    raise ModuleError("kaynak cevap vermedi")


@pytest.fixture(autouse=True)
def fake_modules(monkeypatch):
    monkeypatch.setitem(engine.REGISTRY, "fake-dns", Module(
        "fake-dns", "Sahte DNS", "test", "test", "selector", ("domain",), PASSIVE, frozenset(), _fake_dns, cache_hours=1))
    monkeypatch.setitem(engine.REGISTRY, "fake-active", Module(
        "fake-active", "Sahte aktif", "test", "test", "selector", ("domain",), ACTIVE, frozenset(), _fake_dns))
    monkeypatch.setitem(engine.REGISTRY, "fake-fail", Module(
        "fake-fail", "Sahte hata", "test", "test", "selector", ("domain",), PASSIVE, frozenset(), _failing))


def _selector(client, value):
    r = client.post("/selectors", json={"value": value})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_run_records_raw_with_hash_and_writes_pivots(client):
    sid = _selector(client, "enrich-one.example")
    r = client.post("/enrichment/run", json={"module": "fake-dns", "target_id": sid})
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["status"] == "DONE" and run["cached"] is False
    assert run["raw_sha256"] and run["opsec"] == PASSIVE
    raw = client.get(f"/enrichment/runs/{run['id']}/raw").json()
    assert raw["integrity_ok"] is True
    assert raw["record"]["summary"]["records"]["A"] == ["93.184.216.34"]
    pivots = {(p["relation"], p["to_id"]) for p in run["pivots"]}
    assert ("resolves_to", "ip:93.184.216.34") in pivots
    # "in" yönü: alt alan adı → hedef.
    assert ("subdomain_of", sid) in pivots
    detail = client.get(f"/selectors/{quote(sid, safe='')}/detail").json()
    assert {p["id"] for p in detail["pivots"]} == {"ip:93.184.216.34", "domain:www.enrich-one.example"}
    ip = client.get("/selectors/ip:93.184.216.34/detail").json()
    assert ip["selector"]["origin"] == "enrichment"


def test_cache_prevents_repeat_queries_unless_forced(client):
    sid = _selector(client, "enrich-cache.example")
    before = CALLS["n"]
    first = client.post("/enrichment/run", json={"module": "fake-dns", "target_id": sid}).json()
    second = client.post("/enrichment/run", json={"module": "fake-dns", "target_id": sid}).json()
    assert second["id"] == first["id"] and second["cached"] is True
    assert CALLS["n"] == before + 1
    forced = client.post("/enrichment/run", json={"module": "fake-dns", "target_id": sid, "force": True}).json()
    assert forced["id"] != first["id"] and CALLS["n"] == before + 2
    # Pivot ikinci kez görüldüğünde yeni kenar açılmaz.
    detail = client.get(f"/selectors/{quote(sid, safe='')}/detail").json()
    assert len([p for p in detail["pivots"] if p["relation"] == "resolves_to"]) == 1


def test_failure_is_recorded_not_raised(client):
    sid = _selector(client, "enrich-fail.example")
    run = client.post("/enrichment/run", json={"module": "fake-fail", "target_id": sid}).json()
    assert run["status"] == "FAILED" and "cevap vermedi" in run["error"]


def test_active_module_is_off_by_default_and_needs_confirmation(client):
    sid = _selector(client, "enrich-active.example")
    assert client.post("/enrichment/run", json={"module": "fake-active", "target_id": sid}).status_code == 409
    assert client.patch("/enrichment/modules/fake-active", json={"enabled": True}).status_code == 200
    try:
        assert client.post("/enrichment/run", json={"module": "fake-active", "target_id": sid}).status_code == 428
        ok = client.post("/enrichment/run", json={"module": "fake-active", "target_id": sid, "confirm_active": True})
        assert ok.status_code == 200 and ok.json()["opsec"] == ACTIVE
        # Toplu çalıştırma aktif modülü asla kabul etmez.
        assert client.post("/enrichment/bulk", json={"module": "fake-active", "kind": "domain"}).status_code == 409
    finally:
        client.patch("/enrichment/modules/fake-active", json={"enabled": False})


def test_disabling_a_passive_module(client):
    sid = _selector(client, "enrich-off.example")
    client.patch("/enrichment/modules/fake-dns", json={"enabled": False})
    try:
        assert client.post("/enrichment/run", json={"module": "fake-dns", "target_id": sid}).status_code == 409
    finally:
        client.patch("/enrichment/modules/fake-dns", json={"enabled": True})


def test_wrong_target_kind_is_rejected(client):
    sid = _selector(client, "CVE-2031-55555")
    assert client.post("/enrichment/run", json={"module": "fake-dns", "target_id": sid}).status_code == 422


def test_async_run_finishes_in_background(client):
    sid = _selector(client, "enrich-async.example")
    run = client.post("/enrichment/run", json={"module": "fake-dns", "target_id": sid, "wait": False}).json()
    for _ in range(50):
        if client.get(f"/enrichment/runs/{run['id']}").json()["status"] != "RUNNING":
            break
        time.sleep(0.05)
    assert client.get(f"/enrichment/runs/{run['id']}").json()["status"] == "DONE"


def test_run_becomes_an_observation(client):
    sid = _selector(client, "enrich-obs.example")
    run = client.post("/enrichment/run", json={"module": "fake-dns", "target_id": sid}).json()
    r = client.post(f"/enrichment/runs/{run['id']}/observation")
    assert r.status_code == 201, r.text
    obs = r.json()
    assert obs["text_source"] == "enrichment"
    assert "93.184.216.34" in obs["raw_content"]


def test_target_modules_lists_only_applicable(client):
    sid = _selector(client, "enrich-list.example")
    names = {m["name"] for m in client.get(f"/enrichment/targets/{quote(sid, safe='')}/modules").json()}
    assert {"fake-dns", "dns", "crtsh", "rdap"} <= names
    assert "nvd" not in names


# ---- Veri setleri ve yardımcılar -------------------------------------------------------

def test_ofac_index_and_name_matching():
    sdn = (
        '36,"AEROCARIBBEAN AIRLINES","-0- ","CUBA","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- "\n'
        '173,"ANGLO-CARIBBEAN CO., LTD.","-0- ","CUBA","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ","-0- ",'
        '"Digital Currency Address - XBT 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa; alt. Digital Currency Address - ETH 0xABCDEF0123456789abcdef0123456789ABCDEF01."\n'
    ).encode("latin-1")
    alt = b'173,1,"aka","CARIBBEAN ANGLO TRADING"," "\n'
    index, count = datasets._ofac_index({"sdn": sdn, "alt": alt})
    assert count == 2
    assert index["crypto"]["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]["ent_num"] == "173"
    assert "0xabcdef0123456789abcdef0123456789abcdef01" in index["crypto"]
    assert _match_names(index, "Anglo-Caribbean Company")[0]["ent_num"] == "173"
    assert _match_names(index, "Caribbean Anglo Trading")[0]["score"] == 1.0
    assert _match_names(index, "Siemens") == []


def test_favicon_hash_matches_reference_mmh3():
    # Referans değerler mmh3 kütüphanesinden (mmh3.hash).
    assert _mmh3_32(b"") == 0
    assert _mmh3_32(b"foo") == -156908512
    assert _mmh3_32(b"hello world") == 1586663183


def test_pivot_graph_neighbourhood(client, make_entity):
    sid = _selector(client, "enrich-graph.example")
    client.post("/enrichment/run", json={"module": "fake-dns", "target_id": sid})
    entity = make_entity()
    client.post(f"/selectors/{quote(sid, safe='')}/entities", json={"entity_id": entity["id"]})
    g = client.get(f"/selectors/{quote(sid, safe='')}/graph").json()
    ids = {n["id"] for n in g["nodes"]}
    assert {sid, "ip:93.184.216.34", "domain:www.enrich-graph.example", f"entity:{entity['id']}"} <= ids
    assert {"resolves_to", "subdomain_of", "belongs_to"} <= {e["relation"] for e in g["edges"]}


def test_tool_links_and_dorks(client):
    links = client.get("/tools/links", params={"kind": "cve", "value": "CVE-2024-3400"}).json()
    assert any(link["url"] == "https://nvd.nist.gov/vuln/detail/CVE-2024-3400" for link in links)
    attack = client.get("/tools/links", params={"kind": "attack", "value": "T1059.001"}).json()
    assert attack[0]["url"] == "https://attack.mitre.org/techniques/T1059/001/"
    # URL'in kendi kalıbı olmayan araç, alan adı kalıbına düşer.
    url_links = client.get("/tools/links", params={"kind": "url", "value": "https://evil.example/x"}).json()
    assert any(link["url"] == "https://crt.sh/?q=evil.example" for link in url_links)
    dorks = client.get("/tools/dorks", params={"kind": "domain", "value": "evil.example"}).json()
    assert dorks[0]["query"].startswith("site:evil.example")
    assert client.get("/tools/links", params={"kind": "username", "value": "x"}).status_code == 422
    cat = client.get("/tools").json()
    assert len(cat["tools"]) >= 90 and all(t["category_label"] for t in cat["tools"])


def test_queue_signals_from_selectors(client, make_entity):
    entity = make_entity(name="Quiet Infra Owner")
    sid = _selector(client, "c2-signal.example")
    client.post(f"/selectors/{quote(sid, safe='')}/entities", json={"entity_id": entity["id"]})
    obs = client.post("/observations", json={"raw_content": "Beacon traffic to c2-signal[.]example observed"}).json()
    items = client.get("/observations/queue", params={"limit": 2000}).json()["items"]
    row = next(i for i in items if i["id"] == obs["id"])
    codes = {r["code"] for r in row["signal_reasons"]}
    assert {"KNOWN_SELECTOR", "DEFANGED_IOC"} <= codes
    assert row["signal_score"] >= 0.40


def test_watched_selector_change_lands_in_inbox(client, monkeypatch):
    from app import selectorwatch

    state = {"subs": ["a.watch-me.example"]}

    def fake_crtsh(ctx, target):
        return Result({"domain": target.value, "subdomains": list(state["subs"]), "certificate_count": len(state["subs"])})

    monkeypatch.setitem(engine.REGISTRY, "crtsh", Module(
        "crtsh", "Sertifika şeffaflığı", "test", "test", "selector", ("domain",), PASSIVE, frozenset(), fake_crtsh))
    monkeypatch.setitem(selectorwatch.WATCH_MODULES, "domain", ("crtsh",))
    sid = _selector(client, "watch-me.example")
    assert client.post("/monitors", json={"target_type": "Selector", "target_id": sid}).status_code == 201

    first = client.post(f"/selectors/{quote(sid, safe='')}/watch-check").json()
    assert first["notices"] == []  # ilk koşu taban çizgisi
    state["subs"] = ["a.watch-me.example", "vpn.watch-me.example"]
    second = client.post(f"/selectors/{quote(sid, safe='')}/watch-check").json()
    assert len(second["notices"]) == 1 and second["notices"][0]["priority"] == "MEDIUM"
    items = [i for i in client.get("/inbox").json() if i["target_id"] == sid]
    assert items and "vpn.watch-me.example" in items[0]["title"]


def test_watch_diff_rules():
    from app.selectorwatch import diff

    assert diff("kev", {"in_kev": False}, {"in_kev": True, "date_added": "2026-10-01"})[0]["code"] == "KEV_ADDED"
    assert diff("dns", {"records": {"A": ["1.1.1.1"]}}, {"records": {"A": ["2.2.2.2"]}})[0]["code"] == "DNS_ADDED"
    assert diff("internetdb", {"ports": [22]}, {"ports": [22]}) == []
