"""Claim katmanının değişmezleri — 2026-10-18 denetiminde bulunan açıkların regresyon testleri."""
from datetime import datetime, timedelta, timezone


def test_claim_cannot_be_about_entity_and_event(client, make_source, make_entity, make_event):
    src, ent, ev = make_source(), make_entity(), make_event()
    r = client.post(
        "/claims",
        json={"text": "x iddiası", "source_id": src["id"], "about_entity_id": ent["id"], "about_event_id": ev["id"]},
    )
    assert r.status_code == 422


def test_blank_claim_text_rejected(client, make_source):
    r = client.post("/claims", json={"text": "   ", "source_id": make_source()["id"]})
    assert r.status_code == 422


def test_validation_happens_before_any_write(client, make_source):
    # Var olmayan bir supersede hedefi: istek reddedilmeli VE hiçbir claim yazılmamalı.
    src = make_source()
    before = len(client.get("/claims").json())
    r = client.post("/claims", json={"text": "yarım kalmamalı", "source_id": src["id"], "supersedes": "yok-boyle-bir-id"})
    assert r.status_code == 404
    assert len(client.get("/claims").json()) == before


def test_corroboration_on_create_requires_independent_roots(client, make_source, make_claim):
    src = make_source()
    first = make_claim(src["id"])
    # Aynı kaynaktan doğrulama: önceden promote/create yolu bunu denetimsiz kabul ediyordu.
    r = client.post("/claims", json={"text": "aynı kaynak", "source_id": src["id"], "corroborates": [first["id"]]})
    assert r.status_code == 422
    other = make_source()
    ok = make_claim(other["id"], corroborates=[first["id"]])
    explain = client.get(f"/claims/{first['id']}/explain").json()
    assert explain["corroboration"] > 0
    assert any(c["claim_id"] == ok["id"] for c in explain["corroborated_by"])


def test_corroboration_rejects_shared_lineage_root(client, make_source, make_claim):
    agency, site = make_source(), make_source()
    r = client.post(f"/sources/{site['id']}/derived-from", json={"upstream_source_id": agency["id"]})
    assert r.status_code == 200, r.text
    base = make_claim(agency["id"])
    r = client.post("/claims", json={"text": "türetilmiş", "source_id": site["id"], "corroborates": [base["id"]]})
    assert r.status_code == 422
    assert "bağımsız" in r.json()["detail"]


def test_links_batch_skips_same_root(client, make_source, make_claim):
    src = make_source()
    a, b = make_claim(src["id"]), make_claim(src["id"])
    r = client.post("/claims/links-batch", json={"pairs": [{"claim_a_id": a["id"], "claim_b_id": b["id"], "link": "CORROBORATES"}]})
    body = r.json()
    assert body["linked"] == 0 and body["skipped"] == 1


def test_supersede_rules(client, make_source, make_claim):
    src = make_source()
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    old = make_claim(src["id"], valid_from=t0.isoformat())
    newer = make_claim(src["id"], valid_from=(t0 + timedelta(days=5)).isoformat(), supersedes=old["id"])
    assert client.get(f"/claims/{old['id']}").json()["superseded_by_claim_id"] == newer["id"]

    # İkinci kez yerini alma: 409 (önceden create/promote yolunda kontrol yoktu).
    r = client.post("/claims", json={"text": "üçüncü", "source_id": src["id"], "supersedes": old["id"],
                                      "valid_from": (t0 + timedelta(days=9)).isoformat()})
    assert r.status_code == 409

    # Zaman çizgisi tersine dönemez.
    young = make_claim(src["id"], valid_from=(t0 + timedelta(days=30)).isoformat())
    r = client.post("/claims", json={"text": "geçmişten", "source_id": src["id"], "supersedes": young["id"],
                                      "valid_from": t0.isoformat()})
    assert r.status_code == 422


def test_supersede_cycle_rejected(client, make_source, make_claim):
    src = make_source()
    same = datetime(2026, 2, 1, tzinfo=timezone.utc).isoformat()
    a = make_claim(src["id"], valid_from=same)
    b = make_claim(src["id"], valid_from=same)
    assert client.post(f"/claims/{a['id']}/supersedes", json={"supersedes_claim_id": b["id"]}).status_code == 200
    r = client.post(f"/claims/{b['id']}/supersedes", json={"supersedes_claim_id": a["id"]})
    assert r.status_code in (409, 422)


def test_list_claims_matches_single_get(client, make_source, make_entity, make_claim):
    src, ent = make_source(), make_entity()
    c = make_claim(src["id"], about_entity_id=ent["id"])
    listed = {x["id"]: x for x in client.get("/claims").json()}
    single = client.get(f"/claims/{c['id']}").json()
    assert listed[c["id"]] == single
    assert single["about_entity_id"] == ent["id"]
    assert single["source_id"] == src["id"]


def test_moving_claim_to_event_carries_entity_and_recomputes_old_event(
    client, make_source, make_entity, make_event, make_claim
):
    src, ent = make_source(reliability=1.0), make_entity()
    ev1, ev2 = make_event(), make_event()
    c = make_claim(src["id"], about_entity_id=ent["id"])

    # PUT /events/{id}/claims: entity INVOLVED_IN ile taşınmalı (önceden sessizce düşüyordu).
    r = client.put(f"/events/{ev1['id']}/claims/{c['id']}")
    assert r.status_code == 200
    assert r.json()["confidence"] > 0
    recall = client.get(f"/entities/{ent['id']}/recall").json()
    assert any(e["id"] == ev1["id"] for e in recall["related_events"])

    # PATCH about ile başka olaya: eski olayın türetilmiş skoru sıfırlanmalı.
    r = client.patch(f"/claims/{c['id']}/about", json={"about_event_id": ev2["id"]})
    assert r.status_code == 200
    assert client.get(f"/events/{ev1['id']}").json()["confidence"] == 0.0
    assert client.get(f"/events/{ev2['id']}").json()["confidence"] > 0


def test_delete_event_with_claims_is_refused(client, make_source, make_event, make_claim):
    ev = make_event()
    c = make_claim(make_source()["id"], about_event_id=ev["id"])
    assert client.delete(f"/events/{ev['id']}").status_code == 409
    assert client.delete(f"/events/{ev['id']}/claims/{c['id']}").status_code == 200
    assert client.delete(f"/events/{ev['id']}").status_code == 204


def test_unlink_missing_links_return_404(client, make_entity, make_event, make_source, make_claim):
    ev, ent = make_event(), make_entity()
    c = make_claim(make_source()["id"])
    assert client.delete(f"/events/{ev['id']}/entities/{ent['id']}").status_code == 404
    assert client.delete(f"/events/{ev['id']}/claims/{c['id']}").status_code == 404


def test_promote_is_idempotent_and_renders_once(client, make_source, monkeypatch):
    from app.routers import claims as claims_router
    from app.routers import observations as observations_router

    calls = []
    for module in (claims_router, observations_router):
        monkeypatch.setattr(module, "safe_render_vault", lambda conn: calls.append(1))
    src = make_source()
    obs = client.post("/observations", json={"raw_content": "Promote edilecek gözlem metni"}).json()
    r = client.post(f"/observations/{obs['id']}/promote", json={"source_id": src["id"]})
    assert r.status_code == 200, r.text
    assert len(calls) == 1  # önceden 2: create_claim route'u kendi içinde de render ediyordu
    again = client.post(f"/observations/{obs['id']}/promote", json={"source_id": src["id"]})
    assert again.status_code == 409


def test_input_datetimes_are_normalised_to_utc(client, make_source, make_claim):
    c = make_claim(make_source()["id"], valid_from="2026-03-01T12:00:00+03:00")
    assert client.get(f"/claims/{c['id']}").json()["valid_from"].startswith("2026-03-01T09:00:00")
