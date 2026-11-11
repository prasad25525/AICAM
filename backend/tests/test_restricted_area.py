"""Cement plant: restricted / danger area entry."""

import pytest

from app.config import settings
from app.db import SessionLocal
from app.detection.tracking import Tracker
from app.detection.zone_rules import RuleParams, ZoneRuleEngine
from app.detection.zones import ZoneShape
from app.services.app_settings import get_settings
from tests.test_detection_api import isolate_detection, wait_for  # noqa: F401 (isolate_detection is an autouse fixture)

W, H = 1000, 1000
DANGER = ZoneShape(1, "Crusher area", ((0.6, 0.5), (1.0, 0.5), (1.0, 1.0), (0.6, 1.0)), "restricted")
OTHER = ZoneShape(2, "Walkway", ((0.0, 0.5), (0.4, 0.5), (0.4, 1.0), (0.0, 1.0)), "walkway")
PARAMS = RuleParams(restricted_min_s=2)


def box_at(x: float) -> tuple[int, int, int, int]:
    """A person with their feet at horizontal position x (fraction), bottom of the frame."""
    cx = int(x * W)
    return (cx - 60, 450, cx + 60, 950)


class Walk:
    def __init__(self, rules=frozenset({"restricted_area"})):
        self.tracker, self.engine, self.now, self.events, self.x, self.rules = Tracker(), ZoneRuleEngine(), 0.0, [], 0.2, set(rules)

    def to(self, x: float, then_stay_s: int = 0):
        """Walk (0.1 per second, so the tracker keeps the id) to x, then stay there."""
        while abs(x - self.x) > 1e-9:
            self.x = min(x, self.x + 0.1) if x > self.x else max(x, self.x - 0.1)
            self._tick()
        for _ in range(then_stay_s):
            self._tick()
        return self

    def _tick(self):
        self.now += 1
        tracks = self.tracker.update([box_at(self.x)], self.now)
        self.events += self.engine.update(self.now, tracks, [DANGER, OTHER], W, H, PARAMS, self.rules)


def test_entering_and_staying_alerts_once_per_visit():
    w = Walk().to(0.3, 2).to(0.7)  # first second just inside the line
    assert w.events == [] and w.engine.intrusions[0]["zone"] == "Crusher area"  # inside, but not long enough yet
    w.to(0.8, 10)
    (ev,) = w.events
    assert ev.event_type == "restricted_area" and ev.zone.name == "Crusher area" and ev.box is not None
    assert 2 <= ev.details["seconds_inside"] <= 3 and "Crusher area" in ev.message
    assert w.engine.intrusions[0]["seconds"] >= 10  # the live view keeps counting

    w.to(0.3, 2)
    assert w.engine.intrusions == []  # left
    w.to(0.8, 3)
    assert [e.event_type for e in w.events] == ["restricted_area", "restricted_area"]  # a new visit


def test_a_brief_step_in_is_not_an_alert():
    w = Walk().to(0.5).to(0.65).to(0.5, 3)  # one second just inside the line
    assert w.events == []


def test_only_the_feet_count():
    """Walking just in front of a danger area: the body is over the line, the feet are not."""
    upper = ZoneShape(3, "Machine base", ((0.0, 0.3), (1.0, 0.3), (1.0, 0.8), (0.0, 0.8)), "restricted")
    engine, tracker = ZoneRuleEngine(), Tracker()
    for now in range(1, 6):
        tracks = tracker.update([box_at(0.5)], now)  # feet at y=0.95, box centre at y=0.7 (inside)
        assert engine.update(now, tracks, [upper], W, H, PARAMS, {"restricted_area"}) == []
        assert engine.intrusions == []


def test_other_zones_and_switched_off_rule():
    assert Walk().to(0.1, 10).events == []  # a walkway is not restricted
    assert Walk(rules=set()).to(0.8, 10).events == []


@pytest.fixture
def cement_camera(client, auth, test_video):
    client.put("/api/industry", headers=auth, json={"industry": "cement"})
    yield client.post("/api/cameras", headers=auth, json={"name": "Crusher cam", "source_url": test_video}).json()
    with SessionLocal() as db:
        get_settings(db).active_industry = "restaurant"
        db.commit()


def test_restricted_area_end_to_end(client, auth, cement_camera, monkeypatch):
    """The test engine always sees one person standing at the bottom centre: put a danger zone there."""
    monkeypatch.setattr(settings, "fake_person_box", [0.4, 0.3, 0.6, 0.95])
    cid = cement_camera["id"]
    zone = {"name": "Crusher area", "zone_type": "restricted", "polygon": [[0.3, 0.6], [0.7, 0.6], [0.7, 1.0], [0.3, 1.0]]}
    assert client.post(f"/api/cameras/{cid}/zones", headers=auth, json=zone).status_code == 201
    r = client.put(f"/api/detection/cameras/{cid}/config", headers=auth,
                   json={"enabled": True, "checks": ["restricted_area"], "min_duration_s": 1, "interval_s": 0.2})
    assert r.status_code == 200, r.text

    events = wait_for(lambda: client.get("/api/events", headers=auth).json()["items"], timeout=20)
    assert events and [e["event_type"] for e in events] == ["restricted_area"]
    e = events[0]
    assert e["zone_name"] == "Crusher area" and e["severity"] == "critical" and e["has_image"]
    assert e["evidence"]["seconds_inside"] >= 1

    latest = client.get(f"/api/detection/cameras/{cid}/latest", headers=auth).json()
    (intrusion,) = latest["intrusions"]
    assert intrusion["zone"] == "Crusher area" and intrusion["seconds"] >= 1
