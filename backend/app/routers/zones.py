from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.detection.service import detection
from app.industries import get_industry
from app.models import Camera, Zone
from app.schemas import ZoneCreate, ZoneOut, ZoneUpdate
from app.services.industry import active_industry

router = APIRouter(tags=["zones"])


def _camera_or_404(db: Session, camera_id: int) -> Camera:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    return camera


def _zone_or_404(db: Session, zone_id: int) -> Zone:
    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zone not found")
    return zone


def _check_zone_type(zone_type: str, camera: Camera) -> None:
    industry = get_industry(camera.industry)
    if zone_type not in industry.zone_type_keys:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Unknown zone type for {industry.name}: {zone_type}. Choose one of: {', '.join(z.key for z in industry.zone_types)}",
        )


def _ensure_unique_name(db: Session, camera_id: int, name: str, exclude_id: int | None = None) -> None:
    q = select(Zone.id).where(Zone.camera_id == camera_id, func.lower(Zone.name) == name.lower())
    if exclude_id is not None:
        q = q.where(Zone.id != exclude_id)
    if db.scalar(q):
        raise HTTPException(status.HTTP_409_CONFLICT, f'This camera already has a zone named "{name}"')


@router.get("/zones", response_model=list[ZoneOut])
def list_all_zones(db: Session = Depends(get_db)):
    """Zones of the active industry's cameras."""
    industry = active_industry(db).key
    return db.scalars(select(Zone).join(Camera).where(Camera.industry == industry).order_by(Zone.camera_id, Zone.name)).all()


@router.get("/cameras/{camera_id}/zones", response_model=list[ZoneOut])
def list_camera_zones(camera_id: int, db: Session = Depends(get_db)):
    _camera_or_404(db, camera_id)
    return db.scalars(select(Zone).where(Zone.camera_id == camera_id).order_by(Zone.name)).all()


@router.post("/cameras/{camera_id}/zones", response_model=ZoneOut, status_code=status.HTTP_201_CREATED)
def create_zone(camera_id: int, body: ZoneCreate, db: Session = Depends(get_db)):
    camera = _camera_or_404(db, camera_id)
    _check_zone_type(body.zone_type, camera)
    _ensure_unique_name(db, camera_id, body.name)
    zone = Zone(camera_id=camera_id, **body.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    detection.refresh_soon()  # detection tags events with zones
    return zone


@router.patch("/zones/{zone_id}", response_model=ZoneOut)
def update_zone(zone_id: int, body: ZoneUpdate, db: Session = Depends(get_db)):
    zone = _zone_or_404(db, zone_id)
    changes = body.model_dump(exclude_unset=True)
    for required in ("name", "zone_type", "polygon"):
        if required in changes and changes[required] is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{required} cannot be empty")
    if "name" in changes:
        _ensure_unique_name(db, zone.camera_id, changes["name"], exclude_id=zone_id)
    if "zone_type" in changes:
        _check_zone_type(changes["zone_type"], zone.camera)
    for field, value in changes.items():
        setattr(zone, field, value)
    db.commit()
    db.refresh(zone)
    detection.refresh_soon()
    return zone


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    """Removes the zone. Past events keep their record but lose the zone link."""
    db.delete(_zone_or_404(db, zone_id))
    db.commit()
    detection.refresh_soon()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
