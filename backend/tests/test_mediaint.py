"""Faz 34 — MEDIAINT: görsel analizi, GPS → koordinat seçicisi, önizleme, güneş konumu."""
import io
from datetime import datetime, timezone

from PIL import Image, PngImagePlugin

from app import doc_worker, mediaint, solar


def _jpeg_with_exif() -> bytes:
    img = Image.new("RGB", (64, 48), (120, 160, 200))
    for x in range(64):
        img.putpixel((x, x % 48), (250, 20, 20))
    exif = Image.Exif()
    exif[0x010F] = "TestCam"          # Make
    exif[0x0110] = "Model X"          # Model
    exif[0x0131] = "Adobe Photoshop 25.0"  # Software
    exif[0x0132] = "2026:05:02 10:00:00"   # DateTime
    gps = exif.get_ifd(0x8825)
    gps.update({1: "N", 2: (41.0, 0.0, 29.52), 3: "E", 4: (28.0, 58.0, 42.24)})
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _upload(client, data: bytes, name: str) -> str:
    r = client.post("/evidence/upload", files={"file": (name, data)}, data={"evidence_type": "fotoğraf"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_image_evidence_is_analysed_and_gps_becomes_a_selector(client):
    eid = _upload(client, _jpeg_with_exif(), "saha.jpg")
    doc_worker.process_evidence(eid)
    body = client.get(f"/evidence/{eid}/media").json()
    a = body["analysis"]
    assert a["image"]["format"] == "JPEG"
    assert a["exif"]["Make"] == "TestCam"
    assert abs(a["gps"]["lat"] - 41.0082) < 1e-3 and abs(a["gps"]["lon"] - 28.9784) < 1e-3
    assert "EDITED" in {f["code"] for f in a["flags"]}
    assert len(a["hashes"]["dhash"]) == 16
    sel = client.get("/selectors/coord:41.008200,28.978400/detail").json()
    assert sel["documents"][0]["evidence_id"] == eid
    preview = client.get(f"/evidence/{eid}/preview")
    assert preview.status_code == 200 and preview.headers["content-type"] == "image/png"


def test_ai_generation_declared_in_png_text_chunk(tmp_path):
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", "a city at night, Steps: 30, Sampler: Euler a, Model: sdxl — Stable Diffusion")
    path = tmp_path / "gen.png"
    Image.new("RGB", (32, 32), (10, 10, 10)).save(path, pnginfo=info)
    a = mediaint.analyze(path)
    assert "AI_DECLARED" in {f["code"] for f in a["flags"]}
    assert "parameters" in a["text_chunks"]


def test_perceptual_hash_survives_reencoding(tmp_path):
    img = Image.new("RGB", (200, 150))
    for x in range(200):
        for y in range(150):
            img.putpixel((x, y), ((x * 3) % 256, (y * 5) % 256, (x + y) % 256))
    a, b = tmp_path / "a.png", tmp_path / "b.jpg"
    img.save(a)
    img.resize((100, 75)).save(b, quality=60)
    with Image.open(a) as ia, Image.open(b) as ib:
        assert mediaint.hamming(mediaint.dhash(ia), mediaint.dhash(ib)) <= 6


def test_sun_position_and_chronolocation_round_trip(client):
    when = datetime(2026, 10, 24, 8, 30, tzinfo=timezone.utc)
    pos = solar.sun_position(41.0082, 28.9784, when)
    # astral 3.2 ile karşılaştırıldı: azimut 156.66°, yükseklik 34.20°.
    assert abs(pos["azimuth"] - 156.66) < 0.1 and abs(pos["elevation"] - 34.20) < 0.1
    sh = solar.shadow(pos["elevation"], pos["azimuth"])
    r = client.post("/tools/chronolocate", json={
        "lat": 41.0082, "lon": 28.9784, "day": "2026-10-24",
        "shadow_direction": sh["direction"], "length_ratio": sh["length_ratio"],
    })
    best = r.json()["windows"][0]
    assert best["from_utc"] <= "2026-10-24T08:30:00+00:00" <= best["to_utc"]
    day = client.get("/tools/sun", params={"lat": 41.0082, "lon": 28.9784, "day": "2026-06-21"}).json()["day"]
    assert day["sunrise_utc"].startswith("2026-06-21T02:3")
