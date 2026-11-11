from dataclasses import dataclass, field

Box = tuple[int, int, int, int]  # x0, y0, x1, y1 in pixels


@dataclass
class CheckResult:
    state: str  # "ok" | "violation" | "unknown"
    p_present: float | None = None  # model's probability that the item is worn
    regions: list[Box] = field(default_factory=list)  # image areas that were checked


@dataclass
class PersonResult:
    box: Box
    score: float
    checks: dict[str, CheckResult]  # keyed by event type, e.g. "no_mask"


@dataclass
class Analysis:
    width: int
    height: int
    persons: list[PersonResult]
    inference_ms: float


def state_from_probability(p_present: float, present_th: float, absent_th: float) -> str:
    if p_present >= present_th:
        return "ok"
    if p_present <= absent_th:
        return "violation"
    return "unknown"
