from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.detection.service import detection
from app.industries import get_industry
from app.models import Camera, DetectionConfig
from app.services.industry import active_industry

router = APIRouter(prefix="/detection", tags=["detection"])

# Checks default to everything the camera's industry can detect.
DEFAULTS = {
    "enabled": False, "min_duration_s": 5.0, "cooldown_s": 120.0, "interval_s": 0.5,
    "handwash_min_s": 20.0, "wash_valid_min": 30.0, "table_clear_min": 10.0,
}


class DetectionConfigIn(BaseModel):
    enabled: bool
    checks: list[str] | None = None  # None = all of the camera's industry checks
    min_duration_s: float = Field(5.0, ge=1, le=300)
    cooldown_s: float = Field(120.0, ge=10, le=3600)
    interval_s: float = Field(0.5, ge=0.2, le=10)
    # Zone rules (only act on cameras with matching zones drawn)
    handwash_min_s: float = Field(20.0, ge=5, le=120, description="A proper hand wash lasts at least this long")
    wash_valid_min: float = Field(30.0, ge=1, le=480, description="A hand wash counts for this long before prep")
    table_clear_min: float = Field(10.0, ge=0.1, le=120, description="Alert when an empty table keeps tableware this long")


class DetectionConfigOut(DetectionConfigIn):
    camera_id: int
    checks: list[str]


def _valid_checks(requested: list[str] | None, camera: Camera) -> list[str]:
    """The camera's industry decides what it can detect; keep the pack's order, drop duplicates."""
    available = get_industry(camera.industry).check_keys
    if requested is None:
        return available
    unsupported = sorted(set(requested) - set(available))
    if unsupported:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Not supported for this camera: {', '.join(unsupported)}. Available: {', '.join(available)}",
        )
    return [c for c in available if c in requested]


class CheckOut(BaseModel):
    state: str
    p_present: float | None
    regions: list[list[int]]


class PersonOut(BaseModel):
    box: list[int]
    score: float
    checks: dict[str, CheckOut]


class ObjectOut(BaseModel):
    label: str
    box: list[int]


class TableOut(BaseModel):
    zone_id: int
    name: str
    state: Literal["occupied", "clear", "waiting", "not_cleared"]
    items: list[str]
    waited_s: float  # empty with items on it for this long
    limit_s: float
    anchor: list[float]  # where to put its label: top-centre of the zone, as fractions of the frame


class IntrusionOut(BaseModel):
    box: list[int]
    zone: str
    seconds: float  # inside for this long


class ZoneStateOut(BaseModel):
    """An image zone rule on one zone right now, e.g. spillage on the floor under a conveyor."""

    zone_id: int
    name: str
    rule: str
    label: str
    state: Literal["problem", "clear", "unsure"]
    p: float  # P(problem)
    seconds: float  # problem seen for this long
    anchor: list[float]  # where to put its label: top-centre of the zone, as fractions of the frame


class CounterOut(BaseModel):
    """A counting line (e.g. bags on a packing belt)."""

    zone_id: int
    name: str
    kind: str  # e.g. "bags"
    total: int  # counted since detection started on this camera
    per_minute: int  # counted in the last minute
    line: list[float]  # x, y0, y1 as fractions of the frame
    passing: bool  # something is on the line right now


class LatestOut(BaseModel):
    camera_id: int
    at: datetime
    age_ms: int  # how old the result is, so clients can hide stale boxes
    width: int
    height: int
    inference_ms: float
    persons: list[PersonOut]
    objects: list[ObjectOut] = []  # tableware (only while the table rule runs)
    tables: list[TableOut] = []
    intrusions: list[IntrusionOut] = []  # people inside restricted zones (cement plant)
    zone_states: list[ZoneStateOut] = []  # image zone rules (e.g. conveyor spillage)
    counters: list[CounterOut] = []  # counting lines (e.g. bags)


class EngineOut(BaseModel):
    state: str
    name: str | None
    device: str | None
    error: str | None


class CameraDetectionOut(BaseModel):
    camera_id: int
    camera_name: str
    analyses_per_s: float
    last_ms: int | None
    last_at: datetime | None
    persons: int
    observations: dict[str, str]
    error: str | None
    paused: bool  # skipped while focus mode is on another camera


class StatusOut(BaseModel):
    engine: EngineOut
    cameras: list[CameraDetectionOut]
    available_checks: list[str]
    focus_camera_id: int | None


class FocusIn(BaseModel):
    camera_id: int | None  # None ends focus mode


def _config_out(camera: Camera, cfg: DetectionConfig | None) -> DetectionConfigOut:
    camera_id = camera.id
    if cfg is None:
        return DetectionConfigOut(camera_id=camera_id, checks=get_industry(camera.industry).check_keys, **DEFAULTS)
    return DetectionConfigOut(
        camera_id=camera_id, enabled=cfg.enabled, checks=cfg.checks, min_duration_s=cfg.min_duration_s,
        cooldown_s=cfg.cooldown_s, interval_s=cfg.interval_s, handwash_min_s=cfg.handwash_min_s,
        wash_valid_min=cfg.wash_valid_min, table_clear_min=cfg.table_clear_min,
    )


@router.get("/status", response_model=StatusOut)
def detection_status(db: Session = Depends(get_db)):
    return StatusOut(**detection.status(), available_checks=active_industry(db).check_keys)


@router.put("/focus", response_model=StatusOut)
def set_focus(body: FocusIn, db: Session = Depends(get_db)):
    """Focus mode: analyse only this camera, as fast as the GPU allows; other cameras pause (no
    alerts from them). Lasts 30 s unless renewed — the Live View renews it while a single camera
    is shown, so closing the page restores normal detection automatically."""
    if body.camera_id is not None and not db.get(Camera, body.camera_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    detection.set_focus(body.camera_id)
    return StatusOut(**detection.status(), available_checks=active_industry(db).check_keys)


@router.get("/configs", response_model=list[DetectionConfigOut])
def list_configs(db: Session = Depends(get_db)):
    """Detection settings of the active industry's cameras."""
    configs = {c.camera_id: c for c in db.scalars(select(DetectionConfig))}
    cameras = db.scalars(select(Camera).where(Camera.industry == active_industry(db).key).order_by(Camera.id))
    return [_config_out(c, configs.get(c.id)) for c in cameras]


def _camera_or_404(db: Session, camera_id: int) -> Camera:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    return camera


@router.get("/cameras/{camera_id}/config", response_model=DetectionConfigOut)
def get_config(camera_id: int, db: Session = Depends(get_db)):
    camera = _camera_or_404(db, camera_id)
    return _config_out(camera, db.get(DetectionConfig, camera_id))


@router.put("/cameras/{camera_id}/config", response_model=DetectionConfigOut)
def put_config(camera_id: int, body: DetectionConfigIn, db: Session = Depends(get_db)):
    camera = _camera_or_404(db, camera_id)
    values = body.model_dump()
    values["checks"] = _valid_checks(body.checks, camera)
    cfg = db.get(DetectionConfig, camera_id) or DetectionConfig(camera_id=camera_id)
    for field, value in values.items():
        setattr(cfg, field, value)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    detection.refresh_soon()
    return _config_out(camera, cfg)


@router.get("/cameras/{camera_id}/latest", response_model=LatestOut)
def latest(camera_id: int):
    """Newest analysis for a camera (for drawing boxes over the live view)."""
    found = detection.latest(camera_id)
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No detection results for this camera yet")
    a, at, objects, tables, intrusions, zone_states = found
    return LatestOut(
        zone_states=[ZoneStateOut(**z) for z in zone_states],
        counters=[CounterOut(**c) for c in detection.counters(camera_id)],
        objects=[ObjectOut(label=o.label, box=[int(v) for v in o.box]) for o in objects],
        tables=[TableOut(**t) for t in tables],
        intrusions=[IntrusionOut(**i) for i in intrusions],
        camera_id=camera_id, at=at, age_ms=int((datetime.now(UTC) - at).total_seconds() * 1000), width=a.width, height=a.height, inference_ms=round(a.inference_ms, 1),
        persons=[
            PersonOut(
                box=list(p.box), score=round(p.score, 3),
                checks={
                    k: CheckOut(state=c.state, p_present=None if c.p_present is None else round(c.p_present, 3), regions=[list(r) for r in c.regions])
                    for k, c in p.checks.items()
                },
            )
            for p in a.persons
        ],
    )
