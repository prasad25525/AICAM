"""Draw detection results on a frame, for event snapshots."""

import cv2
import numpy as np

from app.detection.types import Analysis
from app.services.events import EVENT_TYPES

RED = (60, 60, 235)
GREEN = (61, 242, 181)  # lime (BGR)
GOLD = (39, 162, 201)
GREY = (170, 170, 170)


def _label(img: np.ndarray, text: str, x: int, y: int, colour, scale: float) -> None:
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.65 * scale, 2)
    cv2.rectangle(img, (x, y - th - 8), (x + tw + 12, y + 6), colour, -1)
    cv2.putText(img, text, (x + 6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65 * scale, (20, 20, 20), 2, cv2.LINE_AA)


def annotate_zone(frame: np.ndarray, analysis: Analysis, zone, person_box=None, objects=()) -> np.ndarray:
    """Snapshot for a zone-rule alert: the zone outlined, the person involved in red, tableware marked."""
    img = frame.copy()
    h, w = img.shape[:2]
    thick = max(2, w // 400)
    scale = max(1.0, w / 800)
    pts = np.array([[int(x * w), int(y * h)] for x, y in zone.polygon], np.int32)
    overlay = img.copy()
    cv2.fillPoly(overlay, [pts], GOLD)
    img = cv2.addWeighted(overlay, 0.2, img, 0.8, 0)
    cv2.polylines(img, [pts], True, GOLD, thick)
    _label(img, zone.name, int(pts[:, 0].min()), max(24, int(pts[:, 1].min()) - 4), GOLD, scale)
    for p in analysis.persons:
        colour = RED if person_box is not None and tuple(p.box) == tuple(person_box) else GREY
        cv2.rectangle(img, p.box[:2], p.box[2:], colour, thick)
    for o in objects:
        cv2.rectangle(img, o.box[:2], o.box[2:], RED, max(1, thick - 1))
    return img


def annotate(frame: np.ndarray, analysis: Analysis, highlight: str | None = None) -> np.ndarray:
    img = frame.copy()
    thick = max(2, img.shape[1] // 400)
    scale = max(1.0, img.shape[1] / 800)  # readable on small (640px) frames too
    for person in analysis.persons:
        missing = [k for k, c in person.checks.items() if c.state == "violation"]
        colour = RED if missing else GREEN
        x0, y0, x1, y1 = person.box
        cv2.rectangle(img, (x0, y0), (x1, y1), colour, thick)
        # Regions that were checked; the alert's own check in gold.
        for check, c in person.checks.items():
            for r in c.regions:
                rc = GOLD if check == highlight else (RED if c.state == "violation" else GREY)
                cv2.rectangle(img, r[:2], r[2:], rc, 1)
        labels = [EVENT_TYPES[k].label for k in missing] or ["OK"]
        y = y0 + int(24 * scale)
        for text in labels:
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.65 * scale, 2)
            cv2.rectangle(img, (x0, y - th - 8), (x0 + tw + 12, y + 6), colour, -1)
            cv2.putText(img, text, (x0 + 6, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65 * scale, (20, 20, 20), 2, cv2.LINE_AA)
            y += th + 16
    return img
