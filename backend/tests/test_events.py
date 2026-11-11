from datetime import UTC, datetime, timedelta

import cv2
import numpy as np
import pytest

from app.config import settings
from app.db import SessionLocal
from app.models import Camera
from app.services.events import create_event


@pytest.fixture
def cam(client, auth, test_video) -> dict:
    return client.post("/api/cameras", headers=auth, json={"name": "Prep 1", "source_url": test_video}).json()


@pytest.fixture
def media_token(client, auth) -> str:
    return client.post("/api/auth/media-token", headers=auth).json()["access_token"]


def add_event(camera_id: int, event_type="no_gloves", minutes_ago=0, with_frame=True, **kw):
    with SessionLocal() as db:
        camera = db.get(Camera, camera_id)
        frame = np.full((360, 640, 3), 120, np.uint8) if with_frame else None
        return create_event(
            db, camera=camera, event_type=event_type, frame=frame,
            occurred_at=datetime.now(UTC) - timedelta(minutes=minutes_ago), **kw,
        ).id


def test_event_types_catalogue(client, auth):
    types = {t["key"]: t for t in client.get("/api/events/types", headers=auth).json()}
    assert types["no_gloves"] == {"key": "no_gloves", "label": "No gloves", "severity": "critical", "area": "kitchen"}
    assert {"no_mask", "no_hair_cover", "no_apron", "pest", "table_not_cleared"} <= types.keys()


def test_events_need_auth(client):
    assert client.get("/api/events").status_code == 401


def test_create_and_read_event(client, auth, cam):
    event_id = add_event(cam["id"], confidence=0.87)
    e = client.get(f"/api/events/{event_id}", headers=auth).json()
    assert e["camera_name"] == "Prep 1" and e["type_label"] == "No gloves"
    assert e["severity"] == "critical" and e["status"] == "open"
    assert e["message"] == "Handling food without gloves"
    assert e["has_image"] is True and e["simulated"] is False and e["confidence"] == 0.87
    # Times are returned as explicit UTC so browsers show the right local time.
    assert e["occurred_at"].endswith("Z") or e["occurred_at"].endswith("+00:00")


def test_list_newest_first_with_pagination(client, auth, cam):
    ids = [add_event(cam["id"], minutes_ago=m) for m in (30, 20, 10)]
    page1 = client.get("/api/events?limit=2", headers=auth).json()
    assert page1["total"] == 3
    assert [e["id"] for e in page1["items"]] == [ids[2], ids[1]]
    page2 = client.get("/api/events?limit=2&offset=2", headers=auth).json()
    assert [e["id"] for e in page2["items"]] == [ids[0]]


def test_filters_and_status_counts(client, auth, cam):
    a = add_event(cam["id"], "no_gloves", minutes_ago=90)
    add_event(cam["id"], "no_mask", minutes_ago=5)
    add_event(cam["id"], "bin_open", minutes_ago=1)
    client.patch(f"/api/events/{a}", headers=auth, json={"status": "resolved"})

    r = client.get("/api/events?status=open", headers=auth).json()
    assert r["total"] == 2 and r["counts"] == {"open": 2, "acknowledged": 0, "resolved": 1, "false_alarm": 0}
    assert client.get("/api/events?severity=info", headers=auth).json()["total"] == 1
    assert client.get("/api/events?event_type=no_mask", headers=auth).json()["total"] == 1
    assert client.get(f"/api/events?camera_id={cam['id']}", headers=auth).json()["total"] == 3
    assert client.get("/api/events?camera_id=9999", headers=auth).json()["total"] == 0

    since = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    r = client.get("/api/events", params={"since": since}, headers=auth).json()
    assert r["total"] == 2 and r["counts"]["resolved"] == 0  # the 90-minute-old one is outside the window


def test_status_workflow_timestamps(client, auth, cam):
    event_id = add_event(cam["id"])
    url = f"/api/events/{event_id}"

    ack = client.patch(url, headers=auth, json={"status": "acknowledged"}).json()
    assert ack["acknowledged_at"] and ack["resolved_at"] is None

    res = client.patch(url, headers=auth, json={"status": "resolved", "note": "  Reminded chef  "}).json()
    assert res["resolved_at"] and res["acknowledged_at"] == ack["acknowledged_at"] and res["note"] == "Reminded chef"

    reopened = client.patch(url, headers=auth, json={"status": "open"}).json()
    assert reopened["acknowledged_at"] is None and reopened["resolved_at"] is None and reopened["note"] == "Reminded chef"

    fa = client.patch(url, headers=auth, json={"status": "false_alarm"}).json()
    assert fa["status"] == "false_alarm" and fa["acknowledged_at"] and fa["resolved_at"]

    assert client.patch(url, headers=auth, json={"status": None}).status_code == 422
    assert client.patch(url, headers=auth, json={"status": "bogus"}).status_code == 422
    assert client.patch("/api/events/99999", headers=auth, json={"status": "resolved"}).status_code == 404


def test_bulk_update(client, auth, cam):
    ids = [add_event(cam["id"]) for _ in range(3)]
    r = client.post("/api/events/bulk", headers=auth, json={"ids": ids[:2], "status": "acknowledged"}).json()
    assert {e["status"] for e in r} == {"acknowledged"}
    counts = client.get("/api/events", headers=auth).json()["counts"]
    assert counts["acknowledged"] == 2 and counts["open"] == 1
    assert client.post("/api/events/bulk", headers=auth, json={"ids": [], "status": "resolved"}).status_code == 422


def test_image_with_header_and_media_token(client, auth, cam, media_token):
    event_id = add_event(cam["id"])
    r = client.get(f"/api/events/{event_id}/image", headers=auth)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR).shape == (360, 640, 3)

    assert client.get(f"/api/events/{event_id}/image?token={media_token}").status_code == 200
    assert client.get(f"/api/events/{event_id}/image").status_code == 401
    # The media token only opens images/streams, not the rest of the API.
    assert client.get(f"/api/events/{event_id}?token={media_token}").status_code == 401

    # Stored under the configured data dir, never in the real backend/data during tests.
    assert list((settings.data_dir / "events").rglob("*.jpg"))


def test_event_without_image(client, auth, cam):
    event_id = add_event(cam["id"], with_frame=False)
    assert client.get(f"/api/events/{event_id}", headers=auth).json()["has_image"] is False
    assert client.get(f"/api/events/{event_id}/image", headers=auth).status_code == 404


def test_test_event_uses_camera_frame(client, auth, cam):
    r = client.post("/api/events/test", headers=auth, json={"camera_id": cam["id"], "event_type": "no_mask"})
    assert r.status_code == 201
    e = r.json()
    assert e["simulated"] is True and e["has_image"] is True and e["type_label"] == "No mask"
    img = client.get(f"/api/events/{e['id']}/image", headers=auth)
    assert cv2.imdecode(np.frombuffer(img.content, np.uint8), cv2.IMREAD_COLOR).shape == (360, 640, 3)


def test_test_event_validation(client, auth, cam):
    assert client.post("/api/events/test", headers=auth, json={"camera_id": cam["id"], "event_type": "nope"}).status_code == 422
    assert client.post("/api/events/test", headers=auth, json={"camera_id": 9999, "event_type": "no_mask"}).status_code == 404


def test_delete_event_removes_image(client, auth, cam):
    event_id = add_event(cam["id"])
    files_before = set((settings.data_dir / "events").rglob("*.jpg"))
    assert client.delete(f"/api/events/{event_id}", headers=auth).status_code == 204
    assert client.get(f"/api/events/{event_id}", headers=auth).status_code == 404
    assert len(set((settings.data_dir / "events").rglob("*.jpg"))) == len(files_before) - 1
    assert client.delete(f"/api/events/{event_id}", headers=auth).status_code == 404


def test_bulk_delete_removes_events_and_images(client, auth, cam):
    ids = [add_event(cam["id"]) for _ in range(3)]
    keep = add_event(cam["id"])
    files_before = len(list((settings.data_dir / "events").rglob("*.jpg")))
    r = client.post("/api/events/bulk-delete", headers=auth, json={"ids": [*ids, 99999]})
    assert r.json() == {"deleted": 3}  # unknown ids are ignored
    assert [e["id"] for e in client.get("/api/events", headers=auth).json()["items"]] == [keep]
    assert len(list((settings.data_dir / "events").rglob("*.jpg"))) == files_before - 3
    assert client.post("/api/events/bulk-delete", headers=auth, json={"ids": []}).status_code == 422
    assert client.post("/api/events/bulk-delete", json={"ids": [keep]}).status_code == 401


def test_event_kept_when_camera_deleted(client, auth, cam):
    event_id = add_event(cam["id"])
    client.delete(f"/api/cameras/{cam['id']}", headers=auth)
    e = client.get(f"/api/events/{event_id}", headers=auth).json()
    assert e["camera_id"] is None and e["camera_name"] == "Prep 1"
