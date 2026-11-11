"""Turn per-frame observations into alerts: a violation must persist before it fires, and the same
alert on the same camera is not repeated within the cooldown."""

from dataclasses import dataclass, field

from app.detection.types import Analysis

GRACE_S = 3.0  # a short gap (person turned away, missed frame) does not restart the timer


def camera_observation(analysis: Analysis, check: str) -> tuple[str, float | None]:
    """Combine people in view: any violation wins; otherwise ok if anyone was judged; else unknown.
    Returns (state, p_present of the deciding person)."""
    judged = [p.checks[check] for p in analysis.persons if check in p.checks and p.checks[check].state != "unknown"]
    violations = [c for c in judged if c.state == "violation"]
    if violations:
        return "violation", min((c.p_present for c in violations if c.p_present is not None), default=None)
    if judged:
        return "ok", max((c.p_present for c in judged if c.p_present is not None), default=None)
    return "unknown", None


@dataclass
class CheckTracker:
    violation_since: float | None = None
    last_violation_at: float | None = None
    fired_at: float | None = None
    p_samples: list[float] = field(default_factory=list)

    def update(self, state: str, p_present: float | None, now: float, min_duration_s: float, cooldown_s: float) -> bool:
        """Feed one observation; returns True when an alert should be raised now."""
        if state == "violation":
            if self.violation_since is None:
                self.violation_since = now
                self.p_samples = []
            self.last_violation_at = now
            if p_present is not None:
                self.p_samples.append(p_present)
        elif state == "ok":
            self.violation_since = None
        elif self.last_violation_at is not None and now - self.last_violation_at > GRACE_S:
            self.violation_since = None

        if self.violation_since is None or now - self.violation_since < min_duration_s:
            return False
        if self.fired_at is not None and now - self.fired_at < cooldown_s:
            return False
        self.fired_at = now
        return True

    @property
    def confidence(self) -> float | None:
        """How sure we are the item was missing, averaged over the violation."""
        if not self.p_samples:
            return None
        return round(1 - sum(self.p_samples) / len(self.p_samples), 3)
