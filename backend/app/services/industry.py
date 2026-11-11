"""Which industry is active: chosen at login (or switched later), or fixed by AICAM_INDUSTRY_LOCK."""

from sqlalchemy.orm import Session

from app.config import settings
from app.industries import INDUSTRIES, Industry, get_industry
from app.services.app_settings import get_settings


class IndustryLocked(Exception):
    pass


def locked_industry() -> Industry | None:
    return INDUSTRIES[settings.industry_lock] if settings.industry_lock else None


def check_lock_setting() -> None:
    """Fail at startup on a typo, rather than silently showing the wrong industry."""
    if settings.industry_lock and settings.industry_lock not in INDUSTRIES:
        raise ValueError(f"AICAM_INDUSTRY_LOCK={settings.industry_lock!r} is not one of: {', '.join(INDUSTRIES)}")


def active_industry(db: Session) -> Industry:
    return locked_industry() or get_industry(get_settings(db).active_industry)


def set_active_industry(db: Session, key: str) -> tuple[Industry, bool]:
    """Make `key` the active industry. Returns (industry, changed)."""
    if key not in INDUSTRIES:
        raise KeyError(key)
    locked = locked_industry()
    if locked and key != locked.key:
        raise IndustryLocked(f"This installation is set up for {locked.name} only")
    row = get_settings(db)
    changed = row.active_industry != key
    if changed:
        row.active_industry = key
        db.commit()
    return INDUSTRIES[key], changed
