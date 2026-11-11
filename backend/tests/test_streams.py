import time

import cv2
import numpy as np
import pytest

from app.config import settings
from app.services.streams import streams


@pytest.fixture(autouse=True)
def short_idle(monkeypatch):
    monkeypatch.setattr(settings, "stream_idle_timeout_s", 1.0)
    yield
    streams.stop_all()


@pytest.fixture
def media_token(client, auth) -> str:
    return client.post("/api/auth/media-token", headers=auth).json()["access_token"]


@pytest.fixture
def video_cam(client, auth, test_video) -> dict:
    return client.post("/api/cameras", headers=auth, json={"name": "Pattern", "source_url": test_video}).json()


def read_mjpeg(client, url: str) -> list[np.ndarray]:
    with client.stream("GET", url) as r:
        assert r.status_code == 200, r.read()
        assert r.headers["content-type"] == "multipart/x-mixed-replace; boundary=frame"
        body = r.read()
    frames = []
    for part in body.split(b"--frame\r\n")[1:]:
        headers, jpeg = part.split(b"\r\n\r\n", 1)
        assert b"Content-Type: image/jpeg" in headers
        frames.append(cv2.imdecode(np.frombuffer(jpeg.rstrip(b"\r\n"), np.uint8), cv2.IMREAD_COLOR))
    return frames


def wait_until(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


# --- auth ------------------------------------------------------------------


def test_stream_requires_token(client, video_cam):
    assert client.get(f"/api/cameras/{video_cam['id']}/stream?limit=1").status_code == 401


def test_api_token_not_accepted_in_url(client, auth, video_cam):
    api_token = auth["Authorization"].removeprefix("Bearer ")
    assert client.get(f"/api/cameras/{video_cam['id']}/stream?limit=1&token={api_token}").status_code == 401


def test_media_token_only_works_for_streams(client, media_token):
    assert client.get("/api/cameras", headers={"Authorization": f"Bearer {media_token}"}).status_code == 401
    assert client.get(f"/api/cameras?token={media_token}").status_code == 401


# --- streaming -------------------------------------------------------------


def test_mjpeg_frames_and_video_loops(client, video_cam, media_token):
    # The test video has 30 frames (3s at 10 fps), so 35 frames proves it loops.
    frames = read_mjpeg(client, f"/api/cameras/{video_cam['id']}/stream?limit=35&token={media_token}")
    assert len(frames) == 35
    assert all(f is not None and f.shape == (360, 640, 3) for f in frames)


def test_stream_listed_while_open_then_stops_when_idle(client, auth, video_cam, media_token):
    read_mjpeg(client, f"/api/cameras/{video_cam['id']}/stream?limit=5&token={media_token}")
    info = client.get("/api/streams", headers=auth).json()
    assert [s["camera_id"] for s in info] == [video_cam["id"]]
    assert info[0]["state"] == "live" and info[0]["width"] == 640 and info[0]["fps"] > 5

    # No viewers left: the camera is released after the idle timeout (1s in tests).
    assert wait_until(lambda: client.get("/api/streams", headers=auth).json() == [], timeout=10)


def test_long_retry_wait_ends_when_nobody_watches(tmp_path):
    """A camera that keeps failing waits longer and longer between retries (up to 30 s); leaving
    the page must still release it within a second or so, not after the wait."""
    import time

    from app.services.streams import streams

    from app.services.streams import NOT_LIVE_GRACE_S

    stream = streams.acquire(987654, str(tmp_path / "missing.mp4"))  # fails to open, every time
    streams.release(stream)  # nobody watching
    time.sleep(NOT_LIVE_GRACE_S + 0.2)  # past the idle timeout for a camera that isn't live
    start = time.monotonic()
    stream._wait_unless_idle(30)
    assert time.monotonic() - start < 3
    assert wait_until(lambda: streams.get(987654) is None, timeout=5)


def test_failing_camera_survives_slow_polls(tmp_path):
    """While a tile retries a failing camera every 3 s, the stream (and its error message) stays."""
    import time

    from app.services.streams import streams

    stream = streams.acquire(987655, str(tmp_path / "missing.mp4"))
    streams.release(stream)
    for _ in range(3):
        time.sleep(3)  # longer than the 1 s test idle timeout, shorter than the not-live grace
        assert streams.get(987655) is stream and stream.error
        streams.release(streams.acquire(987655, str(tmp_path / "missing.mp4")))  # the tile's next poll
    stream.stop()


def test_stream_marks_camera_online(client, auth, video_cam, media_token):
    read_mjpeg(client, f"/api/cameras/{video_cam['id']}/stream?limit=3&token={media_token}")
    status = client.get(f"/api/cameras/{video_cam['id']}", headers=auth).json()["status"]
    assert status["state"] == "online" and status["width"] == 640


def test_snapshot_reuses_open_stream(client, auth, video_cam, media_token):
    read_mjpeg(client, f"/api/cameras/{video_cam['id']}/stream?limit=3&token={media_token}")
    r = client.get(f"/api/cameras/{video_cam['id']}/snapshot", headers=auth)
    assert r.status_code == 200
    # Served from the stream's frame, so no reconnect latency was recorded.
    assert client.get(f"/api/cameras/{video_cam['id']}", headers=auth).json()["status"]["latency_ms"] == 0


def test_single_frame_endpoint_for_grids(client, auth, video_cam, media_token):
    url = f"/api/cameras/{video_cam['id']}/frame"
    assert client.get(url).status_code == 401
    r = client.get(f"{url}?token={media_token}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    assert img.shape == (360, 640, 3)
    # Polling keeps the camera open (as a recent viewer) without holding a connection.
    assert client.get("/api/streams", headers=auth).json()[0]["camera_id"] == video_cam["id"]
    assert wait_until(lambda: client.get("/api/streams", headers=auth).json() == [], timeout=10)


def test_disabled_camera_cannot_stream(client, auth, test_video, media_token):
    cam = client.post("/api/cameras", headers=auth, json={"name": "Off", "source_url": test_video, "enabled": False}).json()
    assert client.get(f"/api/cameras/{cam['id']}/stream?limit=1&token={media_token}").status_code == 409


def test_missing_camera_404(client, media_token):
    assert client.get(f"/api/cameras/99999/stream?limit=1&token={media_token}").status_code == 404


def test_two_cameras_on_the_same_video_stream_together(client, auth, test_video, media_token):
    a = client.post("/api/cameras", headers=auth, json={"name": "View A", "source_url": test_video}).json()
    b = client.post("/api/cameras", headers=auth, json={"name": "View B", "source_url": test_video}).json()
    for cam in (a, b):
        r = client.get(f"/api/cameras/{cam['id']}/frame?token={media_token}")
        assert r.status_code == 200, r.text  # previously the second waited forever for the first's lock


def test_webcam_probe_waits_for_lock_instead_of_double_opening(client, auth, monkeypatch):
    """While something holds a webcam open, the device scan must not open it a second time."""
    import app.routers.cameras as cameras_router
    from app.services.capture import lock_for

    opened = []
    monkeypatch.setattr(cameras_router, "WEBCAM_PROBE_WAIT_S", 0.2)
    monkeypatch.setattr(cameras_router.cv2, "VideoCapture", lambda i, *_: opened.append(i) or _ClosedCapture())
    lock = lock_for("0")
    lock.acquire()
    try:
        client.get("/api/cameras/devices", headers=auth)
    finally:
        lock.release()
    assert 0 not in opened and opened == [1, 2, 3, 4]


class _ClosedCapture:
    def isOpened(self):
        return False

    def release(self):
        pass


def test_disabling_camera_stops_its_stream(client, auth, video_cam, media_token):
    read_mjpeg(client, f"/api/cameras/{video_cam['id']}/stream?limit=2&token={media_token}")
    assert client.get("/api/streams", headers=auth).json()
    client.patch(f"/api/cameras/{video_cam['id']}", headers=auth, json={"enabled": False})
    assert client.get("/api/streams", headers=auth).json() == []
