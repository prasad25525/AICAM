"""Industry packs: everything that differs between industries (what to detect, labels, zone types,
areas). The rest of the platform — cameras, streams, events, zones, dashboard, reports — is shared.

One industry is active at a time (see services/industry.py); each camera belongs to one industry,
and its zones and events follow it.
"""

from dataclasses import dataclass, field

from app.models import Severity

# Body regions the pose model can locate (see detection/regions.py).
Region = str  # "head" | "face" | "hands" | "torso"


@dataclass(frozen=True)
class PPECheck:
    """Something a person should wear, judged on one body region with yes/no image prompts."""

    key: str  # also the event type raised when it is missing
    item: str  # what should be worn, e.g. "Safety helmet"
    missing: str  # short label on screen, e.g. "No helmet"
    region: Region
    worn: tuple[str, ...]
    not_worn: tuple[str, ...]


@dataclass(frozen=True)
class ZoneRule:
    key: str  # also the event type it raises
    label: str
    needs: str  # shown when the camera lacks the zones, e.g. "Needs a Hand-wash sink zone"
    zone_types: tuple[tuple[str, ...], ...]  # all groups needed; any type within a group will do
    # Image check on the zone itself (no people involved), e.g. spillage on the floor under a conveyor:
    # the zone's picture is compared with these prompts; P(problem) = sigmoid(best look_for - best normal).
    look_for: tuple[str, ...] = ()
    normal: tuple[str, ...] = ()
    # Counting instead of alerting: what is counted on the zone's counting line (e.g. "bags").
    counts: str | None = None

    @property
    def is_visual(self) -> bool:
        return bool(self.look_for)


@dataclass(frozen=True)
class ZoneTypeDef:
    key: str
    label: str
    colour: str


@dataclass(frozen=True)
class EventType:
    label: str
    severity: Severity
    area: str
    message: str


@dataclass(frozen=True)
class Industry:
    key: str
    name: str  # e.g. "Restaurant"
    description: str  # e.g. "Kitchen hygiene & dining area"
    icon: str  # icon name for the UI
    score_label: str  # e.g. "Hygiene score"
    areas: dict[str, str]  # key -> label
    default_area: str
    zone_types: tuple[ZoneTypeDef, ...]
    ppe_checks: tuple[PPECheck, ...]
    zone_rules: tuple[ZoneRule, ...]
    event_types: dict[str, EventType]
    planned: tuple[str, ...] = field(default_factory=tuple)  # use cases on the roadmap, shown as "coming soon"

    @property
    def check_keys(self) -> list[str]:
        """Everything a camera of this industry can detect, in display order."""
        return [c.key for c in self.ppe_checks] + [r.key for r in self.zone_rules]

    @property
    def zone_type_keys(self) -> set[str]:
        return {z.key for z in self.zone_types}


from app.industries.cement import CEMENT  # noqa: E402
from app.industries.restaurant import RESTAURANT  # noqa: E402

INDUSTRIES: dict[str, Industry] = {i.key: i for i in (RESTAURANT, CEMENT)}
DEFAULT_INDUSTRY = RESTAURANT.key


def _merge(attr: str) -> dict:
    merged: dict = {}
    for industry in INDUSTRIES.values():
        items = getattr(industry, attr)
        for key, value in (items.items() if isinstance(items, dict) else ((x.key, x) for x in items)):
            if key in merged and merged[key] != value:
                raise ValueError(f"{attr} key {key!r} is defined differently by two industries")
            merged[key] = value
    return merged


# Lookups across all industries (event and check keys are unique platform-wide), so a label is
# always found even for an event recorded while another industry was active.
ALL_EVENT_TYPES: dict[str, EventType] = _merge("event_types")
ALL_PPE_CHECKS: dict[str, PPECheck] = _merge("ppe_checks")
ALL_ZONE_RULES: dict[str, ZoneRule] = _merge("zone_rules")


def get_industry(key: str | None) -> Industry:
    return INDUSTRIES.get(key or "", INDUSTRIES[DEFAULT_INDUSTRY])
