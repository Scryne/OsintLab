"""Kuyruk tazeliği (app/aging.py): değerlendirilmeyen gözlem süresi dolunca elenir, silinmez.

Kurallar: düşük sinyal 7 gün, yüksek sinyal 21 gün; elle girilen/belgeden gelen/izlenen ya da
açık investigation'a değen gözlem hiç yaşlanmaz; eleme gerekçesi yazılı ve geri alınabilir.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app import aging, triage


def _observe(client, text: str, url: str | None = "https://news.example.org/a") -> str:
    body = {"raw_content": text}
    if url:
        body["source_url"] = f"{url}/{uuid.uuid4().hex[:6]}"
    res = client.post("/observations", json=body)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _backdate(conn, observation_id: str, days: int) -> None:
    conn.execute(
        "MATCH (o:Observation) WHERE o.id = $id SET o.created_at = $at",
        {"id": observation_id, "at": datetime.now(timezone.utc) - timedelta(days=days)},
    )


def _state(conn, observation_id: str) -> dict:
    rows = conn.execute(
        "MATCH (o:Observation) WHERE o.id = $id RETURN o.dismissed AS d, o.dismiss_reason AS r",
        {"id": observation_id},
    )
    row = rows.get_next()
    return {"dismissed": bool(row[0]), "reason": row[1]}


def test_low_signal_ages_out_after_a_week_and_can_be_restored(client, conn):
    stale = _observe(client, f"Bir yerel belediye duyurusu {uuid.uuid4().hex}")
    fresh = _observe(client, f"Bir başka belediye duyurusu {uuid.uuid4().hex}")
    _backdate(conn, stale, aging.LOW_SIGNAL_DAYS)
    _backdate(conn, fresh, aging.LOW_SIGNAL_DAYS - 1)

    result = aging.age_out(conn)

    assert result["low"] >= 1
    stale_state = _state(conn, stale)
    assert stale_state["dismissed"] is True
    assert stale_state["reason"].startswith(aging.REASON_PREFIX)
    assert "düşük sinyal" in stale_state["reason"] and "Geri alınabilir" in stale_state["reason"]
    assert _state(conn, fresh)["dismissed"] is False

    # Silinmedi: geri alınınca kuyruğa döner.
    res = client.post("/observations/undismiss", json={"observation_ids": [stale]})
    assert res.status_code == 200 and res.json()["dismissed"] == 1
    assert _state(conn, stale)["dismissed"] is False


def test_high_signal_gets_three_weeks(client, conn, make_entity):
    entity = make_entity(name=f"Yaşlanma Şirketi {uuid.uuid4().hex[:5]}")
    week_old = _observe(client, f"{entity['name']} yeni bir ürün duyurdu")
    month_old = _observe(client, f"{entity['name']} soruşturma altında")
    _backdate(conn, week_old, aging.LOW_SIGNAL_DAYS + 3)
    _backdate(conn, month_old, aging.HIGH_SIGNAL_DAYS)

    aging.age_out(conn)

    assert _state(conn, week_old)["dismissed"] is False
    month_state = _state(conn, month_old)
    assert month_state["dismissed"] is True
    assert "yüksek sinyal" in month_state["reason"]


def test_manual_entries_never_age(client, conn):
    manual = _observe(client, f"Elle not: {uuid.uuid4().hex}", url=None)
    _backdate(conn, manual, 400)
    aging.age_out(conn)
    assert _state(conn, manual)["dismissed"] is False


def test_due_for_aging_skips_every_exempt_signal():
    now = datetime.now(timezone.utc)

    class Item:
        def __init__(self, code, score=0.1):
            self.id = code
            self.signal_score = score
            self.created_at = now - timedelta(days=365)
            self.signal_reasons = [triage.SignalReason(code=code, text="x", weight=0.1)]

    items = [Item(code) for code in aging.EXEMPT_CODES] + [Item("SOURCE_RELIABILITY")]
    groups = aging.due_for_aging(items, now=now)
    assert [i for ids in groups.values() for i in ids] == ["SOURCE_RELIABILITY"]


def test_queue_stats_report_the_rule(client):
    stats = client.get("/observations/queue?limit=1").json()["stats"]
    assert stats["aging_low_signal_days"] == aging.LOW_SIGNAL_DAYS
    assert stats["aging_high_signal_days"] == aging.HIGH_SIGNAL_DAYS
    assert stats["aging_enabled"] is True
