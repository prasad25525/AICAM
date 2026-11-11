import time

import pytest

from app.db import SessionLocal
from app.detection.zones import ZoneShape, point_in_polygon, zone_for_person
from app.models import Camera
from app.services.events import create_event
from app.services.streams import streams

SQUARE = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
BOTTOM_HALF = [[0, 0.5], [1, 0.5], [1, 1], [0, 1]]


@pytest.fixture
def cam(client, auth, test_video) -> dict:
    return client.post("/api/cameras", headers=auth, json={"name": "Prep 1", "source_url": test_video}).json()


def add_zone(client, auth, camera_id, name="Sink", zone_type="sink", polygon=SQUARE):
    return client.post(f"/api/cameras/{camera_id}/zones", headers=auth, json={"name": name, "zone_type": zone_type, "polygon": polygon})


# --- API ---------------------------------------------------------------------


def test_zone_crud(client, auth, cam):
    r = add_zone(client, auth, cam["id"])
    assert r.status_code == 201
    z = r.json()
    assert z["name"] == "Sink" and z["zone_type"] == "sink" and z["polygon"] == SQUARE

    assert [x["id"] for x in client.get(f"/api/cameras/{cam['id']}/zones", headers=auth).json()] == [z["id"]]
    assert [x["id"] for x in client.get("/api/zones", headers=auth).json()] == [z["id"]]

    moved = [[0.2, 0.2], [0.6, 0.2], [0.6, 0.6]]
    r = client.patch(f"/api/zones/{z['id']}", headers=auth, json={"name": "Hand sink", "polygon": moved}).json()
    assert r["name"] == "Hand sink" and r["polygon"] == moved and r["zone_type"] == "sink"

    assert client.delete(f"/api/zones/{z['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/cameras/{cam['id']}/zones", headers=auth).json() == []
    assert client.delete(f"/api/zones/{z['id']}", headers=auth).status_code == 404


@pytest.mark.parametrize(
    "polygon, message",
    [
        ([[0.1, 0.1], [0.5, 0.1]], "between 3 and 50 points"),
        ([[0.1, 0.1], [1.5, 0.1], [0.5, 0.5]], "between 0 and 1"),
        ([[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]], "too small or its points are in a line"),
        ([[0.1, 0.1], [0.5, 0.1, 0.3], [0.5, 0.5]], "[x, y]"),
    ],
)
def test_polygon_validation(client, auth, cam, polygon, message):
    r = add_zone(client, auth, cam["id"], polygon=polygon)
    assert r.status_code == 422 and message in r.text


def test_names_unique_per_camera(client, auth, cam, test_video):
    add_zone(client, auth, cam["id"], name="Sink")
    assert add_zone(client, auth, cam["id"], name="sink").status_code == 409
    other = client.post("/api/cameras", headers=auth, json={"name": "Prep 2", "source_url": test_video}).json()
    assert add_zone(client, auth, other["id"], name="Sink").status_code == 201  # fine on another camera


def test_bad_type_and_missing_camera(client, auth, cam):
    assert add_zone(client, auth, cam["id"], zone_type="bathroom").status_code == 422
    assert add_zone(client, auth, 9999).status_code == 404
    assert client.get("/api/cameras/9999/zones", headers=auth).status_code == 404


def test_deleting_camera_removes_its_zones(client, auth, cam):
    add_zone(client, auth, cam["id"])
    client.delete(f"/api/cameras/{cam['id']}", headers=auth)
    assert client.get("/api/zones", headers=auth).json() == []


def test_event_keeps_zone_name_after_zone_deleted(client, auth, cam):
    zone = add_zone(client, auth, cam["id"], name="Raw prep", zone_type="raw_prep").json()
    with SessionLocal() as db:
        event_id = create_event(db, camera=db.get(Camera, cam["id"]), event_type="no_gloves", zone_id=zone["id"]).id
    assert client.get(f"/api/events/{event_id}", headers=auth).json()["zone_name"] == "Raw prep"
    client.delete(f"/api/zones/{zone['id']}", headers=auth)
    e = client.get(f"/api/events/{event_id}", headers=auth).json()
    assert e["zone_id"] is None and e["zone_name"] == "Raw prep"


def test_zone_from_another_camera_is_ignored(client, auth, cam, test_video):
    other = client.post("/api/cameras", headers=auth, json={"name": "Prep 2", "source_url": test_video}).json()
    foreign = add_zone(client, auth, other["id"]).json()
    with SessionLocal() as db:
        e = create_event(db, camera=db.get(Camera, cam["id"]), event_type="no_mask", zone_id=foreign["id"])
        assert e.zone_id is None


# --- geometry ----------------------------------------------------------------


def test_point_in_polygon():
    assert point_in_polygon(0.3, 0.3, SQUARE)
    assert not point_in_polygon(0.7, 0.3, SQUARE)
    triangle = [[0, 0], [1, 0], [0, 1]]
    assert point_in_polygon(0.2, 0.2, triangle) and not point_in_polygon(0.8, 0.8, triangle)


def test_feet_cut_off_by_frame_bottom_still_count():
    # Person partly out of view: box reaches the bottom edge exactly (y = 1.0).
    sink = ZoneShape(1, "Sink", ((0.2, 0.6), (0.45, 0.6), (0.45, 1.0), (0.2, 1.0)))
    assert zone_for_person((350, 300, 490, 480), 1280, 480, [sink]).name == "Sink"


def test_duplicate_person_boxes_are_merged():
    import numpy as np

    from app.detection.engine import dedupe_people

    full = [100, 50, 300, 470]
    upper = [110, 50, 290, 250]  # same person, upper body only
    other = [600, 60, 800, 470]
    kept = dedupe_people(np.array([upper, full, other], float))
    assert sorted(kept) == [1, 2]  # the partial box is dropped, the other person kept


def test_zone_for_person_feet_then_centre_and_smallest_wins():
    floor = ZoneShape(1, "Kitchen floor", ((0, 0), (1, 0), (1, 1), (0, 1)))
    sink = ZoneShape(2, "Sink", ((0.4, 0.6), (0.6, 0.6), (0.6, 1), (0.4, 1)))
    upper = ZoneShape(3, "Counter", ((0, 0), (1, 0), (1, 0.5), (0, 0.5)))
    person = (270, 200, 370, 470)  # feet at (0.5, 0.98) in a 640x480 frame
    assert zone_for_person(person, 640, 480, [floor, sink]).name == "Sink"  # nested: smallest
    assert zone_for_person(person, 640, 480, [floor]).name == "Kitchen floor"
    # Feet outside every zone: fall back to the box centre (0.5, 0.70) — still outside "Counter".
    assert zone_for_person(person, 640, 480, [upper]) is None
    waist_up = (270, 20, 370, 300)  # centre (0.5, 0.33) is inside "Counter"
    assert zone_for_person(waist_up, 640, 480, [upper]).name == "Counter"


# --- detection tags events with the zone ------------------------------------------


def test_detected_event_is_tagged_with_zone(client, auth, cam):
    # The fake engine's person stands at the bottom-centre of the frame.
    add_zone(client, auth, cam["id"], name="Top shelf", zone_type="storage", polygon=[[0, 0], [1, 0], [1, 0.3], [0, 0.3]])
    add_zone(client, auth, cam["id"], name="Prep counter", zone_type="raw_prep", polygon=BOTTOM_HALF)
    client.put(f"/api/detection/cameras/{cam['id']}/config", headers=auth,
               json={"enabled": True, "checks": ["no_mask"], "min_duration_s": 1, "interval_s": 0.2})
    try:
        deadline = time.monotonic() + 15
        events = []
        while not events and time.monotonic() < deadline:
            events = client.get("/api/events", headers=auth).json()["items"]
            time.sleep(0.2)
        assert events and events[0]["event_type"] == "no_mask"
        assert events[0]["zone_name"] == "Prep counter"
    finally:
        client.put(f"/api/detection/cameras/{cam['id']}/config", headers=auth, json={"enabled": False})
        from app.detection.service import detection

        detection.refresh_soon()
        deadline = time.monotonic() + 10
        while detection.status()["cameras"] and time.monotonic() < deadline:
            time.sleep(0.1)
        streams.stop_all()
