"""End-to-end detection with the fake engine (see conftest): it reports one person with no mask
and every other item worn."""

import time

import cv2
import numpy as np
import pytest

from sqlalchemy import delete

from app.db import SessionLocal
from app.detection.service import detection
from app.models import DetectionConfig
from app.services.streams import streams


@pytest.fixture
def cam(client, auth, test_video) -> dict:
    return client.post("/api/cameras", headers=auth, json={"name": "Line cam", "source_url": test_video}).json()


@pytest.fixture(autouse=True)
def isolate_detection():
    """Leave no detection run behind: camera ids get reused, so a leftover run would leak into the next test."""
    yield
    with SessionLocal() as db:
        db.execute(delete(DetectionConfig))
        db.commit()
    detection.refresh_soon()
    assert wait_for(lambda: detection.status()["cameras"] == [], timeout=10) is not None
    streams.stop_all()


def wait_for(fn, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if value := fn():
            return value
        time.sleep(0.2)
    return None


def enable(client, auth, camera_id, **overrides):
    body = {"enabled": True, "min_duration_s": 1, "cooldown_s": 600, "interval_s": 0.2, **overrides}
    r = client.put(f"/api/detection/cameras/{camera_id}/config", headers=auth, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_default_config_is_off(client, auth, cam):
    cfg = client.get(f"/api/detection/cameras/{cam['id']}/config", headers=auth).json()
    assert cfg == {
        "camera_id": cam["id"], "enabled": False,
        "checks": ["no_hair_cover", "no_mask", "no_gloves", "no_apron", "handwash_skipped", "handwash_short", "table_not_cleared"],
        "min_duration_s": 5.0, "cooldown_s": 120.0, "interval_s": 0.5,
        "handwash_min_s": 20.0, "wash_valid_min": 30.0, "table_clear_min": 10.0,
    }
    assert [c["camera_id"] for c in client.get("/api/detection/configs", headers=auth).json()] == [cam["id"]]


def test_config_validation(client, auth, cam):
    url = f"/api/detection/cameras/{cam['id']}/config"
    assert client.put(url, headers=auth, json={"enabled": True, "checks": ["pest"]}).status_code == 422
    assert client.put(url, headers=auth, json={"enabled": True, "min_duration_s": 0}).status_code == 422
    assert client.put("/api/detection/cameras/9999/config", headers=auth, json={"enabled": True}).status_code == 404
    r = client.put(url, headers=auth, json={"enabled": False, "checks": ["no_mask", "no_hair_cover", "no_mask"]}).json()
    assert r["checks"] == ["no_hair_cover", "no_mask"]


def test_detection_creates_event_with_annotated_image(client, auth, cam):
    enable(client, auth, cam["id"])

    # The camera is registered a moment before the engine finishes loading, so wait for both.
    status = wait_for(lambda: (s := client.get("/api/detection/status", headers=auth).json())["cameras"] and s["engine"]["state"] == "ready" and s)
    assert status and status["engine"]["name"] == "Fake engine (testing)"

    latest = wait_for(lambda: (r := client.get(f"/api/detection/cameras/{cam['id']}/latest", headers=auth)).status_code == 200 and r.json())
    assert latest["width"] == 640 and len(latest["persons"]) == 1
    checks = latest["persons"][0]["checks"]
    assert checks["no_mask"]["state"] == "violation" and checks["no_gloves"]["state"] == "ok"

    events = wait_for(lambda: client.get("/api/events", headers=auth).json()["items"])
    assert [e["event_type"] for e in events] == ["no_mask"]  # only the violated check, only once
    e = events[0]
    assert e["camera_name"] == "Line cam" and e["has_image"] and not e["simulated"] and e["confidence"] == 0.95
    assert e["evidence"] == {"persons_in_view": 1, "persons_in_violation": 1, "min_duration_s": 1.0}
    img = client.get(f"/api/events/{e['id']}/image", headers=auth)
    frame = cv2.imdecode(np.frombuffer(img.content, np.uint8), cv2.IMREAD_COLOR)
    assert frame.shape == (360, 640, 3)

    # Cooldown: no repeat while the violation continues.
    time.sleep(2)
    assert client.get("/api/events", headers=auth).json()["total"] == 1

    obs = client.get("/api/detection/status", headers=auth).json()["cameras"][0]["observations"]
    assert obs == {"no_hair_cover": "ok", "no_mask": "violation", "no_gloves": "ok", "no_apron": "ok"}


def test_unselected_checks_do_not_alert(client, auth, cam):
    enable(client, auth, cam["id"], checks=["no_gloves", "no_apron"])
    assert wait_for(lambda: client.get(f"/api/detection/cameras/{cam['id']}/latest", headers=auth).status_code == 200)
    time.sleep(2)
    assert client.get("/api/events", headers=auth).json()["total"] == 0


def test_disabling_stops_detection_and_releases_camera(client, auth, cam):
    enable(client, auth, cam["id"])
    assert wait_for(lambda: client.get("/api/detection/status", headers=auth).json()["cameras"])
    assert wait_for(lambda: streams.get(cam["id"]) is not None)  # detection keeps the camera open

    client.put(f"/api/detection/cameras/{cam['id']}/config", headers=auth, json={"enabled": False})
    assert wait_for(lambda: client.get("/api/detection/status", headers=auth).json()["cameras"] == [])


def test_focus_mode_analyses_only_the_focused_camera(client, auth, cam, test_video, monkeypatch):
    import app.detection.service as svc

    other = client.post("/api/cameras", headers=auth, json={"name": "Other cam", "source_url": test_video}).json()
    enable(client, auth, cam["id"], interval_s=0.5)
    enable(client, auth, other["id"], interval_s=0.5)
    status_of = lambda: {c["camera_id"]: c for c in client.get("/api/detection/status", headers=auth).json()["cameras"]}  # noqa: E731
    assert wait_for(lambda: len(status_of()) == 2 and all(c["analyses_per_s"] > 0 for c in status_of().values()))

    r = client.put("/api/detection/focus", headers=auth, json={"camera_id": cam["id"]}).json()
    assert r["focus_camera_id"] == cam["id"]
    time.sleep(5.5)  # rates are measured over the last 5 s
    s = status_of()
    assert s[other["id"]]["paused"] and s[other["id"]]["analyses_per_s"] == 0
    assert not s[cam["id"]]["paused"] and s[cam["id"]]["analyses_per_s"] >= 2  # faster than its 0.5 s interval
    # The paused camera's video is let go (stops decoding once idle), the focused one kept.
    assert wait_for(lambda: streams.get(other["id"]) is None, timeout=10)
    assert streams.get(cam["id"]) is not None

    # Ends when cleared (or when not renewed: TTL); the paused camera is picked up again.
    client.put("/api/detection/focus", headers=auth, json={"camera_id": None})
    assert client.get("/api/detection/status", headers=auth).json()["focus_camera_id"] is None
    assert wait_for(lambda: streams.get(other["id"]) is not None and status_of()[other["id"]]["analyses_per_s"] > 0)
    monkeypatch.setattr(svc, "FOCUS_TTL_S", 0.2)
    detection.set_focus(cam["id"])
    time.sleep(0.4)
    assert detection.focus_camera_id() is None
    assert client.put("/api/detection/focus", headers=auth, json={"camera_id": 9999}).status_code == 404


def test_disabled_camera_is_not_analysed(client, auth, cam):
    enable(client, auth, cam["id"])
    assert wait_for(lambda: client.get("/api/detection/status", headers=auth).json()["cameras"])
    client.patch(f"/api/cameras/{cam['id']}", headers=auth, json={"enabled": False})
    assert wait_for(lambda: client.get("/api/detection/status", headers=auth).json()["cameras"] == [])
