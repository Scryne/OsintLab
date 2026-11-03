"""Platform katmanı: CSRF/DNS rebinding koruması, kuyruk önbelleği, vault, lineage, kanıt yolu,
arşiv doğrulaması ve zamanlanmış tarama hatalarının kayda geçmesi."""
from datetime import datetime, timezone

import pytest

from app import archive, scanning, vault
from app.collector import CollectorFetchError
from app.lineage import resolve_independent_root
from app.routers.evidence import _is_anchored


# ---- Güvenlik ara katmanı --------------------------------------------------

def test_cross_site_write_is_rejected(client):
    r = client.post("/entities", json={"name": "csrf", "entity_type": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_allowed_origin_and_headerless_clients_can_write(client):
    ok = client.post("/entities", json={"name": "yerel", "entity_type": "x"}, headers={"Origin": "http://localhost:3000"})
    assert ok.status_code == 201
    assert client.post("/entities", json={"name": "curl", "entity_type": "x"}).status_code == 201


def test_default_origins_are_only_local_3000():
    from app.main import frontend_origins

    assert frontend_origins(None) == ("http://localhost:3000", "http://127.0.0.1:3000")
    assert frontend_origins("") == frontend_origins(" , ")
    # Varsayılan port tekrar verilirse liste şişmez.
    assert frontend_origins("3000") == frontend_origins(None)


def test_frontend_port_adds_only_local_origins():
    from app.main import frontend_origins

    assert frontend_origins("3001, 4000") == (
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
        "http://localhost:4000", "http://127.0.0.1:4000",
    )


@pytest.mark.parametrize("bad", [
    "*", "evil.example", "http://evil.example:3001", "localhost:3001", "3001/x", "0", "65536", "-1", "3e3", "٣٠٠١",
])
def test_frontend_port_rejects_anything_but_a_port(bad):
    from app.main import frontend_origins

    with pytest.raises(ValueError):
        frontend_origins(bad)


def test_frontend_port_env_feeds_both_cors_and_csrf(tmp_path):
    """Uçtan uca: ortam değişkeni ayrı bir süreçte, uygulama import edilmeden ÖNCE veriliyor —
    tıpkı start.ps1'in yaptığı gibi. Ek port hem CORS'ta hem CSRF'te açılır; yabancı origin ve
    ek portun yerel olmayan hâli yine reddedilir."""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = """
import json
from fastapi.testclient import TestClient
from app.main import app, ALLOWED_ORIGINS
c = TestClient(app)
def write(origin):
    h = {"Origin": origin} if origin else {}
    return c.post("/entities", json={"name": "cors-" + str(origin), "entity_type": "x"}, headers=h).status_code
def preflight(origin):
    r = c.options("/entities", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    return r.headers.get("access-control-allow-origin")
print(json.dumps({
    "origins": list(ALLOWED_ORIGINS),
    "write_3001": write("http://localhost:3001"),
    "write_3001_ip": write("http://127.0.0.1:3001"),
    "write_3000": write("http://localhost:3000"),
    "write_evil_3001": write("http://evil.example:3001"),
    "write_3002": write("http://localhost:3002"),
    "write_headerless": write(None),
    "cors_3001": preflight("http://localhost:3001"),
    "cors_evil": preflight("http://evil.example:3001"),
}))
"""
    env = {**os.environ, "OSINTLAB_FRONTEND_PORT": "3001", "OSINTLAB_DATA_DIR": str(tmp_path),
           "OSINTLAB_SCHEDULER": "0", "OSINTLAB_ALLOWED_HOSTS": "testserver", "PYTHONUTF8": "1"}
    backend_dir = Path(__file__).resolve().parent.parent
    out = subprocess.run([sys.executable, "-c", script], cwd=backend_dir, env=env,
                         capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout.strip().splitlines()[-1])
    assert r["origins"] == ["http://localhost:3000", "http://127.0.0.1:3000",
                            "http://localhost:3001", "http://127.0.0.1:3001"]
    assert r["write_3001"] == r["write_3001_ip"] == r["write_3000"] == r["write_headerless"] == 201
    assert r["write_evil_3001"] == 403 and r["write_3002"] == 403
    assert r["cors_3001"] == "http://localhost:3001"
    assert r["cors_evil"] is None


def test_invalid_frontend_port_stops_startup(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = {**os.environ, "OSINTLAB_FRONTEND_PORT": "*", "OSINTLAB_DATA_DIR": str(tmp_path), "OSINTLAB_SCHEDULER": "0"}
    out = subprocess.run([sys.executable, "-c", "import app.main"], cwd=Path(__file__).resolve().parent.parent,
                         env=env, capture_output=True, text=True, timeout=180)
    assert out.returncode != 0 and "OSINTLAB_FRONTEND_PORT" in out.stderr


def test_foreign_host_header_is_rejected(client):
    # DNS rebinding: saldırganın alan adı 127.0.0.1'e çözülse bile Host başlığı onu ele verir.
    assert client.get("/health", headers={"Host": "attacker.example"}).status_code == 400


def test_health_reports_background_mechanisms(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "vault" in body and "ocr" in body


# ---- Promote Kuyruğu önbelleği -------------------------------------------------

def test_queue_cache_is_invalidated_by_new_observations(client):
    before = client.get("/observations/queue?limit=1").json()["stats"]["pending"]
    client.post("/observations", json={"raw_content": "Kuyruğa yeni düşen gözlem"})
    after = client.get("/observations/queue?limit=1").json()["stats"]["pending"]
    assert after == before + 1


def test_queue_count_matches_scored_queue_without_scoring(client, monkeypatch):
    from app import triage

    client.post("/observations", json={"raw_content": "Rozet sayacı için gözlem"})
    pending = client.get("/observations/queue?limit=1").json()["stats"]["pending"]

    def skorlama_yok(*_a, **_k):
        raise AssertionError("rozet sayacı skorlamaya girmemeli")

    monkeypatch.setattr(triage, "_score_all", skorlama_yok)
    assert client.get("/observations/queue/count").json() == {"pending": pending}
    client.post("/observations", json={"raw_content": "Bir tane daha"})
    assert client.get("/observations/queue/count").json() == {"pending": pending + 1}


def test_word_matching_respects_boundaries():
    assert scanning.contains_word("meta's new model", "meta")
    assert not scanning.contains_word("metadata leak", "meta")
    assert scanning.contains_word("(openai) said", "openai")


# ---- Vault -----------------------------------------------------------------------

def test_yaml_scalar_escapes_backslash_and_newlines():
    assert vault._yaml_scalar('x\\') == '"x\\\\"'
    assert "\n" not in vault._yaml_scalar("a\nb")


def test_sync_dir_removes_orphans_and_skips_unchanged(tmp_path):
    (tmp_path / "eski.md").write_text("eski", encoding="utf-8")
    vault._sync_dir(tmp_path, {"yeni.md": "içerik"})
    assert sorted(p.name for p in tmp_path.iterdir()) == ["yeni.md"]
    before = (tmp_path / "yeni.md").stat().st_mtime_ns
    assert vault._write(tmp_path / "yeni.md", "içerik") is False
    assert (tmp_path / "yeni.md").stat().st_mtime_ns == before


def test_vault_render_endpoint_is_synchronous(client, make_entity):
    ent = make_entity(name="Vault Render Testi")
    r = client.post("/vault/render")
    assert r.status_code == 200
    notes = list((vault.VAULT_DIR / "entities").glob("*.md"))
    assert any("Vault Render Testi" in p.read_text(encoding="utf-8") for p in notes), ent


# ---- Lineage -----------------------------------------------------------------------

def test_lineage_cycle_resolves_to_single_root(conn, make_source):
    a, b = make_source(), make_source()
    now = datetime.now(timezone.utc)
    for down, up in ((a, b), (b, a)):
        conn.execute(
            "MATCH (d:Source {id: $d}), (u:Source {id: $u}) "
            "CREATE (d)-[:DERIVED_FROM {method: 'TEST', similarity: 1.0, shared_agencies: '', detected_at: $now}]->(u)",
            {"d": down["id"], "u": up["id"], "now": now},
        )
    # Önceden A'dan bakınca kök A, B'den bakınca B çıkıyordu: türeyen iki kaynak "bağımsız".
    assert resolve_independent_root(conn, a["id"]) == resolve_independent_root(conn, b["id"])


# ---- Kanıt yolu ----------------------------------------------------------------------

@pytest.mark.parametrize("path", [r"\\host\share\f.pdf", "//host/share", "C:/Windows/win.ini", "/etc/passwd"])
def test_anchored_paths_are_never_touched(path):
    assert _is_anchored(path)


def test_evidence_create_does_not_hash_files_outside_vault(client, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("gizli", encoding="utf-8")
    r = client.post("/evidence", json={"evidence_type": "belge", "file_path": str(secret)})
    assert r.status_code == 201
    assert r.json()["content_hash"] is None


# ---- Arşiv doğrulaması ------------------------------------------------------------------

def _archived_claim(client, make_source):
    src = make_source()
    obs = client.post(
        "/observations",
        json={"raw_content": "Arşivlenecek başlık satırı yeterince uzun\n\nÖzet", "source_url": "https://example.com/a"},
    ).json()
    claim = client.post(f"/observations/{obs['id']}/promote", json={"source_id": src["id"]}).json()["claim"]
    return claim["id"], archive.existing_archive(archive_conn(), claim["id"])["id"]


def archive_conn():
    from app.db import get_connection

    return get_connection()


def test_transient_failure_keeps_verified_evidence(client, conn, make_source, monkeypatch):
    claim_id, evidence_id = _archived_claim(client, make_source)
    page = "<html><body><p>Arşivlenecek başlık satırı yeterince uzun</p></body></html>".encode("utf-8")
    monkeypatch.setattr(archive, "safe_fetch", lambda url, allow: (url, page, "text/html"))
    assert archive.verify_archive(conn, evidence_id, claim_id)["status"] == archive.DOGRULANDI

    def down(url, allow):
        raise CollectorFetchError("503", status_code=503)

    monkeypatch.setattr(archive, "safe_fetch", down)
    result = archive.verify_archive(conn, evidence_id, claim_id)
    assert result["status"] == archive.DOGRULANDI and result["scored"] is True

    def gone(url, allow):
        raise CollectorFetchError("404", status_code=404)

    monkeypatch.setattr(archive, "safe_fetch", gone)
    result = archive.verify_archive(conn, evidence_id, claim_id)
    assert result["status"] == archive.ERISILEMEDI and result["scored"] is False


# ---- Zamanlanmış tarama ----------------------------------------------------------------

def test_unexpected_scan_error_is_recorded_not_swallowed(conn, make_source, monkeypatch):
    src = make_source(url="https://example.com/feed")
    schedule_id = scanning.create_schedule(
        conn, source_id=src["id"], url="https://example.com/feed", mode="rss",
        interval_minutes=60, item_limit=5, since_days=7, label=None,
    )

    def explode(*a, **k):
        raise ValueError("ayrıştırıcı patladı")

    monkeypatch.setattr(scanning, "collect_from_url", explode)
    result = scanning.run_schedule(conn, schedule_id)
    assert result["status"] == "ERROR"
    row = scanning.get_schedule_row(conn, schedule_id)
    assert row["last_run_at"] is not None and row["consecutive_failures"] == 1


def test_same_schedule_cannot_run_twice_at_once(conn, make_source):
    scanning._running.add("kilitli-tarama")
    try:
        with pytest.raises(scanning.ScheduleBusyError):
            scanning.run_schedule(conn, "kilitli-tarama")
    finally:
        scanning._running.discard("kilitli-tarama")


def test_schedule_patch_rejects_null_interval(client, conn, make_source):
    src = make_source()
    sid = scanning.create_schedule(
        conn, source_id=src["id"], url=f"https://example.com/{src['id']}", mode="rss",
        interval_minutes=60, item_limit=5, since_days=7, label=None,
    )
    assert client.patch(f"/collectors/schedules/{sid}", json={"interval_minutes": None}).status_code == 422
    assert client.patch(f"/collectors/schedules/{sid}", json={"since_days": 999999}).status_code == 422
