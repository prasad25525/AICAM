"""In-memory last-known status per camera. Refreshed by snapshots and checks (later: by the detection workers)."""

import threading
from datetime import UTC, datetime

from app.schemas import CameraStatus
from app.services.capture import Grab

_status: dict[int, CameraStatus] = {}
_lock = threading.Lock()


def record_ok(camera_id: int, grab: Grab) -> CameraStatus:
    status = CameraStatus(
        state="online",
        checked_at=datetime.now(UTC),
        width=grab.width,
        height=grab.height,
        fps=grab.fps,
        latency_ms=grab.latency_ms,
    )
    with _lock:
        _status[camera_id] = status
    return status


def record_online(camera_id: int, width: int, height: int, fps: float | None) -> CameraStatus:
    """Called periodically by a running live stream."""
    status = CameraStatus(state="online", checked_at=datetime.now(UTC), width=width, height=height, fps=fps)
    with _lock:
        _status[camera_id] = status
    return status


def record_error(camera_id: int, error: str) -> CameraStatus:
    status = CameraStatus(state="offline", checked_at=datetime.now(UTC), error=error)
    with _lock:
        _status[camera_id] = status
    return status


def get(camera_id: int) -> CameraStatus | None:
    with _lock:
        return _status.get(camera_id)


def forget(camera_id: int) -> None:
    with _lock:
        _status.pop(camera_id, None)


def clear() -> None:
    """Forget every camera's status (tests reset between runs)."""
    with _lock:
        _status.clear()
