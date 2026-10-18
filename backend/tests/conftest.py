"""Test altyapısı — her koşu kendi geçici veri kökünde, gerçek `data/`ya dokunmadan.

`OSINTLAB_DATA_DIR` uygulama modülleri İLK import edilmeden önce ayarlanmalı: `app.db`, veri
kökünü import anında sabitliyor (Faz 13'ün dersi — test verisi gerçek grafa yazıldığında iki
gerçek Evidence kaydı silinmişti). Bu yüzden ortam değişkenleri bu dosyanın en başında.
"""
import os
import sys
import tempfile
import uuid
from pathlib import Path

_DATA_ROOT = Path(tempfile.mkdtemp(prefix="osintlab-test-"))
os.environ["OSINTLAB_DATA_DIR"] = str(_DATA_ROOT)
os.environ["OSINTLAB_SCHEDULER"] = "0"
# TestClient `Host: testserver` gönderir; DNS-rebinding korumasının izin listesine eklenir.
os.environ["OSINTLAB_ALLOWED_HOSTS"] = "testserver"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import vault  # noqa: E402
from app.db import DATA_ROOT, get_connection  # noqa: E402
from app.main import app  # noqa: E402

# Emniyet kemeri: veri kökü gerçek proje klasörüne çözülüyorsa testler hiç başlamamalı.
_REAL_DATA = (Path(__file__).resolve().parent.parent.parent / "data").resolve()
assert DATA_ROOT.resolve() != _REAL_DATA, "Testler gerçek data/ klasörüne bağlandı — durduruldu"


@pytest.fixture(scope="session", autouse=True)
def background_vault_renderer():
    # Üretimdeki gibi: yazma uçları vault'u arka plan iş parçacığına bırakır. Bu olmadan her
    # yazma isteği senkron tam render yapar ve test süresi grafla birlikte büyür.
    vault.start_background_renderer()
    yield
    vault.stop_background_renderer()


@pytest.fixture(scope="session")
def client() -> TestClient:
    # Lifespan bilerek ÇALIŞTIRILMIYOR (context manager yok): zamanlayıcı ve belge işçisi
    # testlerde kapalı.
    return TestClient(app)


@pytest.fixture(scope="session")
def conn():
    return get_connection()


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def make_source(client):
    def _make(name: str | None = None, reliability: float = 0.8, url: str | None = None) -> dict:
        r = client.post(
            "/sources",
            json={"name": name or _uid("Kaynak"), "source_type": "haber sitesi", "reliability": reliability, "url": url},
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def make_entity(client):
    def _make(name: str | None = None, entity_type: str = "Organization") -> dict:
        r = client.post("/entities", json={"name": name or _uid("Entity"), "entity_type": entity_type})
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def make_event(client):
    def _make(title: str | None = None) -> dict:
        r = client.post("/events", json={"title": title or _uid("Olay"), "event_type": "açıklama"})
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def make_claim(client):
    def _make(source_id: str, text: str | None = None, **extra) -> dict:
        r = client.post("/claims", json={"text": text or _uid("İddia metni"), "source_id": source_id, **extra})
        assert r.status_code == 201, r.text
        return r.json()

    return _make


@pytest.fixture
def make_investigation(client):
    def _make(title: str | None = None) -> dict:
        r = client.post("/investigations", json={"title": title or _uid("Araştırma"), "research_question": "Ne oldu?"})
        assert r.status_code == 201, r.text
        return r.json()

    return _make
