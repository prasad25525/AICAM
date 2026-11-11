"""Which zone a detected person is in."""

from dataclasses import dataclass

from app.detection.types import Box


@dataclass(frozen=True)
class ZoneShape:
    id: int
    name: str
    polygon: tuple[tuple[float, float], ...]  # normalised 0-1 points
    zone_type: str = "other"

    @property
    def area(self) -> float:
        p = self.polygon
        return 0.5 * abs(sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p))))


def point_in_polygon(x: float, y: float, polygon) -> bool:
    """Ray casting; points exactly on an edge may go either way, which is fine here."""
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


EDGE_INSET = 0.002  # feet cut off by the bottom of the frame sit exactly on the edge; nudge them inside


def _test_points(box: Box, width: int, height: int) -> tuple[float, tuple[float, float]]:
    x0, y0, x1, y1 = box
    cx = min(max((x0 + x1) / 2 / width, EDGE_INSET), 1 - EDGE_INSET)
    feet = min(max(y1 / height, EDGE_INSET), 1 - EDGE_INSET)
    return cx, (feet, (y0 + y1) / 2 / height)


def zones_for_person(box: Box, width: int, height: int, zones: list[ZoneShape]) -> list[ZoneShape]:
    """Every zone the person is in (feet first, then box centre; see zone_for_person)."""
    cx, ys = _test_points(box, width, height)
    for y in ys:
        hits = [z for z in zones if point_in_polygon(cx, y, z.polygon)]
        if hits:
            return hits
    return []


def zones_at_feet(box: Box, width: int, height: int, zones: list[ZoneShape]) -> list[ZoneShape]:
    """Zones the person is standing in, by their feet only (no box-centre fallback): for a danger
    area, someone walking past the line has their body above it but their feet still outside."""
    cx, (feet, _) = _test_points(box, width, height)
    return [z for z in zones if point_in_polygon(cx, feet, z.polygon)]


def point_in_zone(x: float, y: float, zone: ZoneShape) -> bool:
    return point_in_polygon(x, y, zone.polygon)


def zone_for_person(box: Box, width: int, height: int, zones: list[ZoneShape]) -> ZoneShape | None:
    """The zone the person stands in: tested at their feet (bottom-centre of the box), then at the
    box centre (for cameras that only see people from the waist up). With nested zones the
    smallest one wins, e.g. "Sink" inside "Kitchen floor"."""
    hits = zones_for_person(box, width, height, zones)
    return min(hits, key=lambda z: z.area) if hits else None
