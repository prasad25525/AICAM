"""Counting things that pass a line on a conveyor (cement bags), on every video frame.

Light bags on a dark belt: at a short counting line across the belt, the share of bright pixels
rises while a bag passes and dips at the gap or seam before the next one. Each rise is one bag
(with hysteresis, so a noisy edge isn't counted twice). Cheap (about a millisecond a frame), so it
runs on every frame the camera delivers — bags pass about once a second, which the AI's 1-3 checks
a second would alias.

The line sits LINE_AT of the way along the zone (bags assumed to move left to right, as drawn
across the belt), and spans the zone's height there — so draw the zone tightly over the bags.

Limit: bags pressed end to end are only told apart if the gap or seam between them shows on at
least one frame, i.e. it is wider than the belt moves between two frames (about 16 px at 12 fps
on the demo belt). Tested on the demo video (5 of 5 bags per loop) and synthetic belts.
"""

import threading
from dataclasses import dataclass, field

import cv2
import numpy as np

from app.detection.zones import ZoneShape

LINE_AT = 0.75  # counting line position along the zone (0 = left edge, 1 = right edge)
LINE_HALF_WIDTH = 1  # pixels each side of the line: thin, so a narrow seam between touching bags darkens it
BRIGHT = 170  # grey level above which a pixel counts as "bag" (white / light bags)
RISE = 0.5  # share of bright pixels on the line that means "a bag is passing"
FALL = 0.3  # ...and that means "gap between bags"


@dataclass
class LineCounter:
    zone: ZoneShape
    total: int = 0
    passing: bool = False
    last_count_at: float | None = None
    level: float = 0.0  # last share of bright pixels, for the live view
    unsaved: int = 0  # counted but not yet written to the database
    history: list[float] = field(default_factory=list)  # times of recent counts (last minute), for the rate
    # feed() runs on the camera's reader thread, take_unsaved() on the detection thread.
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def take_unsaved(self) -> int:
        with self._lock:
            n, self.unsaved = self.unsaved, 0
            return n

    @property
    def line(self) -> tuple[float, float, float]:
        """(x, y0, y1) as fractions of the frame."""
        xs, ys = [p[0] for p in self.zone.polygon], [p[1] for p in self.zone.polygon]
        return min(xs) + LINE_AT * (max(xs) - min(xs)), min(ys), max(ys)

    def feed(self, frame: np.ndarray, now: float) -> int:
        """Look at one frame; returns how many bags were counted on it (0 or 1)."""
        h, w = frame.shape[:2]
        x, y0, y1 = self.line
        cx = int(x * w)
        strip = frame[int(y0 * h) : max(int(y1 * h), int(y0 * h) + 1), max(0, cx - LINE_HALF_WIDTH) : cx + LINE_HALF_WIDTH + 1]
        if strip.size == 0:
            return 0
        grey = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY) if strip.ndim == 3 else strip
        self.level = float((grey > BRIGHT).mean())
        if not self.passing and self.level >= RISE:
            self.passing = True
            with self._lock:
                self.total += 1
                self.unsaved += 1
                self.last_count_at = now
                self.history = [t for t in self.history if now - t <= 60] + [now]
            return 1
        if self.passing and self.level <= FALL:
            self.passing = False
        return 0

    def per_minute(self, now: float) -> int:
        with self._lock:
            return len([t for t in self.history if now - t <= 60])
