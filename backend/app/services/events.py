"""Event catalogue, snapshot storage, and event creation (used by the detection workers and the test-event API)."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from app.config import settings
from app.industries import ALL_EVENT_TYPES as EVENT_TYPES  # every industry's event types (keys are unique)
from app.models import Camera, Event, Severity, Zone
from app.services.alerts import alerts
from app.services.app_settings import get_settings, should_notify
from app.services.capture import encode_jpeg


def snapshots_dir() -> Path:
    return settings.data_dir / "events"


def save_snapshot(frame: np.ndarray, when: datetime) -> str:
    """Save a JPEG under data/events/YYYY/MM/DD/ and return its path relative to that folder."""
    rel = Path(f"{when:%Y/%m/%d}") / f"{uuid.uuid4().hex}.jpg"
    path = snapshots_dir() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_jpeg(frame, max_width=1280, quality=85))
    return rel.as_posix()


def snapshot_file(event: Event) -> Path | None:
    if not event.snapshot_path:
        return None
    path = (snapshots_dir() / event.snapshot_path).resolve()
    # Never serve anything outside the snapshots folder.
    if not path.is_relative_to(snapshots_dir().resolve()) or not path.is_file():
        return None
    return path


def create_event(
    db,
    *,
    camera: Camera,
    event_type: str,
    frame: np.ndarray | None = None,
    severity: Severity | None = None,
    message: str | None = None,
    confidence: float | None = None,
    zone_id: int | None = None,
    details: dict | None = None,
    occurred_at: datetime | None = None,
) -> Event:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown event type: {event_type}")
    info = EVENT_TYPES[event_type]
    when = occurred_at or datetime.now(UTC)
    zone = db.get(Zone, zone_id) if zone_id is not None else None
    if zone is not None and zone.camera_id != camera.id:
        zone = None  # a zone belongs to one camera's picture; ignore a mismatched id
    event = Event(
        camera_id=camera.id,
        zone_id=zone.id if zone else None,
        industry=camera.industry,
        event_type=event_type,
        severity=severity or info.severity,
        message=message or info.message,
        confidence=confidence,
        snapshot_path=save_snapshot(frame, when) if frame is not None else None,
        # Keep camera/zone names so the event still reads well if either is deleted later.
        details={"camera_name": camera.name, **({"zone_name": zone.name} if zone else {}), **(details or {})},
        occurred_at=when,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    if not should_notify(get_settings(db), event.severity.value):
        alerts.publish("changed", {"ids": [event.id]})  # lists still refresh, just no pop-up
        return event
    alerts.publish(
        "created",
        {
            "event": {
                "id": event.id,
                "event_type": event.event_type,
                "type_label": info.label,
                "severity": event.severity.value,
                "message": event.message,
                "camera_id": camera.id,
                "camera_name": camera.name,
                "zone_name": zone.name if zone else None,
                "confidence": event.confidence,
                "has_image": bool(event.snapshot_path),
                "simulated": bool(event.details.get("simulated")),
                "occurred_at": event.occurred_at.isoformat(),
            }
        },
    )
    return event
