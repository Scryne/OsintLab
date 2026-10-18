"""Entity katmanı: ilişkiler, silme koruması, aday ve eşleşme kararlarının kalıcılığı."""


def test_create_relation_returns_201_and_rejects_duplicates(client, make_entity):
    a, b = make_entity(), make_entity()
    r = client.post(f"/entities/{a['id']}/relations", json={"to_entity_id": b["id"], "relation_type": "ortak"})
    # Önceden tanımsız `now` yüzünden ilişki yazılıp 500 dönüyordu.
    assert r.status_code == 201, r.text
    assert r.json()["valid_from"]
    dup = client.post(f"/entities/{a['id']}/relations", json={"to_entity_id": b["id"], "relation_type": "ortak"})
    assert dup.status_code == 409
    assert len(client.get(f"/entities/{a['id']}/relations").json()) == 1


def test_relation_batch_validates_everything_before_writing(client, make_entity):
    a, b = make_entity(), make_entity()
    r = client.post(
        "/entities/relations/batch",
        json={"decisions": [
            {"from_entity_id": a["id"], "to_entity_id": b["id"], "action": "CREATE", "relation_type": "rakip"},
            {"from_entity_id": a["id"], "to_entity_id": "yok", "action": "CREATE", "relation_type": "x"},
        ]},
    )
    assert r.status_code == 404
    assert client.get(f"/entities/{a['id']}/relations").json() == []


def test_used_entity_cannot_be_deleted(client, make_entity, make_source, make_claim):
    used, unused = make_entity(), make_entity()
    make_claim(make_source()["id"], about_entity_id=used["id"])
    r = client.delete(f"/entities/{used['id']}")
    assert r.status_code == 409
    assert "claim öznesi" in r.json()["detail"]
    assert client.delete(f"/entities/{unused['id']}").status_code == 204
    assert client.get(f"/entities/{unused['id']}").status_code == 404


def test_rejected_same_as_is_not_suggested_again(client, make_entity):
    a = make_entity(name="Acme Holding Group")
    b = make_entity(name="Acme Holding")
    assert any(c["entity_id"] == b["id"] for c in client.get(f"/entities/{a['id']}/same-as/candidates").json())
    assert client.post(f"/entities/{a['id']}/same-as", json={"to_entity_id": b["id"]}).status_code == 201
    assert client.post(f"/entities/same-as/{a['id']}/{b['id']}/reject").status_code == 200
    assert not any(c["entity_id"] == b["id"] for c in client.get(f"/entities/{a['id']}/same-as/candidates").json())


def test_confirmed_same_as_counts_once_in_graph(client, make_entity):
    a = make_entity(name="Globex Corporation Ltd")
    b = make_entity(name="Globex Corporation")
    client.post(f"/entities/{a['id']}/same-as", json={"to_entity_id": b["id"]})
    client.post(f"/entities/same-as/{a['id']}/{b['id']}/confirm")
    graph = client.get("/entities/relations/graph").json()
    pair = {a["id"], b["id"]}
    same = [e for e in graph["edges"] if e["kind"] == "same_as" and {e["source"], e["target"]} == pair]
    assert len(same) == 1


def test_candidate_promote_is_not_duplicated(client):
    key = "zz-test-aday"
    body = {"items": [{"key": key, "name": "Zeta Test Aday", "entity_type": "Organization"}]}
    first = client.post("/entities/candidates/promote", json=body).json()
    second = client.post("/entities/candidates/promote", json=body).json()
    assert first["promoted"] == 1 and second["promoted"] == 0
    # PROMOTED bir aday elenemez (kararın üzerine yazmak entity bağını kaybettiriyordu).
    assert client.post("/entities/candidates/dismiss", json={"keys": [key]}).json()["dismissed"] == 0
