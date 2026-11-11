from datetime import UTC, datetime, timedelta

import pytest

from app.db import SessionLocal
from app.models import Camera, EventStatus
from app.services import camera_status
from app.services.events import create_event


@pytest.fixture
def cam(client, auth, test_video) -> dict:
    return client.post("/api/cameras", headers=auth, json={"name": "Prep 1", "source_url": test_video}).json()


def add(camera_id, event_type, when: datetime, status: EventStatus | None = None):
    with SessionLocal() as db:
        e = create_event(db, camera=db.get(Camera, camera_id), event_type=event_type, occurred_at=when)
        if status:
            e.status = status
            db.commit()


def local_today_at(hour: int, tz_offset: int) -> datetime:
    """UTC time corresponding to `hour`:30 today in a timezone `tz_offset` minutes east of UTC."""
    offset = timedelta(minutes=tz_offset)
    local_midnight = (datetime.now(UTC) + offset).replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight + timedelta(hours=hour, minutes=30) - offset


def test_empty_dashboard(client, auth):
    s = client.get("/api/dashboard/summary", headers=auth).json()
    assert s["hygiene_score"] == 100 and s["violations_today"] == 0 and s["open_alerts"] == 0
    assert len(s["by_hour"]) == 24 and sum(h["count"] for h in s["by_hour"]) == 0
    assert s["by_type"] == [] and s["recent"] == [] and s["cameras"] == []


def test_counts_score_and_breakdowns(client, auth, cam):
    tz = 330  # e.g. India, UTC+5:30: buckets must follow the local day, not UTC
    now_local_hour = (datetime.now(UTC) + timedelta(minutes=tz)).hour
    h = max(0, now_local_hour - 1)  # an hour that has already happened today

    add(cam["id"], "no_gloves", local_today_at(h, tz))  # critical, -5
    add(cam["id"], "no_gloves", local_today_at(h, tz))  # critical, -5
    add(cam["id"], "no_mask", local_today_at(h, tz), EventStatus.ACKNOWLEDGED)  # warning, -2
    add(cam["id"], "bin_open", local_today_at(0, tz), EventStatus.RESOLVED)  # info, -0.5
    add(cam["id"], "no_mask", local_today_at(h, tz), EventStatus.FALSE_ALARM)  # ignored
    add(cam["id"], "pest", local_today_at(0, tz) - timedelta(days=2))  # too old for today

    s = client.get("/api/dashboard/summary", params={"tz_offset": tz}, headers=auth).json()
    assert s["violations_today"] == 4
    assert s["hygiene_score"] == round(100 - 5 - 5 - 2 - 0.5)
    assert s["open_alerts"] == 3  # 2x no_gloves + the old pest (open alerts are not limited to today)
    assert s["critical_open"] == 3

    assert s["current_hour"] == now_local_hour
    hours = {b["hour"]: b["count"] for b in s["by_hour"]}
    if h == 0:
        assert hours[0] == 4
    else:
        assert hours[h] == 3 and hours[0] == 1
    assert [(t["event_type"], t["count"]) for t in s["by_type"]] == [("no_gloves", 2), ("bin_open", 1), ("no_mask", 1)]
    assert s["by_type"][0]["label"] == "No gloves"
    assert len(s["recent"]) == 6 and s["recent"][0]["occurred_at"] >= s["recent"][-1]["occurred_at"]


def test_yesterday_comparison_uses_same_window(client, auth, cam):
    now = datetime.now(UTC)
    add(cam["id"], "no_gloves", now - timedelta(days=1, minutes=5))  # yesterday, before this time -> counted
    add(cam["id"], "no_gloves", now - timedelta(days=1) + timedelta(minutes=5))  # yesterday, after this time -> not
    s = client.get("/api/dashboard/summary", params={"tz_offset": 0}, headers=auth).json()
    # When run just after midnight the first one may fall on the day before; the second is never counted.
    assert s["violations_yesterday"] in (0, 1)
    assert s["hygiene_score_yesterday"] == (95 if s["violations_yesterday"] else 100)


def test_camera_states(client, auth, cam, test_video):
    off = client.post("/api/cameras", headers=auth, json={"name": "Spare", "source_url": test_video, "enabled": False}).json()
    dead = client.post("/api/cameras", headers=auth, json={"name": "Dead", "source_url": test_video}).json()
    camera_status.record_online(cam["id"], 640, 360, 10)
    camera_status.record_error(dead["id"], "gone")
    s = client.get("/api/dashboard/summary", headers=auth).json()
    states = {c["name"]: c["state"] for c in s["cameras"]}
    assert states == {"Prep 1": "online", "Spare": "disabled", "Dead": "offline"}
    assert (s["cameras_enabled"], s["cameras_online"], s["cameras_offline"]) == (2, 1, 1)
    camera_status.forget(off["id"])


def test_tz_offset_validated(client, auth):
    assert client.get("/api/dashboard/summary", params={"tz_offset": 5000}, headers=auth).status_code == 422
    assert client.get("/api/dashboard/summary").status_code == 401
