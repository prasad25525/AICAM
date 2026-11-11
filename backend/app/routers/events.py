import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Camera, Event, EventStatus, Severity
from app.schemas import (
    BulkDeleteResult,
    EventBulkDelete,
    EventBulkUpdate,
    EventList,
    EventOut,
    EventTypeOut,
    EventUpdate,
    TestEventCreate,
)
from app.services.alerts import alerts
from app.services.capture import CaptureError
from app.industries import get_industry
from app.services.events import EVENT_TYPES, create_event, snapshot_file
from app.services.industry import active_industry
from app.services.streams import grab

router = APIRouter(prefix="/events", tags=["events"])

HEARTBEAT_S = 15

# Detail keys worth showing to people (the rest, like boxes and track ids, is internal).
EVIDENCE_KEYS = (
    "wash_seconds", "handwash_min_s", "items", "waited_min", "table_clear_min",
    "persons_in_view", "persons_in_violation", "min_duration_s", "seconds_inside", "seconds_seen",
)


def _to_out(e: Event) -> EventOut:
    details = e.details or {}
    info = EVENT_TYPES.get(e.event_type)
    return EventOut(
        id=e.id,
        camera_id=e.camera_id,
        camera_name=e.camera.name if e.camera else details.get("camera_name"),
        zone_id=e.zone_id,
        zone_name=e.zone.name if e.zone else details.get("zone_name"),
        event_type=e.event_type,
        type_label=info.label if info else e.event_type,
        severity=e.severity,
        status=e.status,
        message=e.message,
        confidence=e.confidence,
        has_image=bool(e.snapshot_path),
        simulated=bool(details.get("simulated")),
        note=e.note,
        occurred_at=e.occurred_at,
        acknowledged_at=e.acknowledged_at,
        resolved_at=e.resolved_at,
        evidence={k: details[k] for k in EVIDENCE_KEYS if k in details},
    )


def _get_or_404(db: Session, event_id: int) -> Event:
    event = db.get(Event, event_id, options=[selectinload(Event.camera), selectinload(Event.zone)])
    if not event:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return event


def _apply_status(event: Event, new_status: EventStatus) -> None:
    now = datetime.now(UTC)
    event.status = new_status
    if new_status == EventStatus.OPEN:  # reopened
        event.acknowledged_at = None
        event.resolved_at = None
    elif new_status == EventStatus.ACKNOWLEDGED:
        event.acknowledged_at = event.acknowledged_at or now
        event.resolved_at = None
    else:  # resolved or false alarm
        event.acknowledged_at = event.acknowledged_at or now
        event.resolved_at = now


@router.get("/types", response_model=list[EventTypeOut])
def list_event_types(db: Session = Depends(get_db)):
    """Event types of the active industry."""
    return [EventTypeOut(key=k, label=t.label, severity=t.severity, area=t.area) for k, t in active_industry(db).event_types.items()]


@router.get("", response_model=EventList)
def list_events(
    db: Session = Depends(get_db),
    status_: EventStatus | None = Query(None, alias="status"),
    severity: Severity | None = None,
    camera_id: int | None = None,
    event_type: str | None = None,
    since: datetime | None = Query(None, description="ISO time, inclusive"),
    until: datetime | None = Query(None, description="ISO time, exclusive"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    filters = [Event.industry == active_industry(db).key]
    if severity:
        filters.append(Event.severity == severity)
    if camera_id is not None:
        filters.append(Event.camera_id == camera_id)
    if event_type:
        filters.append(Event.event_type == event_type)
    if since:
        filters.append(Event.occurred_at >= since)
    if until:
        filters.append(Event.occurred_at < until)

    counts = {s.value: 0 for s in EventStatus}
    for s, n in db.execute(select(Event.status, func.count()).where(*filters).group_by(Event.status)):
        counts[s.value] = n

    if status_:
        filters.append(Event.status == status_)
    total = db.scalar(select(func.count()).select_from(Event).where(*filters))
    rows = db.scalars(
        select(Event)
        .where(*filters)
        .options(selectinload(Event.camera), selectinload(Event.zone))
        .order_by(Event.occurred_at.desc(), Event.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return EventList(items=[_to_out(e) for e in rows], total=total, counts=counts)


@router.post("/test", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_test_event(body: TestEventCreate, db: Session = Depends(get_db)):
    """Create a sample event from the camera's current frame, to try the alert workflow before detection runs."""
    camera = db.get(Camera, body.camera_id)
    if not camera:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    if body.event_type not in get_industry(camera.industry).event_types:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown event type for this camera: {body.event_type}")
    try:
        frame = grab(camera.source_url).frame if camera.enabled else None
        capture_error = None
    except CaptureError as e:
        frame, capture_error = None, str(e)  # still create the event, just without a picture
    event = create_event(
        db,
        camera=camera,
        event_type=body.event_type,
        frame=frame,
        severity=body.severity,
        confidence=0.9,
        details={"simulated": True, **({"capture_error": capture_error} if capture_error else {})},
    )
    return _to_out(_get_or_404(db, event.id))


@router.post("/bulk", response_model=list[EventOut])
def bulk_update(body: EventBulkUpdate, db: Session = Depends(get_db)):
    events = list(db.scalars(select(Event).where(Event.id.in_(body.ids))))
    for e in events:
        _apply_status(e, body.status)
    db.commit()
    alerts.publish("changed", {"ids": [e.id for e in events]})
    return [_to_out(_get_or_404(db, e.id)) for e in events]


@router.post("/bulk-delete", response_model=BulkDeleteResult)
def bulk_delete(body: EventBulkDelete, db: Session = Depends(get_db)):
    """Permanently remove several events and their images."""
    events = list(db.scalars(select(Event).where(Event.id.in_(body.ids))))
    files = [p for e in events if (p := snapshot_file(e))]
    ids = [e.id for e in events]
    for e in events:
        db.delete(e)
    db.commit()
    for p in files:
        p.unlink(missing_ok=True)
    alerts.publish("changed", {"ids": ids})
    return BulkDeleteResult(deleted=len(events))


@router.get("/{event_id:int}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    return _to_out(_get_or_404(db, event_id))


@router.patch("/{event_id:int}", response_model=EventOut)
def update_event(event_id: int, body: EventUpdate, db: Session = Depends(get_db)):
    event = _get_or_404(db, event_id)
    changes = body.model_dump(exclude_unset=True)
    if "status" in changes:
        if changes["status"] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "status cannot be empty")
        _apply_status(event, changes["status"])
    if "note" in changes:
        event.note = changes["note"] or None
    db.commit()
    alerts.publish("changed", {"ids": [event_id]})
    return _to_out(_get_or_404(db, event_id))


@router.delete("/{event_id:int}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    """Permanently remove an event and its image (e.g. test events)."""
    event = _get_or_404(db, event_id)
    path = snapshot_file(event)
    db.delete(event)
    db.commit()
    if path:
        path.unlink(missing_ok=True)
    alerts.publish("changed", {"ids": [event_id]})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/stream", response_class=StreamingResponse, responses={200: {"content": {"text/event-stream": {}}}})
async def event_stream(request: Request, limit: int | None = Query(None, ge=1, description="Stop after N messages (tests)")):
    """Server-Sent Events: pushes {"type": "created", "event": {...}} for new events and
    {"type": "changed", "ids": [...]} when events are updated or deleted.
    Authenticate with ?token= (media token), because EventSource cannot send headers."""
    sub = alerts.subscribe()
    _, queue = sub

    async def messages():
        sent = 0
        try:
            yield f"retry: 3000\ndata: {json.dumps({'type': 'hello'})}\n\n"
            while not await request.is_disconnected():
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_S)
                except TimeoutError:
                    yield ": keep-alive\n\n"  # stops proxies closing an idle connection
                    continue
                yield f"data: {message}\n\n"
                sent += 1
                if limit and sent >= limit:
                    break
        finally:
            alerts.unsubscribe(sub)

    return StreamingResponse(
        messages(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.get(
    "/{event_id:int}/image",
    response_class=FileResponse,
    responses={200: {"content": {"image/jpeg": {}}}, 404: {"description": "No image"}},
)
def event_image(event_id: int, db: Session = Depends(get_db)):
    """The snapshot saved with the event. Accepts ?token= (media token) so it can be used in <img src>."""
    path = snapshot_file(_get_or_404(db, event_id))
    if not path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This event has no image")
    # Snapshots never change, so the browser may cache them.
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})
