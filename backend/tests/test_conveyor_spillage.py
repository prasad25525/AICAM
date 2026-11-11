"""Cement plant: conveyor spillage — an image check on the floor zone under the belt."""

import pytest

from app.config import settings
from app.db import SessionLocal
from app.detection.zone_rules import VISUAL_REARM_S, RuleParams, ZoneRuleEngine
from app.detection.zones import ZoneShape
from app.services.app_settings import get_settings
from tests.test_detection_api import isolate_detection, wait_for  # noqa: F401 (isolate_detection is an autouse fixture)

FLOOR = ZoneShape(7, "Floor under belt 1", ((0.3, 0.68), (0.95, 0.68), (0.95, 1.0), (0.3, 1.0)), "conveyor_floor")
RULES = {"conveyor_spillage"}
PARAMS = RuleParams(visual_min_s=3)


class Floor:
    def __init__(self):
        self.engine, self.now, self.events = ZoneRuleEngine(), 0.0, []

    def looks(self, p: float, seconds: int = 1):
        for _ in range(seconds):
            self.now += 1
            self.events += self.engine.update(self.now, [], [FLOOR], 1000, 1000, PARAMS, RULES, zone_probs={("conveyor_spillage", FLOOR.id): p})
        return self

    @property
    def state(self):
        (z,) = self.engine.zone_view
        return z


def test_spill_must_be_seen_for_a_while_then_alerts_once():
    f = Floor().looks(0.05, 3)
    assert f.state["state"] == "clear" and f.events == []
    f.looks(0.98, 2)
    assert f.events == [] and f.state["state"] == "problem" and f.state["seconds"] == 1  # seen, not long enough yet
    f.looks(0.98, 2)
    (ev,) = f.events
    assert ev.event_type == "conveyor_spillage" and ev.message == "Conveyor spillage at Floor under belt 1"
    assert ev.zone == FLOOR and ev.details == {"seconds_seen": 3.0, "p": 0.98}
    f.looks(0.98, 30)
    assert len(f.events) == 1  # once per spill


def test_a_doubtful_frame_does_not_restart_the_timer():
    f = Floor().looks(0.98, 2).looks(0.45).looks(0.98, 1)
    assert [e.event_type for e in f.events] == ["conveyor_spillage"]


def test_cleaned_up_then_spilled_again_is_a_new_alert():
    f = Floor().looks(0.98, 5).looks(0.05, 3).looks(0.98, 5)
    assert len(f.events) == 1  # clean only briefly (detections flicker): same episode
    f.looks(0.05, int(VISUAL_REARM_S) + 1).looks(0.98, 5)
    assert len(f.events) == 2


def test_rule_off_or_zone_removed():
    engine = ZoneRuleEngine()
    assert engine.update(1, [], [FLOOR], 1000, 1000, PARAMS, set(), zone_probs={("conveyor_spillage", 7): 0.99}) == []
    assert engine.zone_view == []
    assert engine.update(2, [], [], 1000, 1000, PARAMS, RULES, zone_probs={("conveyor_spillage", 7): 0.99}) == []


@pytest.fixture
def cement_camera(client, auth, test_video):
    client.put("/api/industry", headers=auth, json={"industry": "cement"})
    yield client.post("/api/cameras", headers=auth, json={"name": "Belt cam", "source_url": test_video}).json()
    with SessionLocal() as db:
        get_settings(db).active_industry = "restaurant"
        db.commit()


def test_spillage_end_to_end(client, auth, cement_camera, monkeypatch):
    cid = cement_camera["id"]
    zone = {"name": "Floor under belt 1", "zone_type": "conveyor_floor", "polygon": [[0.3, 0.68], [0.95, 0.68], [0.95, 1], [0.3, 1]]}
    assert client.post(f"/api/cameras/{cid}/zones", headers=auth, json=zone).status_code == 201
    client.put(f"/api/detection/cameras/{cid}/config", headers=auth,
               json={"enabled": True, "checks": ["conveyor_spillage"], "min_duration_s": 1, "interval_s": 0.2})

    # A clean floor: watched, never an alert.
    latest = lambda: client.get(f"/api/detection/cameras/{cid}/latest", headers=auth)  # noqa: E731
    assert wait_for(lambda: latest().status_code == 200 and latest().json()["zone_states"], timeout=20)
    assert latest().json()["zone_states"][0]["state"] == "clear"
    wait_for(lambda: False, timeout=2)
    assert client.get("/api/events", headers=auth).json()["total"] == 0

    monkeypatch.setattr(settings, "fake_zone_hits", ["conveyor_spillage"])  # material starts falling
    events = wait_for(lambda: client.get("/api/events", headers=auth).json()["items"], timeout=20)
    assert [e["event_type"] for e in events] == ["conveyor_spillage"]
    e = events[0]
    assert e["zone_name"] == "Floor under belt 1" and e["severity"] == "warning" and e["confidence"] == 0.95 and e["has_image"]
    assert e["evidence"]["seconds_seen"] >= 1
    (state,) = latest().json()["zone_states"]
    assert state["state"] == "problem" and state["label"] == "Conveyor spillage"
