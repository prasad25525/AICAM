"""Cement plant: worker safety, equipment, production and logistics monitoring.

Detection ready now: safety helmet and vest (same pose + image-prompt method as the kitchen PPE),
restricted-area entry (zones + person tracking), conveyor spillage (image prompts on the floor
zone under the belt) and bag counting (a counting line on the packing belt, every frame). The other
use cases are in the event catalogue (so test events and reports work) and listed as planned until
their detectors are built.
"""

from app.industries import EventType, Industry, PPECheck, ZoneRule, ZoneTypeDef
from app.models import Severity

PRODUCTION, PACKING, YARD = "production", "packing", "yard"

CEMENT = Industry(
    key="cement",
    name="Cement plant",
    description="Worker safety & plant monitoring",
    icon="factory",
    score_label="Safety score",
    areas={PRODUCTION: "Production", PACKING: "Packing & dispatch", YARD: "Yard & gate", "other": "Other"},
    default_area=PRODUCTION,
    zone_types=(
        ZoneTypeDef("restricted", "Restricted / danger area", "#d95926"),
        ZoneTypeDef("conveyor", "Conveyor belt", "#3987e5"),
        ZoneTypeDef("conveyor_floor", "Floor under conveyor (spillage)", "#d55181"),
        ZoneTypeDef("packing_line", "Packing line (bag count)", "#199e70"),
        ZoneTypeDef("loading_bay", "Truck loading bay", "#c98500"),
        ZoneTypeDef("gate", "Truck gate", "#9085e9"),
        ZoneTypeDef("walkway", "Walkway", "#008300"),
        ZoneTypeDef("other", "Other", "#8f9690"),
    ),
    ppe_checks=(
        PPECheck(
            "no_helmet", "Safety helmet", "No helmet", "head",
            ("a photo of a worker wearing a hard hat", "a photo of a person wearing a safety helmet"),
            ("a photo of a person's bare head and hair", "a photo of a person without a helmet"),
        ),
        PPECheck(
            "no_vest", "Safety vest", "No vest", "torso",
            ("a photo of a person wearing a high-visibility safety vest", "a photo of a worker in a reflective orange or yellow vest"),
            ("a photo of a person wearing a shirt without a safety vest", "a photo of a person in plain clothes"),
        ),
    ),
    zone_rules=(
        ZoneRule("restricted_area", "Restricted area entry", "Needs a Restricted / danger area zone", (("restricted",),)),
        # Prompts chosen on the demo videos: spill floor 0.97-0.99, clean floor <= 0.01, other plant floors <= 0.02.
        ZoneRule(
            "conveyor_spillage", "Conveyor spillage", "Needs a Floor under conveyor zone", (("conveyor_floor",),),
            look_for=("a photo of a pile of spilled gravel and rocks on a concrete floor", "a photo of a heap of grey material spilled on the floor"),
            normal=("a photo of a clean empty concrete floor", "a photo of a bare concrete floor with nothing on it"),
        ),
        # Counts, never alerts: bags crossing the zone's counting line (see detection/counting.py).
        ZoneRule("bag_count", "Cement bag counting", "Needs a Packing line (bag count) zone", (("packing_line",),), counts="bags"),
    ),
    event_types={
        # Worker safety
        "no_helmet": EventType("No safety helmet", Severity.CRITICAL, PRODUCTION, "Worker without a safety helmet"),
        "no_vest": EventType("No safety vest", Severity.WARNING, PRODUCTION, "Worker without a high-visibility vest"),
        "restricted_area": EventType("Restricted area entry", Severity.CRITICAL, PRODUCTION, "Person entered a restricted area"),
        # Equipment and quality
        "conveyor_spillage": EventType("Conveyor spillage", Severity.WARNING, PRODUCTION, "Material spilling from the conveyor"),
        "damaged_bag": EventType("Damaged cement bag", Severity.WARNING, PACKING, "Torn or damaged cement bag on the line"),
        # Environment
        "dust_visible": EventType("Visible dust", Severity.WARNING, PRODUCTION, "Visible dust emission"),
    },
    planned=(
        "Damaged cement bag detection",
        "Truck entry/exit monitoring",
        "Visible dust detection",
    ),
)
