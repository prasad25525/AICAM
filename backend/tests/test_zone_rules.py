"""Zone rules and the person tracker, driven with made-up timelines (no models)."""

import time

import pytest

from app.detection.tracking import MAX_AGE_S, Tracker
from app.detection.zone_rules import ITEMS_GONE_S, PREP_DWELL_S, SINK_MIN_VISIT_S, RuleParams, TableObject, ZoneRuleEngine
from app.detection.zones import ZoneShape

W, H = 1000, 1000
# Floor plan (fractions): sink on the left, raw prep on the right, a dining table top-middle.
SINK = ZoneShape(1, "Hand sink", ((0.0, 0.5), (0.3, 0.5), (0.3, 1.0), (0.0, 1.0)), "sink")
PREP = ZoneShape(2, "Raw prep", ((0.7, 0.5), (1.0, 0.5), (1.0, 1.0), (0.7, 1.0)), "raw_prep")
TABLE = ZoneShape(3, "Table 4", ((0.35, 0.0), (0.65, 0.0), (0.65, 0.4), (0.35, 0.4)), "dining_table")
ZONES = [SINK, PREP, TABLE]
ALL_RULES = {"handwash_skipped", "handwash_short", "table_not_cleared"}


def box_at(x: float) -> tuple[int, int, int, int]:
    """A person standing with their feet at horizontal position x (fraction), bottom of the frame."""
    cx = int(x * W)
    return (cx - 60, 450, cx + 60, 950)


MIDDLE, AT_SINK, AT_PREP = 0.5, 0.15, 0.85


WALK_SPEED = 0.1  # fraction of the frame per 1s tick: people walk, they don't teleport


class Scene:
    """Feeds positions over time into a tracker + rule engine, collecting events."""

    def __init__(self, params=None, rules=ALL_RULES):
        self.tracker, self.rules, self.now, self.events = Tracker(), ZoneRuleEngine(), 0.0, []
        self.params, self.rule_set = params or RuleParams(handwash_min_s=20, wash_valid_min=30, table_clear_min=1), rules
        self.x: float | None = None  # current position of the (single) walking person

    def _tick(self, boxes, objects):
        self.now += 1
        tracks = self.tracker.update(boxes, self.now)
        self.events += self.rules.update(self.now, tracks, ZONES, W, H, self.params, self.rule_set, list(objects))

    def step(self, xs: list[float], seconds: float = 1.0, objects=(), people_boxes=None):
        """Advance time in 1s ticks with people at xs (or explicit boxes). A single person first
        walks from where they were, WALK_SPEED per tick, so the tracker can follow them."""
        if people_boxes is None and len(xs) == 1 and self.x is not None:
            while abs(xs[0] - self.x) > WALK_SPEED:
                self.x += WALK_SPEED if xs[0] > self.x else -WALK_SPEED
                self._tick([box_at(self.x)], objects)
        if len(xs) == 1:
            self.x = xs[0]
        for _ in range(int(seconds)):
            self._tick(people_boxes if people_boxes is not None else [box_at(x) for x in xs], objects)
        return self

    def types(self):
        return [e.event_type for e in self.events]


# --- tracker ---------------------------------------------------------------------


def test_tracker_keeps_ids_while_people_move():
    t = Tracker()
    a = t.update([box_at(0.2), box_at(0.8)], 1)
    b = t.update([box_at(0.8) , box_at(0.23)], 2)  # order swapped, first person moved a bit
    assert [x.id for x in a] == [1, 2]
    assert [x.id for x in b] == [2, 1]


def test_tracker_forgets_people_after_max_age():
    t = Tracker()
    first = t.update([box_at(0.5)], 0)[0].id
    t.update([], 1)
    assert t.update([box_at(0.5)], 2)[0].id == first  # brief gap: same person
    later = t.update([box_at(0.5)], 2 + MAX_AGE_S + 1)[0].id
    assert later != first  # gone too long: treated as someone new


# --- hand washing ---------------------------------------------------------------------


def test_proper_wash_then_prep_is_fine():
    s = Scene().step([MIDDLE], 2).step([AT_SINK], 25).step([MIDDLE], 2).step([AT_PREP], 20)
    assert s.types() == []


def test_short_wash_alerts_once_with_duration():
    s = Scene().step([MIDDLE], 2).step([AT_SINK], 8).step([MIDDLE], 2)
    assert s.types() == ["handwash_short"]
    ev = s.events[0]
    # 8s standing at the sink plus a little of the walk in and out, which also crosses the sink zone.
    assert ev.zone.name == "Hand sink" and 7 <= ev.details["wash_seconds"] <= 12
    assert "needs 20s" in ev.message and ev.details["handwash_min_s"] == 20


def test_walking_past_the_sink_is_not_a_wash():
    # Brush past the sink zone's edge (x=0.25 is just inside it) without stopping.
    s = Scene().step([MIDDLE], 2).step([0.25], 0).step([MIDDLE], 2)
    assert s.types() == []
    assert SINK_MIN_VISIT_S > 1


def test_skipping_the_sink_alerts_after_dwell():
    s = Scene().step([MIDDLE], 3).step([AT_PREP], 1)
    assert s.types() == []  # just arrived: could be passing through
    s.step([AT_PREP], int(PREP_DWELL_S) + 1)
    assert s.types() == ["handwash_skipped"]
    assert s.events[0].zone.name == "Raw prep" and s.events[0].box is not None
    s.step([AT_PREP], 30)
    assert s.types() == ["handwash_skipped"]  # once per visit, not repeated


def test_short_wash_still_counts_as_a_visit_for_skipping():
    # A short wash is its own alert; the person did visit the sink, so no "skipped" on top.
    s = Scene().step([MIDDLE], 2).step([AT_SINK], 6).step([MIDDLE], 1).step([AT_PREP], 10)
    assert s.types() == ["handwash_short"]


def test_old_wash_expires():
    s = Scene(RuleParams(handwash_min_s=5, wash_valid_min=1, table_clear_min=10))
    s.step([MIDDLE], 2).step([AT_SINK], 6).step([MIDDLE], 70).step([AT_PREP], 8)
    assert s.types() == ["handwash_skipped"]  # washed 70+ seconds ago, window is 1 minute


def test_person_first_seen_in_prep_is_not_judged():
    s = Scene().step([AT_PREP], 30)
    assert s.types() == []


def test_leaving_and_reentering_prep_is_a_new_visit():
    s = Scene().step([MIDDLE], 2).step([AT_PREP], 7).step([MIDDLE], 2).step([AT_PREP], 7)
    assert s.types() == ["handwash_skipped", "handwash_skipped"]


def test_rules_can_be_switched_off():
    s = Scene(rules={"table_not_cleared"}).step([MIDDLE], 2).step([AT_SINK], 6).step([MIDDLE], 2).step([AT_PREP], 10)
    assert s.types() == []


# --- tables ----------------------------------------------------------------------------------

CUP = TableObject("cup", (480, 150, 520, 190))  # on Table 4
AT_TABLE = [(440, 50, 560, 380)]  # a diner sitting at Table 4


def test_table_left_with_items_alerts_after_timeout():
    s = Scene()  # table_clear_min = 1
    s.step([], 30, objects=[CUP], people_boxes=AT_TABLE)  # guests eating
    assert s.types() == []
    s.step([], 55, objects=[CUP], people_boxes=[])  # guests left, cup still there
    assert s.types() == []
    s.step([], 10, objects=[CUP], people_boxes=[])
    assert s.types() == ["table_not_cleared"]
    ev = s.events[0]
    assert ev.zone.name == "Table 4" and ev.details["items"] == ["cup"] and "(cup left)" in ev.message
    s.step([], 120, objects=[CUP], people_boxes=[])
    assert s.types() == ["table_not_cleared"]  # once per episode


def test_table_view_shows_the_timer():
    s = Scene()  # table_clear_min = 1
    s.step([], 3, objects=[CUP], people_boxes=AT_TABLE)
    (t,) = s.rules.table_view
    assert t["name"] == "Table 4" and t["state"] == "occupied" and t["items"] == ["cup"] and t["limit_s"] == 60
    assert t["anchor"] == [0.5, 0.0]  # top-centre of the zone
    s.step([], 20, objects=[CUP], people_boxes=[])
    (t,) = s.rules.table_view
    assert t["state"] == "waiting" and 18 <= t["waited_s"] <= 20
    s.step([], 45, objects=[CUP], people_boxes=[])
    assert s.rules.table_view[0]["state"] == "not_cleared"
    assert Scene().step([], 2, objects=[], people_boxes=[]).rules.table_view[0]["state"] == "clear"


def test_cleared_table_does_not_alert():
    s = Scene().step([], 30, objects=[], people_boxes=[])
    assert s.types() == []


def test_staff_arriving_resets_the_timer():
    s = Scene().step([], 50, objects=[CUP], people_boxes=[])
    s.step([], 5, objects=[CUP], people_boxes=AT_TABLE)  # waiter comes to clear
    s.step([], 50, objects=[CUP], people_boxes=[])  # (cup still seen) timer restarted at the waiter's exit
    assert s.types() == []


def test_brief_detection_gaps_dont_reset_the_timer():
    s = Scene()
    for _ in range(35):  # cup flickers in and out of detection
        s.step([], 1, objects=[CUP], people_boxes=[])
        s.step([], 1, objects=[], people_boxes=[])
    assert s.types() == ["table_not_cleared"]


def test_items_gone_long_enough_counts_as_cleared():
    s = Scene().step([], 40, objects=[CUP], people_boxes=[])
    s.step([], int(ITEMS_GONE_S) + 5, objects=[], people_boxes=[])
    s.step([], 40, objects=[], people_boxes=[])
    assert s.types() == []


# --- through the running service (fake engine) -------------------------------------------------


@pytest.fixture
def cam(client, auth, test_video):
    return client.post("/api/cameras", headers=auth, json={"name": "Dining cam", "source_url": test_video}).json()


def test_table_rule_end_to_end(client, auth, cam, monkeypatch):
    """Fake engine: its person stands at the bottom-centre; a cup sits on a table zone away from them."""
    from app.config import settings
    from app.detection.service import detection
    from app.services.streams import streams

    monkeypatch.setattr(detection.engine, "objects", [["cup", 0.1, 0.1, 0.15, 0.15]], raising=False) if detection.engine else None
    monkeypatch.setattr(settings, "fake_objects", [["cup", 0.1, 0.1, 0.15, 0.15]])
    client.post(f"/api/cameras/{cam['id']}/zones", headers=auth,
                json={"name": "Table 1", "zone_type": "dining_table", "polygon": [[0, 0], [0.3, 0], [0.3, 0.3], [0, 0.3]]})
    client.put(f"/api/detection/cameras/{cam['id']}/config", headers=auth, json={
        "enabled": True, "checks": ["table_not_cleared"], "interval_s": 0.2, "table_clear_min": 0.1,
    })
    try:
        deadline = time.monotonic() + 30
        items = []
        while not items and time.monotonic() < deadline:
            items = client.get("/api/events", headers=auth).json()["items"]
            time.sleep(0.3)
        assert [e["event_type"] for e in items] == ["table_not_cleared"]
        assert items[0]["zone_name"] == "Table 1" and "(cup left)" in items[0]["message"]
        assert items[0]["has_image"]
        # Measured facts for the UI's visual summary; internal details (boxes, engine) stay hidden.
        ev = items[0]["evidence"]
        assert ev["items"] == ["cup"] and ev["table_clear_min"] == 0.1 and ev["waited_min"] >= 0.1
        assert "engine" not in ev

        # The live view gets the tableware boxes and the table's state, to draw them.
        latest = client.get(f"/api/detection/cameras/{cam['id']}/latest", headers=auth).json()
        assert [o["label"] for o in latest["objects"]] == ["cup"]
        (table,) = latest["tables"]
        assert table["name"] == "Table 1" and table["state"] == "not_cleared" and table["items"] == ["cup"]
    finally:
        client.put(f"/api/detection/cameras/{cam['id']}/config", headers=auth, json={"enabled": False})
        detection.refresh_soon()
        deadline = time.monotonic() + 10
        while detection.status()["cameras"] and time.monotonic() < deadline:
            time.sleep(0.1)
        streams.stop_all()
