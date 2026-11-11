"""Cement plant: counting bags that pass a line on the packing belt."""

import cv2
import numpy as np
import pytest

from app.db import SessionLocal
from app.detection.counting import LineCounter
from app.detection.zones import ZoneShape
from app.services.app_settings import get_settings
from tests.test_detection_api import isolate_detection, wait_for  # noqa: F401 (isolate_detection is an autouse fixture)

W, H = 400, 200
BELT = ZoneShape(1, "Loader belt", ((0.0, 0.3), (1.0, 0.3), (1.0, 0.7), (0.0, 0.7)), "packing_line")  # line at x = 0.75


def conveyor(bag_starts, bag_len=60, seam=0, steps=200, speed=4):
    """Frames of light bags (white boxes) moving right over a dark belt. `seam` = dark gap between
    touching bags in pixels (0 = gap as given by the start positions)."""
    for step in range(steps):
        frame = np.full((H, W, 3), 40, np.uint8)
        for start in bag_starts:
            x0 = start + step * speed
            cv2.rectangle(frame, (x0 + seam, 70), (x0 + bag_len - 1, 130), (235, 235, 235), -1)
        yield frame


def count(frames) -> int:
    c = LineCounter(BELT)
    for i, f in enumerate(frames):
        c.feed(f, i / 12)
    return c.total


def test_counts_separate_bags():
    assert count(conveyor([-60, -160, -260, -360, -460])) == 5
    assert LineCounter(BELT).line == (0.75, 0.3, 0.7)


def test_touching_bags_with_a_seam_still_count_separately():
    # Bags end to end (60 px apart, 60 px long), only an 8-pixel darker seam between them; the belt
    # moves 4 px a frame, so the seam shows on the line for a frame or two.
    assert count(conveyor([-60, -120, -180, -240], seam=8)) == 4


def test_a_seam_narrower_than_one_frame_of_movement_is_missed():
    """The known limit (see counting.py): a seam the belt jumps over between frames can't be seen."""
    assert count(conveyor([-60, -120, -180, -240], seam=2, speed=8)) < 4


def test_a_flickering_edge_is_not_counted_twice():
    c = LineCounter(BELT)
    frames = [np.full((H, W, 3), 40, np.uint8) for _ in range(12)]
    for i, f in enumerate(frames):
        cv2.rectangle(f, (295, 70), (305, 70 + (90 if i % 2 else 70)), (235, 235, 235), -1)  # wobbles around the threshold
        c.feed(f, i / 12)
    assert c.total == 1


def test_nothing_on_the_belt_counts_nothing():
    assert count(np.full((H, W, 3), 40, np.uint8) for _ in range(50)) == 0


def test_saving_takes_each_count_once():
    c = LineCounter(BELT)
    for i, f in enumerate(conveyor([-60, -160])):
        c.feed(f, i / 12)
    assert c.take_unsaved() == 2 and c.take_unsaved() == 0 and c.total == 2 and c.per_minute(200 / 12) == 2


@pytest.fixture
def belt_video(tmp_path):
    """A 4-second, 24 fps video: 4 bags crossing a dark belt from left to right."""
    path = tmp_path / "belt.mp4"
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 24, (W, H))
    for f in conveyor([-60, -150, -240, -330], steps=96, speed=5):
        out.write(f)
    out.release()
    return str(path)


@pytest.fixture
def cement_auth(client, auth):
    client.put("/api/industry", headers=auth, json={"industry": "cement"})
    yield auth
    with SessionLocal() as db:
        get_settings(db).active_industry = "restaurant"
        db.commit()


def test_bag_counting_end_to_end(client, cement_auth, belt_video):
    auth = cement_auth
    cam = client.post("/api/cameras", headers=auth, json={"name": "Packer 1", "source_url": belt_video, "area": "packing"}).json()
    zone = {"name": "Loader belt", "zone_type": "packing_line", "polygon": [[0, 0.3], [1, 0.3], [1, 0.7], [0, 0.7]]}
    assert client.post(f"/api/cameras/{cam['id']}/zones", headers=auth, json=zone).status_code == 201
    r = client.put(f"/api/detection/cameras/{cam['id']}/config", headers=auth, json={"enabled": True, "checks": ["bag_count"], "interval_s": 1})
    assert r.status_code == 200, r.text

    # The video loops: 4 bags per 4-second loop, saved to the database and summed for today.
    today = lambda: client.get("/api/counts/today", headers=auth, params={"tz_offset": 0}).json()  # noqa: E731
    assert wait_for(lambda: today()["today"] >= 4, timeout=30)
    t = today()
    assert t["kind"] == "bags" and [c["camera_name"] for c in t["by_camera"]] == ["Packer 1"] and sum(t["by_hour"]) == t["today"]

    latest = wait_for(lambda: (r := client.get(f"/api/detection/cameras/{cam['id']}/latest", headers=auth)).status_code == 200 and r.json())
    (counter,) = latest["counters"]
    assert counter["name"] == "Loader belt" and counter["kind"] == "bags" and counter["total"] >= 4 and counter["line"] == [0.75, 0.3, 0.7]
    assert client.get("/api/events", headers=auth).json()["total"] == 0  # counting never raises alerts
