"""Production counts (e.g. cement bags): saved per camera and minute, summed for the dashboard."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Camera, ProductionCount


def add_count(db: Session, camera: Camera, kind: str, n: int, when: datetime | None = None) -> None:
    """Add n to this camera's count for the minute `when` falls in."""
    if n <= 0:
        return
    minute = (when or datetime.now(UTC)).replace(second=0, microsecond=0)
    row = db.scalar(
        select(ProductionCount).where(ProductionCount.camera_id == camera.id, ProductionCount.kind == kind, ProductionCount.minute == minute)
    )
    if row is None:
        row = ProductionCount(camera_id=camera.id, camera_name=camera.name, industry=camera.industry, kind=kind, minute=minute, count=0)
        db.add(row)
    row.count += n
    db.commit()


def totals(db: Session, industry: str, kind: str, start: datetime, end: datetime) -> list[tuple[int | None, str, int]]:
    """(camera id, camera name, total) for the period, largest first."""
    rows = db.execute(
        select(ProductionCount.camera_id, ProductionCount.camera_name, func.sum(ProductionCount.count))
        .where(ProductionCount.industry == industry, ProductionCount.kind == kind, ProductionCount.minute >= start, ProductionCount.minute < end)
        .group_by(ProductionCount.camera_id, ProductionCount.camera_name)
        .order_by(func.sum(ProductionCount.count).desc())
    )
    return [(cid, name, int(total)) for cid, name, total in rows]


def by_hour(db: Session, industry: str, kind: str, start: datetime, end: datetime, offset) -> list[int]:
    """Counts per local hour (0-23) for the period; `offset` = the browser's timedelta from UTC."""
    hours = [0] * 24
    for minute, count in db.execute(
        select(ProductionCount.minute, ProductionCount.count).where(
            ProductionCount.industry == industry, ProductionCount.kind == kind, ProductionCount.minute >= start, ProductionCount.minute < end
        )
    ):
        hours[(minute + offset).hour] += count
    return hours
