from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Camera, Event, EventStatus, Severity
from app.routers.events import _to_out as event_out
from app.schemas import EventOut
from app.services import camera_status
from app.services.events import EVENT_TYPES
from app.services.industry import active_industry

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Hygiene score: 100 minus a penalty per violation today (false alarms excluded), never below 0.
SCORE_PENALTY = {Severity.CRITICAL: 5.0, Severity.WARNING: 2.0, Severity.INFO: 0.5}
RECENT_LIMIT = 8


class HourCount(BaseModel):
    hour: int  # 0-23, local time
    count: int


class TypeCount(BaseModel):
    event_type: str
    label: str
    count: int


class CameraState(BaseModel):
    id: int
    name: str
    state: str  # online | offline | unknown | disabled


class DashboardSummary(BaseModel):
    hygiene_score: int
    hygiene_score_yesterday: int  # same time window yesterday
    violations_today: int
    violations_yesterday: int  # same time window yesterday
    open_alerts: int
    critical_open: int
    cameras_enabled: int
    cameras_online: int
    cameras_offline: int
    by_hour: list[HourCount]
    current_hour: int  # local hour now, so the chart can stop at the present
    by_type: list[TypeCount]
    recent: list[EventOut]
    cameras: list[CameraState]
    score_formula: str


def _score(severity_counts: dict[Severity, int]) -> int:
    penalty = sum(SCORE_PENALTY[s] * n for s, n in severity_counts.items())
    return max(0, round(100 - penalty))


def _severity_counts(db: Session, industry: str, start: datetime, end: datetime) -> dict[Severity, int]:
    rows = db.execute(
        select(Event.severity, func.count())
        .where(Event.industry == industry, Event.occurred_at >= start, Event.occurred_at < end, Event.status != EventStatus.FALSE_ALARM)
        .group_by(Event.severity)
    )
    return {s: n for s, n in rows}


@router.get("/summary", response_model=DashboardSummary)
def summary(
    db: Session = Depends(get_db),
    tz_offset: int = Query(0, ge=-840, le=840, description="Browser's minutes east of UTC, so 'today' is the local day"),
):
    offset = timedelta(minutes=tz_offset)
    now = datetime.now(UTC)
    local_now = now + offset
    today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - offset
    yesterday_start = today_start - timedelta(days=1)
    yesterday_same_time = now - timedelta(days=1)

    today_end = now + timedelta(seconds=1)
    industry = active_industry(db).key  # everything below is for the active industry only
    today = _severity_counts(db, industry, today_start, today_end)
    yesterday = _severity_counts(db, industry, yesterday_start, yesterday_same_time)

    # Hourly and per-type breakdown for today (false alarms excluded), same window as the score.
    todays_events = db.execute(
        select(Event.occurred_at, Event.event_type).where(
            Event.industry == industry, Event.occurred_at >= today_start, Event.occurred_at < today_end, Event.status != EventStatus.FALSE_ALARM
        )
    ).all()
    hours = [0] * 24
    types: dict[str, int] = {}
    for occurred_at, event_type in todays_events:
        hours[(occurred_at + offset).hour] += 1
        types[event_type] = types.get(event_type, 0) + 1

    open_by_severity = dict(
        db.execute(
            select(Event.severity, func.count()).where(Event.industry == industry, Event.status == EventStatus.OPEN).group_by(Event.severity)
        ).all()
    )

    recent = db.scalars(
        select(Event)
        .where(Event.industry == industry)
        .options(selectinload(Event.camera), selectinload(Event.zone))
        .order_by(Event.occurred_at.desc(), Event.id.desc())
        .limit(RECENT_LIMIT)
    )

    cameras = []
    for c in db.scalars(select(Camera).where(Camera.industry == industry).order_by(Camera.area, Camera.name)):
        status = camera_status.get(c.id)
        state = "disabled" if not c.enabled else (status.state if status else "unknown")
        cameras.append(CameraState(id=c.id, name=c.name, state=state))

    return DashboardSummary(
        hygiene_score=_score(today),
        hygiene_score_yesterday=_score(yesterday),
        violations_today=sum(today.values()),
        violations_yesterday=sum(yesterday.values()),
        open_alerts=sum(open_by_severity.values()),
        critical_open=open_by_severity.get(Severity.CRITICAL, 0),
        cameras_enabled=sum(c.state != "disabled" for c in cameras),
        cameras_online=sum(c.state == "online" for c in cameras),
        cameras_offline=sum(c.state == "offline" for c in cameras),
        by_hour=[HourCount(hour=h, count=n) for h, n in enumerate(hours)],
        current_hour=local_now.hour,
        by_type=[
            TypeCount(event_type=k, label=EVENT_TYPES[k].label if k in EVENT_TYPES else k, count=n)
            for k, n in sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        recent=[event_out(e) for e in recent],
        cameras=cameras,
        score_formula="100 − 5 per critical − 2 per warning − 0.5 per info violation today (false alarms excluded)",
    )
