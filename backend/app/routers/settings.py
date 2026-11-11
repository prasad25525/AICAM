from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Severity
from app.schemas import AppSettingsOut, AppSettingsUpdate
from app.services.app_settings import get_settings

router = APIRouter(prefix="/settings", tags=["settings"])


def _to_out(row) -> AppSettingsOut:
    return AppSettingsOut(
        events_enabled=row.events_enabled,
        notifications_enabled=row.notifications_enabled,
        notify_severities=row.notify_severities,
    )


@router.get("", response_model=AppSettingsOut)
def read_settings(db: Session = Depends(get_db)):
    return _to_out(get_settings(db))


@router.put("", response_model=AppSettingsOut)
def update_settings(body: AppSettingsUpdate, db: Session = Depends(get_db)):
    row = get_settings(db)
    if body.events_enabled is not None:
        row.events_enabled = body.events_enabled
    if body.notifications_enabled is not None:
        row.notifications_enabled = body.notifications_enabled
    if body.notify_severities is not None:
        # Keep the usual order and drop repeats.
        row.notify_severities = [s.value for s in Severity if s in body.notify_severities]
    db.commit()
    return _to_out(row)
