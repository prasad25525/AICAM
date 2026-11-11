import base64
from concurrent.futures import ThreadPoolExecutor

import cv2
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.detection.service import detection
from app.industries import get_industry
from app.models import Camera
from app.schemas import CameraCreate, CameraOut, CameraUpdate, SourceTest, SourceTestResult, WebcamDevice
from app.services import camera_status
from app.services.capture import CaptureError, encode_jpeg, lock_for
from app.services.industry import active_industry
from app.services.streams import grab as _grab
from app.services.streams import streams

router = APIRouter(prefix="/cameras", tags=["cameras"])

MAX_WEBCAM_INDEX = 4
WEBCAM_PROBE_WAIT_S = 3.0


def _to_out(camera: Camera) -> CameraOut:
    out = CameraOut.model_validate(camera)
    out.status = camera_status.get(camera.id)
    return out


def _get_or_404(db: Session, camera_id: int) -> Camera:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    return camera


def _ensure_unique_name(db: Session, name: str, exclude_id: int | None = None) -> None:
    query = select(Camera.id).where(func.lower(Camera.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Camera.id != exclude_id)
    if db.scalar(query):
        raise HTTPException(status.HTTP_409_CONFLICT, f'A camera named "{name}" already exists')


def _check_area(area: str, industry_key: str) -> None:
    industry = get_industry(industry_key)
    if area not in industry.areas:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown area for {industry.name}: {area}. Choose one of: {', '.join(industry.areas)}"
        )


def _check(camera_id: int, source: str) -> None:
    try:
        camera_status.record_ok(camera_id, _grab(source))
    except CaptureError as e:
        camera_status.record_error(camera_id, str(e))


@router.get("", response_model=list[CameraOut])
def list_cameras(db: Session = Depends(get_db)):
    """The active industry's cameras."""
    industry = active_industry(db).key
    return [_to_out(c) for c in db.scalars(select(Camera).where(Camera.industry == industry).order_by(Camera.area, Camera.name))]


@router.get("/devices", response_model=list[WebcamDevice])
def list_webcams(db: Session = Depends(get_db)):
    """Probe local webcams (index 0..4). A webcam open in another app may not be listed."""
    used = {c.source_url: c.name for c in db.scalars(select(Camera))}
    devices = []
    for index in range(MAX_WEBCAM_INDEX + 1):
        source = str(index)
        # Opening the same webcam from two threads at once can crash the Windows camera driver,
        # so take the same lock as snapshots and live streams.
        lock = lock_for(source)
        if not lock.acquire(timeout=WEBCAM_PROBE_WAIT_S):
            # Busy: a live stream (or a long snapshot) has it open. Report it from the stream if we can.
            stream = streams.find_by_source(source)
            if stream and stream.width:
                devices.append(WebcamDevice(index=index, width=stream.width, height=stream.height, in_use_by=used.get(source)))
            continue
        try:
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            try:
                if cap.isOpened():
                    devices.append(
                        WebcamDevice(
                            index=index,
                            width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                            height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                            in_use_by=used.get(source),
                        )
                    )
            finally:
                cap.release()
        finally:
            lock.release()
    return devices


@router.post("/test", response_model=SourceTestResult)
def test_source(body: SourceTest):
    """Try a source before saving it: connect, grab one frame, return it as a preview."""
    try:
        grab = _grab(body.source_url)
    except CaptureError as e:
        return SourceTestResult(ok=False, error=str(e))
    jpeg = base64.b64encode(encode_jpeg(grab.frame, max_width=960, quality=80)).decode()
    return SourceTestResult(
        ok=True,
        width=grab.width,
        height=grab.height,
        fps=grab.fps,
        latency_ms=grab.latency_ms,
        snapshot=f"data:image/jpeg;base64,{jpeg}",
    )


@router.post("/check", response_model=list[CameraOut])
def check_cameras(db: Session = Depends(get_db)):
    """Grab a frame from every enabled camera (of the active industry) in parallel and update their online/offline status."""
    industry = active_industry(db).key
    cameras = list(db.scalars(select(Camera).where(Camera.industry == industry).order_by(Camera.area, Camera.name)))
    enabled = [c for c in cameras if c.enabled]
    if enabled:
        with ThreadPoolExecutor(max_workers=min(8, len(enabled))) as pool:
            list(pool.map(lambda c: _check(c.id, c.source_url), enabled))
    return [_to_out(c) for c in cameras]


@router.post("", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
def create_camera(body: CameraCreate, db: Session = Depends(get_db)):
    """New cameras belong to the active industry."""
    _ensure_unique_name(db, body.name)
    industry = active_industry(db)
    data = body.model_dump()
    data["area"] = data["area"] or industry.default_area
    _check_area(data["area"], industry.key)
    camera = Camera(industry=industry.key, **data)
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return _to_out(camera)


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: int, db: Session = Depends(get_db)):
    return _to_out(_get_or_404(db, camera_id))


@router.get(
    "/{camera_id}/snapshot",
    responses={200: {"content": {"image/jpeg": {}}}, 503: {"description": "Camera unreachable"}},
    response_class=Response,
)
def camera_snapshot(camera_id: int, db: Session = Depends(get_db)):
    """A fresh JPEG frame from the camera. Also updates its online/offline status."""
    camera = _get_or_404(db, camera_id)
    try:
        grab = _grab(camera.source_url)
    except CaptureError as e:
        camera_status.record_error(camera.id, str(e))
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from None
    camera_status.record_ok(camera.id, grab)
    return Response(
        content=encode_jpeg(grab.frame),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store", "X-Frame-Width": str(grab.width), "X-Frame-Height": str(grab.height)},
    )


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(camera_id: int, body: CameraUpdate, db: Session = Depends(get_db)):
    camera = _get_or_404(db, camera_id)
    changes = body.model_dump(exclude_unset=True)
    for required in ("name", "area", "source_url", "enabled"):
        if required in changes and changes[required] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{required} cannot be empty")
    if "name" in changes:
        _ensure_unique_name(db, changes["name"], exclude_id=camera_id)
    if "area" in changes:
        _check_area(changes["area"], camera.industry)
    if changes.get("source_url", camera.source_url) != camera.source_url:
        camera_status.forget(camera_id)  # old status no longer applies
        streams.stop(camera_id)
    if changes.get("enabled") is False:
        streams.stop(camera_id)
    for field, value in changes.items():
        setattr(camera, field, value)
    db.commit()
    db.refresh(camera)
    detection.refresh_soon()  # pick up enable/disable or a new source right away
    return _to_out(camera)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(camera_id: int, db: Session = Depends(get_db)):
    """Deletes the camera and its zones. Its events are kept as history."""
    db.delete(_get_or_404(db, camera_id))
    db.commit()
    streams.stop(camera_id)
    camera_status.forget(camera_id)
    detection.refresh_soon()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
