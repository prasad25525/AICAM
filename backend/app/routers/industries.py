"""Industries: the list (public, for the login page), the active industry's profile, and switching."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.detection.service import detection
from app.industries import INDUSTRIES, Industry
from app.models import Severity
from app.services.alerts import alerts
from app.services.industry import IndustryLocked, active_industry, locked_industry, set_active_industry

public_router = APIRouter(tags=["industries"])
router = APIRouter(tags=["industries"])


class IndustrySummary(BaseModel):
    key: str
    name: str
    description: str
    icon: str


class IndustryList(BaseModel):
    industries: list[IndustrySummary]
    active: str
    locked: bool  # one industry only: the login page hides the tabs


class NamedKey(BaseModel):
    key: str
    label: str


class ZoneTypeOut(NamedKey):
    colour: str


class PPECheckOut(BaseModel):
    key: str
    item: str
    missing: str


class ZoneRuleOut(BaseModel):
    key: str
    label: str
    needs: str
    zone_types: list[list[str]]
    counts: str | None = None  # a counting rule (e.g. "bags") instead of an alert


class EventTypeInfo(BaseModel):
    key: str
    label: str
    severity: Severity
    area: str


class IndustryProfile(IndustrySummary):
    """Everything the UI needs to show this industry: labels, checks, zone types, areas."""

    score_label: str
    locked: bool
    areas: list[NamedKey]
    default_area: str
    zone_types: list[ZoneTypeOut]
    ppe_checks: list[PPECheckOut]
    zone_rules: list[ZoneRuleOut]
    event_types: list[EventTypeInfo]
    planned: list[str]


class SwitchIn(BaseModel):
    industry: str


def _summary(i: Industry) -> IndustrySummary:
    return IndustrySummary(key=i.key, name=i.name, description=i.description, icon=i.icon)


def profile_of(i: Industry) -> IndustryProfile:
    return IndustryProfile(
        **_summary(i).model_dump(),
        score_label=i.score_label,
        locked=locked_industry() is not None,
        areas=[NamedKey(key=k, label=v) for k, v in i.areas.items()],
        default_area=i.default_area,
        zone_types=[ZoneTypeOut(key=z.key, label=z.label, colour=z.colour) for z in i.zone_types],
        ppe_checks=[PPECheckOut(key=c.key, item=c.item, missing=c.missing) for c in i.ppe_checks],
        zone_rules=[
            ZoneRuleOut(key=r.key, label=r.label, needs=r.needs, zone_types=[list(g) for g in r.zone_types], counts=r.counts)
            for r in i.zone_rules
        ],
        event_types=[EventTypeInfo(key=k, label=t.label, severity=t.severity, area=t.area) for k, t in i.event_types.items()],
        planned=list(i.planned),
    )


def switch_industry(db: Session, key: str) -> Industry:
    """Make `key` the active industry: detection moves to its cameras, open pages are told."""
    try:
        industry, changed = set_active_industry(db, key)
    except KeyError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown industry: {key}") from None
    except IndustryLocked as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None
    if changed:
        detection.set_focus(None)
        detection.refresh_soon()
        alerts.publish("industry", {"industry": industry.key, "name": industry.name})
    return industry


@public_router.get("/industries", response_model=IndustryList)
def list_industries(db: Session = Depends(get_db)):
    """For the login page: which industries exist and which one is active. No secrets here."""
    locked = locked_industry()
    shown = [locked] if locked else list(INDUSTRIES.values())
    return IndustryList(industries=[_summary(i) for i in shown], active=active_industry(db).key, locked=locked is not None)


@router.get("/industry", response_model=IndustryProfile)
def get_active_profile(db: Session = Depends(get_db)):
    return profile_of(active_industry(db))


@router.put("/industry", response_model=IndustryProfile)
def put_active_industry(body: SwitchIn, db: Session = Depends(get_db)):
    return profile_of(switch_industry(db, body.industry))
