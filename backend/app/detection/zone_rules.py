"""Zone rules: hand-washing and table clearing. Pure logic, fed once per analysed frame.

- handwash_short:    stood at the sink at least SINK_MIN_VISIT_S, but left before handwash_min_s.
- handwash_skipped:  came into a prep zone from elsewhere and stayed PREP_DWELL_S without a sink
                     visit in the last wash_valid_min minutes. People first seen already inside a
                     prep zone are not judged: they may have washed off-camera.
- table_not_cleared: a dining-table zone with nobody at it but tableware still on it for
                     table_clear_min minutes.
- restricted_area:   a person's feet inside a restricted / danger zone for restricted_min_s
                     (cement plant). Once per visit.
- image zone rules:  the zone's picture judged by prompts (e.g. conveyor_spillage: material on the
                     floor under the belt). The problem must be seen for visual_min_s; once per
                     episode, re-armed after the zone has looked clear for VISUAL_REARM_S.
"""

from dataclasses import dataclass, field

from app.detection.tracking import Track
from app.detection.types import Box
from app.detection.zones import ZoneShape, point_in_zone, zones_at_feet, zones_for_person
from app.industries import ALL_ZONE_RULES

SINK_MIN_VISIT_S = 3.0  # shorter than this is walking past, not washing
PREP_DWELL_S = 5.0  # must stay in prep this long (not just passing through)
PREP_TYPES = {"raw_prep", "cooked_prep", "veg_wash"}
ITEMS_GONE_S = 15.0  # tableware must be unseen this long before a table counts as cleared (detections flicker)
VISUAL_PROBLEM_P = 0.6  # image zone rules: P(problem) at or above this = problem seen
VISUAL_CLEAR_P = 0.3  # at or below = clear; in between = unsure (timers keep running)
VISUAL_REARM_S = 10.0  # clear this long before the same zone can alert again


@dataclass
class RuleEvent:
    event_type: str
    message: str
    zone: ZoneShape
    box: Box | None = None  # the person involved, if any
    details: dict = field(default_factory=dict)


@dataclass
class RuleParams:
    handwash_min_s: float = 20.0
    wash_valid_min: float = 30.0
    table_clear_min: float = 10.0
    restricted_min_s: float = 2.0  # inside a restricted zone this long (filters out a foot on the line)
    visual_min_s: float = 3.0  # an image zone rule's problem must be seen this long


@dataclass
class _Person:
    seen_outside_prep: bool = False
    sink_zone: ZoneShape | None = None
    sink_since: float | None = None
    sink_last: float | None = None
    last_wash_at: float | None = None
    prep_since: float | None = None
    skip_alerted: bool = False
    restricted_zone: int | None = None  # the restricted zone they are in, and since when
    restricted_since: float | None = None
    restricted_alerted: bool = False


@dataclass
class _Table:
    empty_with_items_since: float | None = None
    items_last_seen: float | None = None
    alerted: bool = False


@dataclass
class _ZoneWatch:
    problem_since: float | None = None
    clear_since: float | None = None
    alerted: bool = False


@dataclass
class TableObject:
    label: str
    box: Box  # pixels


class ZoneRuleEngine:
    def __init__(self):
        self._people: dict[int, _Person] = {}
        self._tables: dict[int, _Table] = {}
        # Each dining table's state after the last update, for showing on the live view.
        self.table_view: list[dict] = []
        # People inside restricted zones right now (box, zone name, seconds), for the live view.
        self.intrusions: list[dict] = []
        self._watches: dict[tuple[str, int], _ZoneWatch] = {}  # image zone rules, per (rule, zone)
        self.zone_view: list[dict] = []  # their state now, for the live view

    def update(
        self,
        now: float,
        tracks: list[Track],
        zones: list[ZoneShape],
        width: int,
        height: int,
        params: RuleParams,
        rules: set[str],
        objects: list[TableObject] | None = None,
        zone_probs: dict[tuple[str, int], float] | None = None,  # image zone rules: (rule, zone id) -> P(problem)
    ) -> list[RuleEvent]:
        events: list[RuleEvent] = []
        self.zone_view = []
        by_id = {z.id: z for z in zones}
        probs = {k: p for k, p in (zone_probs or {}).items() if k[0] in rules and k[1] in by_id}
        for (rule, zone_id), p in probs.items():
            events += self._visual(rule, by_id[zone_id], p, now, params)
        self._watches = {k: v for k, v in self._watches.items() if k in probs}  # forget removed zones / rules
        seen = set()
        self.intrusions = []
        for t in tracks:
            seen.add(t.id)
            person = self._people.setdefault(t.id, _Person())
            inside = zones_for_person(t.box, width, height, zones)
            if rules & {"handwash_short", "handwash_skipped"}:
                events += self._handwash(person, t, inside, now, params, rules)
            if "restricted_area" in rules:
                events += self._restricted(person, t, zones_at_feet(t.box, width, height, zones), now, params)
        # Forget people who have left (the tracker already dropped them).
        self._people = {k: v for k, v in self._people.items() if k in seen}

        if "table_not_cleared" in rules:
            events += self._tables_rule(tracks, zones, width, height, objects or [], now, params)
        else:
            self.table_view = []
        return events

    # --- hand washing ---------------------------------------------------------

    def _handwash(self, p: _Person, t: Track, inside: list[ZoneShape], now: float, params: RuleParams, rules: set[str]):
        events = []
        sink = next((z for z in inside if z.zone_type == "sink"), None)
        prep = next((z for z in inside if z.zone_type in PREP_TYPES), None)

        if sink:
            if p.sink_since is None:
                p.sink_since, p.sink_zone = now, sink
            p.sink_last = now
        elif p.sink_since is not None:
            # Just left the sink: judge the visit.
            duration = p.sink_last - p.sink_since
            if duration >= SINK_MIN_VISIT_S:
                p.last_wash_at = now
                if "handwash_short" in rules and duration < params.handwash_min_s:
                    events.append(
                        RuleEvent(
                            "handwash_short",
                            f"Hands washed for {duration:.0f}s (needs {params.handwash_min_s:.0f}s)",
                            p.sink_zone, t.box,
                            {"wash_seconds": round(duration, 1), "handwash_min_s": params.handwash_min_s, "track_id": t.id},
                        )
                    )
            p.sink_since = p.sink_last = p.sink_zone = None

        if prep is None:
            p.seen_outside_prep = True
            p.prep_since = None
            p.skip_alerted = False
        else:
            if p.prep_since is None:
                p.prep_since = now
            washed_recently = p.last_wash_at is not None and now - p.last_wash_at <= params.wash_valid_min * 60
            if (
                "handwash_skipped" in rules
                and p.seen_outside_prep
                and not p.skip_alerted
                and not washed_recently
                and now - p.prep_since >= PREP_DWELL_S
            ):
                p.skip_alerted = True
                events.append(
                    RuleEvent(
                        "handwash_skipped",
                        f"Entered {prep.name} without washing hands",
                        prep, t.box, {"track_id": t.id},
                    )
                )
        return events

    # --- restricted areas --------------------------------------------------------

    def _restricted(self, p: _Person, t: Track, inside: list[ZoneShape], now: float, params: RuleParams):
        zone = next((z for z in inside if z.zone_type == "restricted"), None)
        if zone is None:
            p.restricted_zone = p.restricted_since = None
            p.restricted_alerted = False  # left: the next entry is a new visit
            return []
        if p.restricted_zone != zone.id:
            p.restricted_zone, p.restricted_since, p.restricted_alerted = zone.id, now, False
        stayed = now - p.restricted_since
        self.intrusions.append({"box": list(t.box), "zone": zone.name, "seconds": round(stayed, 1)})
        if p.restricted_alerted or stayed < params.restricted_min_s:
            return []
        p.restricted_alerted = True
        return [
            RuleEvent(
                "restricted_area",
                f"Person inside {zone.name} for {stayed:.0f}s",
                zone, t.box, {"seconds_inside": round(stayed, 1), "track_id": t.id},
            )
        ]

    # --- image zone rules (e.g. conveyor spillage) -------------------------------

    def _visual(self, rule: str, zone: ZoneShape, p: float, now: float, params: RuleParams) -> list[RuleEvent]:
        w = self._watches.setdefault((rule, zone.id), _ZoneWatch())
        if p >= VISUAL_PROBLEM_P:
            state = "problem"
            w.clear_since = None
            w.problem_since = w.problem_since if w.problem_since is not None else now
        elif p <= VISUAL_CLEAR_P:
            state = "clear"
            w.problem_since = None
            w.clear_since = w.clear_since if w.clear_since is not None else now
            if now - w.clear_since >= VISUAL_REARM_S:
                w.alerted = False  # clean for a while: the next problem is a new episode
        else:
            state = "unsure"  # keep the timers: one doubtful frame doesn't end a spill
        seen = now - w.problem_since if w.problem_since is not None else 0.0
        label = ALL_ZONE_RULES[rule].label if rule in ALL_ZONE_RULES else rule
        xs, ys = [q[0] for q in zone.polygon], [q[1] for q in zone.polygon]
        self.zone_view.append({
            "zone_id": zone.id, "name": zone.name, "rule": rule, "label": label, "state": state,
            "p": round(p, 2), "seconds": round(seen, 1), "anchor": [round(sum(xs) / len(xs), 4), round(min(ys), 4)],
        })
        if state != "problem" or w.alerted or seen < params.visual_min_s:
            return []
        w.alerted = True
        return [RuleEvent(rule, f"{label} at {zone.name}", zone, None, {"seconds_seen": round(seen, 1), "p": round(p, 2)})]

    # --- tables ------------------------------------------------------------------

    def _tables_rule(self, tracks, zones, width, height, objects, now, params):
        events = []
        view = []
        tables = [z for z in zones if z.zone_type == "dining_table"]
        for zone in tables:
            state = self._tables.setdefault(zone.id, _Table())
            occupied = bool(zones_for_person_any(tracks, width, height, zone))
            items = [o for o in objects if point_in_zone((o.box[0] + o.box[2]) / 2 / width, (o.box[1] + o.box[3]) / 2 / height, zone)]
            if items:
                state.items_last_seen = now
            has_items = state.items_last_seen is not None and now - state.items_last_seen <= ITEMS_GONE_S
            xs, ys = [p[0] for p in zone.polygon], [p[1] for p in zone.polygon]
            shown = {"zone_id": zone.id, "name": zone.name, "items": sorted({o.label for o in items}),
                     "waited_s": 0.0, "limit_s": params.table_clear_min * 60,
                     "anchor": [round(sum(xs) / len(xs), 4), round(min(ys), 4)]}  # top-centre of the zone, 0..1
            view.append(shown)

            if occupied or not has_items:
                state.empty_with_items_since = None
                state.alerted = False
                shown["state"] = "occupied" if occupied else "clear"
                continue
            if state.empty_with_items_since is None:
                state.empty_with_items_since = now
            waited = now - state.empty_with_items_since
            shown["waited_s"] = round(waited, 1)
            shown["state"] = "not_cleared" if waited >= params.table_clear_min * 60 else "waiting"
            if not state.alerted and waited >= params.table_clear_min * 60:
                state.alerted = True
                labels = sorted({o.label for o in items})
                events.append(
                    RuleEvent(
                        "table_not_cleared",
                        f"{zone.name} not cleared for {_duration(waited)}" + (f" ({', '.join(labels)} left)" if labels else ""),
                        zone, None,
                        {"items": labels, "waited_min": round(waited / 60, 1), "table_clear_min": params.table_clear_min},
                    )
                )
        self._tables = {k: v for k, v in self._tables.items() if any(z.id == k for z in tables)}
        self.table_view = view
        return events


def _duration(seconds: float) -> str:
    return f"{seconds:.0f}s" if seconds < 60 else f"{seconds / 60:.0f} min"


def zones_for_person_any(tracks: list[Track], width: int, height: int, zone: ZoneShape) -> list[Track]:
    """People at a table: feet or body centre inside the table zone."""
    return [t for t in tracks if zone in zones_for_person(t.box, width, height, [zone])]
