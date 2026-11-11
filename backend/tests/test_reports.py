import csv
import io
from datetime import UTC, datetime, timedelta

import pytest

from app.db import SessionLocal
from app.models import Camera, EventStatus
from app.services.events import create_event

TZ = 330  # UTC+5:30: days must follow local time


def local_today():
    return (datetime.now(UTC) + timedelta(minutes=TZ)).date()


def at_local(day_offset: int, hour: int) -> datetime:
    """UTC time for local `hour`:15 on (today + day_offset)."""
    d = local_today() + timedelta(days=day_offset)
    return datetime(d.year, d.month, d.day, hour, 15, tzinfo=UTC) - timedelta(minutes=TZ)


@pytest.fixture
def cam(client, auth, test_video):
    return client.post("/api/cameras", headers=auth, json={"name": "Prep 1", "source_url": test_video}).json()


def add(camera_id, event_type, when, status=None, zone_id=None, note=None, resolved_after_min=None):
    with SessionLocal() as db:
        e = create_event(db, camera=db.get(Camera, camera_id), event_type=event_type, occurred_at=when, zone_id=zone_id)
        if status:
            e.status = status
        if note:
            e.note = note
        if resolved_after_min is not None:
            e.status, e.resolved_at = EventStatus.RESOLVED, when + timedelta(minutes=resolved_after_min)
        db.commit()
        return e.id


def summary(client, auth, start, end):
    return client.get("/api/reports/summary", headers=auth, params={"start": str(start), "end": str(end), "tz_offset": TZ})


def test_empty_range(client, auth):
    s = summary(client, auth, local_today() - timedelta(days=6), local_today()).json()
    assert len(s["days"]) == 7 and all(d["score"] == 100 and d["violations"] == 0 for d in s["days"])
    assert s["totals"]["violations"] == 0 and s["totals"]["false_alarm_rate"] is None and s["totals"]["worst_day"] is None
    assert s["totals"]["avg_score"] == 100


def test_daily_scores_breakdowns_and_totals(client, auth, cam):
    zone = client.post(f"/api/cameras/{cam['id']}/zones", headers=auth,
                       json={"name": "Raw prep", "zone_type": "raw_prep", "polygon": [[0, 0], [1, 0], [1, 1]]}).json()
    add(cam["id"], "no_gloves", at_local(-2, 9), zone_id=zone["id"], resolved_after_min=10)  # critical -5
    add(cam["id"], "no_gloves", at_local(-2, 9), resolved_after_min=30)  # critical -5
    add(cam["id"], "no_mask", at_local(-1, 14))  # warning -2
    add(cam["id"], "bin_open", at_local(-1, 14), EventStatus.FALSE_ALARM)  # excluded
    add(cam["id"], "no_mask", at_local(-5, 8))  # outside the 3-day range

    s = summary(client, auth, local_today() - timedelta(days=2), local_today()).json()
    days = {d["date"]: d for d in s["days"]}
    d2, d1, d0 = (str(local_today() - timedelta(days=i)) for i in (2, 1, 0))
    assert list(days) == [d2, d1, d0]
    assert days[d2] | {} == {**days[d2], "violations": 2, "critical": 2, "score": 90}
    assert days[d1]["violations"] == 1 and days[d1]["warning"] == 1 and days[d1]["false_alarms"] == 1 and days[d1]["score"] == 98
    assert days[d0]["score"] == 100

    assert [(t["event_type"], t["count"]) for t in s["by_type"]] == [("no_gloves", 2), ("no_mask", 1)]
    assert s["by_camera"] == [{"name": "Prep 1", "count": 3}]
    assert {z["name"]: z["count"] for z in s["by_zone"]} == {"Raw prep": 1, "No zone": 2}
    hours = {h["hour"]: h["count"] for h in s["by_hour"]}
    assert hours[9] == 2 and hours[14] == 1  # local hours

    t = s["totals"]
    assert t["violations"] == 3 and t["false_alarms"] == 1 and t["false_alarm_rate"] == 0.25
    assert t["resolved"] == 2 and t["avg_resolution_min"] == 20.0 and t["open"] == 1
    assert t["worst_day"] == d2 and t["avg_score"] == round((90 + 98 + 100) / 3, 1)


def test_range_validation_and_future_clipping(client, auth):
    today = local_today()
    assert summary(client, auth, today, today - timedelta(days=1)).status_code == 422
    assert summary(client, auth, today - timedelta(days=400), today).status_code == 422
    s = summary(client, auth, today - timedelta(days=1), today + timedelta(days=5)).json()
    assert s["end"] == str(today) and len(s["days"]) == 2  # no future days
    assert client.get("/api/reports/summary", params={"start": str(today), "end": str(today)}).status_code == 401


def test_csv_export(client, auth, cam):
    add(cam["id"], "no_gloves", at_local(-1, 10), note="Reminded chef — గ్లౌవ్స్")
    add(cam["id"], "no_mask", at_local(0, 0), EventStatus.FALSE_ALARM, note='=HYPERLINK("http://evil")')
    r = client.get("/api/reports/export.csv", headers=auth,
                   params={"start": str(local_today() - timedelta(days=1)), "end": str(local_today()), "tz_offset": TZ})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'filename="vigilsiddhi-events-' in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    assert text.startswith("﻿")  # BOM so Excel reads UTF-8
    rows = list(csv.DictReader(io.StringIO(text.lstrip("﻿"))))
    assert [row["type"] for row in rows] == ["No gloves", "No mask"]
    assert rows[0]["occurred_at"].endswith("10:15:00")  # local time
    assert rows[0]["camera"] == "Prep 1" and rows[0]["zone"] == "No zone" and rows[0]["severity"] == "critical"
    assert rows[0]["note"] == "Reminded chef — గ్లౌవ్స్"
    assert rows[1]["status"] == "false_alarm"
    assert rows[1]["note"].startswith("'=")  # formula neutralised
