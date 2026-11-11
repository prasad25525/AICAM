"""Minimal person tracker: keeps an id on each person across analysed frames.

At 2-3 analyses per second people move little between frames, so greedy matching on box overlap
(IoU), with centre distance as a fallback, is enough. (supervision's ByteTrack is deprecated.)
"""

from dataclasses import dataclass

from app.detection.types import Box

MIN_IOU = 0.25
MAX_CENTRE_JUMP = 0.6  # fraction of the box diagonal a person may move between frames
MAX_AGE_S = 5.0  # forget a person not seen for this long


@dataclass
class Track:
    id: int
    box: Box
    first_seen: float
    last_seen: float


def iou(a: Box, b: Box) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _centre_distance(a: Box, b: Box) -> float:
    """Distance between centres, relative to the diagonal of box a."""
    ax, ay = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    diag = ((a[2] - a[0]) ** 2 + (a[3] - a[1]) ** 2) ** 0.5 or 1.0
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 / diag


class Tracker:
    def __init__(self):
        self._tracks: dict[int, Track] = {}
        self._next_id = 1

    def update(self, boxes: list[Box], now: float) -> list[Track]:
        """Match this frame's boxes to known people. Returns one track per box, in the same order."""
        self._tracks = {i: t for i, t in self._tracks.items() if now - t.last_seen <= MAX_AGE_S}

        # All candidate pairs, best first: overlap, then (for fast movers) closeness.
        pairs = []
        for bi, box in enumerate(boxes):
            for tid, t in self._tracks.items():
                overlap = iou(box, t.box)
                if overlap >= MIN_IOU:
                    pairs.append((1 + overlap, bi, tid))
                elif (d := _centre_distance(t.box, box)) <= MAX_CENTRE_JUMP:
                    pairs.append((1 - d, bi, tid))
        pairs.sort(reverse=True)

        assigned: dict[int, int] = {}
        used: set[int] = set()
        for _, bi, tid in pairs:
            if bi not in assigned and tid not in used:
                assigned[bi] = tid
                used.add(tid)

        result = []
        for bi, box in enumerate(boxes):
            tid = assigned.get(bi)
            if tid is None:
                tid, self._next_id = self._next_id, self._next_id + 1
                self._tracks[tid] = Track(id=tid, box=box, first_seen=now, last_seen=now)
            t = self._tracks[tid]
            t.box, t.last_seen = box, now
            result.append(t)
        return result
