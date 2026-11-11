import base64

import cv2
import numpy as np
import pytest

UNREACHABLE_RTSP = "rtsp://admin:secret@192.0.2.1:554/stream1"  # TEST-NET-1: guaranteed unroutable


def create(client, auth, **fields):
    body = {"name": "Test cam", "source_url": "0", **fields}
    return client.post("/api/cameras", headers=auth, json=body)


# --- CRUD -------------------------------------------------------------------


def test_create_list_get(client, auth):
    r = create(client, auth, name="Laptop Webcam", location="Desk")
    assert r.status_code == 201
    cam = r.json()
    assert cam["source_type"] == "webcam" and cam["status"] is None
    assert [c["name"] for c in client.get("/api/cameras", headers=auth).json()] == ["Laptop Webcam"]
    assert client.get(f"/api/cameras/{cam['id']}", headers=auth).json()["location"] == "Desk"


def test_duplicate_name_case_insensitive(client, auth):
    create(client, auth, name="Prep 1")
    r = create(client, auth, name="prep 1")
    assert r.status_code == 409


@pytest.mark.parametrize(
    "source, message",
    [("rtsp://", "host"), ("C:/does/not/exist.mp4", "Video file not found"), ("   ", "Source is required")],
)
def test_invalid_sources(client, auth, source, message):
    r = create(client, auth, source_url=source)
    assert r.status_code == 422
    assert message in r.text


def test_rtsp_password_masked(client, auth):
    cam = create(client, auth, source_url="rtsp://admin:secret@192.168.1.10:554/s1").json()
    assert cam["source_type"] == "rtsp"
    assert cam["source_display"] == "rtsp://admin:****@192.168.1.10:554/s1"


def test_update_and_null_rejected(client, auth):
    cam = create(client, auth).json()
    r = client.patch(f"/api/cameras/{cam['id']}", headers=auth, json={"enabled": False, "location": "Counter"})
    assert r.json()["enabled"] is False and r.json()["location"] == "Counter"
    assert client.patch(f"/api/cameras/{cam['id']}", headers=auth, json={"name": None}).status_code == 422


def test_delete(client, auth):
    cam = create(client, auth).json()
    assert client.delete(f"/api/cameras/{cam['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/cameras/{cam['id']}", headers=auth).status_code == 404


# --- Test connection / snapshot / status ------------------------------------


def _decode_data_url(data_url: str) -> np.ndarray:
    assert data_url.startswith("data:image/jpeg;base64,")
    raw = base64.b64decode(data_url.split(",", 1)[1])
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def test_test_source_video_file(client, auth, test_video):
    r = client.post("/api/cameras/test", headers=auth, json={"source_url": test_video}).json()
    assert r["ok"] is True, r
    assert (r["width"], r["height"]) == (640, 360)
    assert r["fps"] == 10.0
    assert _decode_data_url(r["snapshot"]).shape == (360, 640, 3)


def test_test_source_unreachable_stream(client, auth):
    r = client.post("/api/cameras/test", headers=auth, json={"source_url": UNREACHABLE_RTSP}).json()
    assert r["ok"] is False
    assert "not reachable" in r["error"] or "Timed out" in r["error"]
    assert r["snapshot"] is None


def test_test_source_validates_input(client, auth):
    assert client.post("/api/cameras/test", headers=auth, json={"source_url": "rtsp://"}).status_code == 422


def test_snapshot_returns_jpeg_and_sets_online(client, auth, test_video):
    cam = create(client, auth, source_url=test_video).json()
    r = client.get(f"/api/cameras/{cam['id']}/snapshot", headers=auth)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "no-store"
    img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape == (360, 640, 3)

    status = client.get(f"/api/cameras/{cam['id']}", headers=auth).json()["status"]
    assert status["state"] == "online" and status["width"] == 640 and status["error"] is None


def test_snapshot_unreachable_is_503_and_sets_offline(client, auth):
    cam = create(client, auth, source_url=UNREACHABLE_RTSP).json()
    r = client.get(f"/api/cameras/{cam['id']}/snapshot", headers=auth)
    assert r.status_code == 503 and r.json()["detail"]
    status = client.get(f"/api/cameras/{cam['id']}", headers=auth).json()["status"]
    assert status["state"] == "offline" and status["error"]


def test_snapshot_needs_auth(client, auth, test_video):
    cam = create(client, auth, source_url=test_video).json()
    assert client.get(f"/api/cameras/{cam['id']}/snapshot").status_code == 401


def test_check_all_skips_disabled(client, auth, test_video):
    good = create(client, auth, name="Good", source_url=test_video).json()
    bad = create(client, auth, name="Bad", source_url=UNREACHABLE_RTSP).json()
    off = create(client, auth, name="Off", source_url=test_video, enabled=False).json()

    result = {c["id"]: c["status"] for c in client.post("/api/cameras/check", headers=auth).json()}
    assert result[good["id"]]["state"] == "online"
    assert result[bad["id"]]["state"] == "offline"
    assert result[off["id"]] is None


def test_changing_source_clears_status(client, auth, test_video):
    cam = create(client, auth, source_url=test_video).json()
    client.get(f"/api/cameras/{cam['id']}/snapshot", headers=auth)
    r = client.patch(f"/api/cameras/{cam['id']}", headers=auth, json={"source_url": "0"}).json()
    assert r["status"] is None
