"""App-wide switches: whether violations are saved as events, and which ones pop up as notifications."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AppSettings

SETTINGS_ID = 1


def get_settings(db: Session) -> AppSettings:
    """The settings row, created with the defaults (everything on) the first time.

    The detection thread and API requests can both find it missing at the same moment; whoever
    inserts second gets a conflict, and then simply reads the row the other one created."""
    row = db.get(AppSettings, SETTINGS_ID)
    if row is None:
        db.add(AppSettings(id=SETTINGS_ID))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        row = db.get(AppSettings, SETTINGS_ID, populate_existing=True)
    return row


def should_notify(row: AppSettings, severity: str) -> bool:
    return row.notifications_enabled and severity in row.notify_severities
