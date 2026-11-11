"""Reports over a date range: daily hygiene score, breakdowns, and CSV export of events."""

import csv
import io
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Event, EventStatus, Severity
from app.routers.dashboard import SCORE_PENALTY, HourCount, TypeCount, _score
from app.services.events import EVENT_TYPES
from app.services.industry import active_industry

router = APIRouter(prefix="/reports", tags=["reports"])

MAX_DAYS = 366
NO_ZONE = "No zone"


class DayRow(BaseModel):
    date: date
    violations: int  # false alarms excluded
    critical: int
    warning: int
    info: int
    false_alarms: int
    score: int


class NamedCount(BaseModel):
    name: str
    count: int


class ReportTotals(BaseModel):
    violations: int
    false_alarms: int
    false_alarm_rate: float | None  # share of all events marked false alarm
    open: int
    resolved: int
    avg_resolution_min: float | None  # detection -> resolved, for resolved events
    avg_score: float
    worst_day: date | None


class ReportSummary(BaseModel):
    start: date
    end: date
    days: list[DayRow]
    by_type: list[TypeCount]
    by_camera: list[NamedCount]
    by_zone: list[NamedCount]
    by_hour: list[HourCount]
    totals: ReportTotals
    score_formula: str


def _range(start: date, end: date, tz_offset: int) -> tuple[date, date, timedelta, datetime, datetime]:
    """Validate an inclusive local-date range; return it (end clipped to today) with its UTC bounds."""
    offset = timedelta(minutes=tz_offset)
    today = (datetime.now(UTC) + offset).date()
    if end < start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "End date is before start date")
    if (end - start).days + 1 > MAX_DAYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Choose at most {MAX_DAYS} days")
    end = min(end, today)  # no future days
    start = min(start, end)
    utc_start = datetime.combine(start, time.min, UTC) - offset
    utc_end = datetime.combine(end + timedelta(days=1), time.min, UTC) - offset
    return start, end, offset, utc_start, utc_end


def _events(db: Session, utc_start: datetime, utc_end: datetime) -> list[Event]:
    """The active industry's events in the range."""
    return list(
        db.scalars(
            select(Event)
            .where(Event.industry == active_industry(db).key, Event.occurred_at >= utc_start, Event.occurred_at < utc_end)
            .options(selectinload(Event.camera), selectinload(Event.zone))
            .order_by(Event.occurred_at)
        )
    )


def _camera_name(e: Event) -> str:
    return e.camera.name if e.camera else (e.details or {}).get("camera_name") or "Deleted camera"


def _zone_name(e: Event) -> str:
    return e.zone.name if e.zone else (e.details or {}).get("zone_name") or NO_ZONE


@router.get("/summary", response_model=ReportSummary)
def report_summary(
    start: date,
    end: date,
    tz_offset: int = Query(0, ge=-840, le=840, description="Browser's minutes east of UTC"),
    db: Session = Depends(get_db),
):
    start, end, offset, utc_start, utc_end = _range(start, end, tz_offset)
    events = _events(db, utc_start, utc_end)
    real = [e for e in events if e.status != EventStatus.FALSE_ALARM]

    per_day: dict[date, Counter] = {start + timedelta(days=i): Counter() for i in range((end - start).days + 1)}
    false_per_day: Counter = Counter()
    hours = [0] * 24
    for e in events:
        local = e.occurred_at + offset
        if e.status == EventStatus.FALSE_ALARM:
            false_per_day[local.date()] += 1
            continue
        per_day[local.date()][e.severity] += 1
        hours[local.hour] += 1

    days = [
        DayRow(
            date=d, violations=sum(c.values()), critical=c[Severity.CRITICAL], warning=c[Severity.WARNING],
            info=c[Severity.INFO], false_alarms=false_per_day[d], score=_score(c),
        )
        for d, c in per_day.items()
    ]

    types = Counter(e.event_type for e in real)
    resolution = [
        (e.resolved_at - e.occurred_at).total_seconds() / 60 for e in events if e.status == EventStatus.RESOLVED and e.resolved_at
    ]
    worst = min(days, key=lambda d: (d.score, -d.violations)) if any(d.violations for d in days) else None

    return ReportSummary(
        start=start,
        end=end,
        days=days,
        by_type=[TypeCount(event_type=k, label=EVENT_TYPES[k].label if k in EVENT_TYPES else k, count=n) for k, n in types.most_common()],
        by_camera=[NamedCount(name=k, count=n) for k, n in Counter(_camera_name(e) for e in real).most_common()],
        by_zone=[NamedCount(name=k, count=n) for k, n in Counter(_zone_name(e) for e in real).most_common()],
        by_hour=[HourCount(hour=h, count=n) for h, n in enumerate(hours)],
        totals=ReportTotals(
            violations=len(real),
            false_alarms=len(events) - len(real),
            false_alarm_rate=round((len(events) - len(real)) / len(events), 3) if events else None,
            open=sum(e.status == EventStatus.OPEN for e in events),
            resolved=sum(e.status == EventStatus.RESOLVED for e in events),
            avg_resolution_min=round(sum(resolution) / len(resolution), 1) if resolution else None,
            avg_score=round(sum(d.score for d in days) / len(days), 1),
            worst_day=worst.date if worst else None,
        ),
        score_formula=(
            f"Per day: 100 − {SCORE_PENALTY[Severity.CRITICAL]:g} per critical − {SCORE_PENALTY[Severity.WARNING]:g} per warning "
            f"− {SCORE_PENALTY[Severity.INFO]:g} per info violation (false alarms excluded)"
        ),
    )


CSV_COLUMNS = [
    "id", "occurred_at", "camera", "zone", "type", "severity", "status", "confidence", "message", "note",
    "acknowledged_at", "resolved_at", "test_event",
]


def _cell(value) -> str:
    """Neutralise spreadsheet formulas (a note like "=HYPERLINK(...)" must stay text in Excel)."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


@router.get("/export.csv", response_class=StreamingResponse, responses={200: {"content": {"text/csv": {}}}})
def export_csv(
    start: date,
    end: date,
    tz_offset: int = Query(0, ge=-840, le=840),
    db: Session = Depends(get_db),
):
    """Every event in the range (false alarms included, marked by status), times in local time."""
    start, end, offset, utc_start, utc_end = _range(start, end, tz_offset)
    local = lambda dt: (dt + offset).strftime("%Y-%m-%d %H:%M:%S") if dt else ""  # noqa: E731

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for e in _events(db, utc_start, utc_end):
        info = EVENT_TYPES.get(e.event_type)
        writer.writerow([_cell(v) for v in (
            e.id, local(e.occurred_at), _camera_name(e), _zone_name(e), info.label if info else e.event_type,
            e.severity.value, e.status.value, "" if e.confidence is None else round(e.confidence, 3), e.message, e.note,
            local(e.acknowledged_at), local(e.resolved_at), "yes" if (e.details or {}).get("simulated") else "no",
        )])

    filename = f"vigilsiddhi-events-{start}-to-{end}.csv"
    # UTF-8 with BOM so Excel shows non-English text (e.g. Telugu notes) correctly.
    return StreamingResponse(
        iter(["﻿" + buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
