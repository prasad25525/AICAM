from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import counts
from app.services.industry import active_industry

router = APIRouter(prefix="/counts", tags=["counts"])


class CameraTotal(BaseModel):
    camera_id: int | None
    camera_name: str
    count: int


class CountSummary(BaseModel):
    kind: str
    today: int
    yesterday_same_time: int
    by_camera: list[CameraTotal]
    by_hour: list[int]  # local hours 0-23, today


@router.get("/today", response_model=CountSummary)
def today(
    kind: str = "bags",
    tz_offset: int = Query(0, ge=-840, le=840, description="Browser's minutes east of UTC, so 'today' is the local day"),
    db: Session = Depends(get_db),
):
    """Counted items (e.g. bags) today for the active industry, per camera and hour."""
    offset = timedelta(minutes=tz_offset)
    now = datetime.now(UTC)
    start = (now + offset).replace(hour=0, minute=0, second=0, microsecond=0) - offset
    end = now + timedelta(minutes=1)
    industry = active_industry(db).key
    per_camera = counts.totals(db, industry, kind, start, end)
    yesterday = counts.totals(db, industry, kind, start - timedelta(days=1), now - timedelta(days=1))
    return CountSummary(
        kind=kind,
        today=sum(c for _, _, c in per_camera),
        yesterday_same_time=sum(c for _, _, c in yesterday),
        by_camera=[CameraTotal(camera_id=cid, camera_name=name, count=c) for cid, name, c in per_camera],
        by_hour=counts.by_hour(db, industry, kind, start, end, offset),
    )
