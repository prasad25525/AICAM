"""Restaurant: kitchen hygiene and dining area."""

from app.industries import EventType, Industry, PPECheck, ZoneRule, ZoneTypeDef
from app.models import Severity

KITCHEN, DINING = "kitchen", "dining"

RESTAURANT = Industry(
    key="restaurant",
    name="Restaurant",
    description="Kitchen hygiene & dining area",
    icon="chef-hat",
    score_label="Hygiene score",
    areas={KITCHEN: "Kitchen", DINING: "Dining", "other": "Other"},
    default_area=KITCHEN,
    # Colours from the validated dark categorical palette; red is left out (it means "violation").
    zone_types=(
        ZoneTypeDef("sink", "Hand-wash sink", "#3987e5"),
        ZoneTypeDef("raw_prep", "Raw prep", "#d95926"),
        ZoneTypeDef("cooked_prep", "Cooked prep", "#199e70"),
        ZoneTypeDef("veg_wash", "Vegetable wash", "#c98500"),
        ZoneTypeDef("waste", "Waste / bins", "#d55181"),
        ZoneTypeDef("storage", "Storage", "#008300"),
        ZoneTypeDef("dining_table", "Dining table", "#9085e9"),
        ZoneTypeDef("other", "Other", "#8f9690"),
    ),
    # Prompts: the best-matching prompt on each side is compared, P(worn) = sigmoid(best_worn - best_not_worn).
    ppe_checks=(
        PPECheck(
            "no_hair_cover", "Hair cap / hairnet", "No hair cap", "head",
            ("a photo of a person wearing a chef hat", "a photo of a person wearing a hairnet", "a photo of a person wearing a cap"),
            ("a photo of a person with uncovered hair", "a photo of a person's bare head and hair"),
        ),
        PPECheck(
            "no_mask", "Face mask", "No mask", "face",
            ("a photo of a face wearing a surgical face mask", "a photo of a person wearing a face mask over mouth and nose"),
            ("a photo of a face without a mask", "a photo of a person's uncovered mouth and nose"),
        ),
        PPECheck(
            "no_gloves", "Gloves", "No gloves", "hands",
            ("a photo of a hand wearing a disposable glove", "a photo of a hand in a latex glove"),
            ("a photo of a bare hand", "a photo of a hand with bare skin"),
        ),
        PPECheck(
            "no_apron", "Apron", "No apron", "torso",
            ("a photo of a person wearing an apron", "a photo of a cook wearing a kitchen apron"),
            ("a photo of a person wearing a shirt without an apron", "a photo of a person in casual clothes"),
        ),
    ),
    zone_rules=(
        ZoneRule("handwash_skipped", "Hand wash skipped before prep", "Needs a Hand-wash sink zone and a prep zone",
                 (("sink",), ("raw_prep", "cooked_prep", "veg_wash"))),
        ZoneRule("handwash_short", "Hand wash too short", "Needs a Hand-wash sink zone", (("sink",),)),
        ZoneRule("table_not_cleared", "Table not cleared", "Needs Dining table zones", (("dining_table",),)),
    ),
    event_types={
        # Kitchen: staff hygiene (PPE)
        "no_hair_cover": EventType("No hair cap", Severity.WARNING, KITCHEN, "Staff member without a hair cap or hairnet"),
        "no_mask": EventType("No mask", Severity.WARNING, KITCHEN, "Staff member without a face mask"),
        "no_gloves": EventType("No gloves", Severity.CRITICAL, KITCHEN, "Handling food without gloves"),
        "no_apron": EventType("No apron", Severity.INFO, KITCHEN, "Staff member without an apron"),
        "phone_use": EventType("Phone use", Severity.WARNING, KITCHEN, "Mobile phone used in the kitchen"),
        "smoking_eating": EventType("Smoking or eating", Severity.CRITICAL, KITCHEN, "Smoking or eating in the food area"),
        # Kitchen: area rules
        "handwash_skipped": EventType("Handwash skipped", Severity.WARNING, KITCHEN, "Entered prep area without washing hands"),
        "handwash_short": EventType("Handwash too short", Severity.WARNING, KITCHEN, "Hands washed for less than 20 seconds"),
        "bin_open": EventType("Bin lid open", Severity.INFO, KITCHEN, "Waste bin lid left open"),
        "pest": EventType("Pest detected", Severity.CRITICAL, KITCHEN, "Rodent or insect detected"),
        "spill": EventType("Spill / wet floor", Severity.WARNING, KITCHEN, "Liquid spill on the floor"),
        "cross_contamination": EventType("Cross-contamination", Severity.CRITICAL, KITCHEN, "Moved from raw to cooked area without changing gloves"),
        "veg_wash": EventType("Vegetables not washed", Severity.WARNING, KITCHEN, "Vegetables not washed properly before prep"),
        # Dining area
        "table_not_cleared": EventType("Table not cleared", Severity.INFO, DINING, "Table left uncleared after guests left"),
        "crowding": EventType("Crowding", Severity.INFO, DINING, "Dining area over the occupancy limit"),
        "queue_long": EventType("Long queue", Severity.INFO, DINING, "Queue longer than the limit"),
        "staff_no_uniform": EventType("Staff not in uniform", Severity.WARNING, DINING, "Serving staff without uniform or cap"),
    },
)
