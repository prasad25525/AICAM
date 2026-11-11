from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field, field_validator

from app.models import EventStatus, Severity

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
# Areas and zone types come from the camera's industry pack; the routers check them against it.
Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
SourceType = Literal["webcam", "rtsp", "http", "file"]

STREAM_SCHEMES = {"rtsp": "rtsp", "rtsps": "rtsp", "http": "http", "https": "http"}


def source_type(source: str) -> SourceType:
    if source.isdigit():
        return "webcam"
    return STREAM_SCHEMES.get(urlsplit(source).scheme.lower(), "file")  # type: ignore[return-value]


def validate_source(source: str) -> str:
    source = source.strip()
    if not source:
        raise ValueError("Source is required")
    kind = source_type(source)
    if kind in ("rtsp", "http") and not urlsplit(source).hostname:
        raise ValueError("Stream URL must include a host, e.g. rtsp://192.168.1.10:554/stream1")
    if kind == "file" and not Path(source).is_file():
        raise ValueError(f"Video file not found: {source}")
    return source


def mask_source(source: str) -> str:
    """Hide the password in rtsp://user:pass@host URLs."""
    parts = urlsplit(source)
    if parts.password:
        netloc = f"{parts.username}:****@{parts.hostname}" + (f":{parts.port}" if parts.port else "")
        return urlunsplit(parts._replace(netloc=netloc))
    return source


class CameraCreate(BaseModel):
    name: Name
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    area: Key | None = None  # None = the active industry's default area
    source_url: str = Field(max_length=500, description='Webcam index ("0"), rtsp:// or http(s):// URL, or video file path')
    enabled: bool = True

    _check_source = field_validator("source_url")(validate_source)


class CameraUpdate(BaseModel):
    name: Name | None = None
    location: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    area: Key | None = None
    source_url: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None

    @field_validator("source_url")
    @classmethod
    def _check_source(cls, v: str | None) -> str | None:
        return None if v is None else validate_source(v)


class CameraStatus(BaseModel):
    state: Literal["online", "offline"]
    checked_at: datetime
    error: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    latency_ms: int | None = None


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str | None
    industry: str
    area: str
    source_url: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    status: CameraStatus | None = None  # last check result; None = not checked since backend start

    @computed_field
    @property
    def source_type(self) -> SourceType:
        return source_type(self.source_url)

    @computed_field
    @property
    def source_display(self) -> str:
        return mask_source(self.source_url)


class SourceTest(BaseModel):
    source_url: str = Field(max_length=500)

    _check_source = field_validator("source_url")(validate_source)


class SourceTestResult(BaseModel):
    ok: bool
    error: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    latency_ms: int | None = None
    snapshot: str | None = None  # data:image/jpeg;base64,...


class WebcamDevice(BaseModel):
    index: int
    width: int
    height: int
    in_use_by: str | None  # name of the camera already using this webcam


# --- Events ------------------------------------------------------------------


class EventTypeOut(BaseModel):
    key: str
    label: str
    severity: Severity
    area: str


class EventOut(BaseModel):
    id: int
    camera_id: int | None
    camera_name: str | None
    zone_id: int | None
    zone_name: str | None
    event_type: str
    type_label: str
    severity: Severity
    status: EventStatus
    message: str
    confidence: float | None
    has_image: bool
    simulated: bool
    note: str | None
    occurred_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    # Measured facts behind the violation (e.g. wash_seconds vs handwash_min_s), for showing it visually.
    evidence: dict = {}


class EventList(BaseModel):
    items: list[EventOut]
    total: int  # matching the filters, all pages
    counts: dict[str, int]  # per status, for the same filters ignoring the status filter


class EventUpdate(BaseModel):
    status: EventStatus | None = None
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class EventBulkUpdate(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    status: EventStatus


class EventBulkDelete(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)


class BulkDeleteResult(BaseModel):
    deleted: int


class TestEventCreate(BaseModel):
    camera_id: int
    event_type: str
    severity: Severity | None = None


# --- Zones -------------------------------------------------------------------

ZoneName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


def validate_polygon(points: list[list[float]]) -> list[list[float]]:
    """3-50 points, each [x, y] as a fraction (0-1) of the frame, with a real area."""
    if not 3 <= len(points) <= 50:
        raise ValueError("A zone needs between 3 and 50 points")
    for p in points:
        if len(p) != 2 or not all(0 <= v <= 1 for v in p):
            raise ValueError("Each point must be [x, y] with values between 0 and 1")
    area = 0.5 * abs(sum(points[i][0] * points[i - 1][1] - points[i - 1][0] * points[i][1] for i in range(len(points))))
    if area < 0.0005:  # about 2% x 2% of the frame
        raise ValueError("Zone is too small or its points are in a line")
    return [[round(x, 5), round(y, 5)] for x, y in points]


class ZoneCreate(BaseModel):
    name: ZoneName
    zone_type: Key = "other"
    polygon: list[list[float]]

    _check_polygon = field_validator("polygon")(validate_polygon)


class ZoneUpdate(BaseModel):
    name: ZoneName | None = None
    zone_type: Key | None = None
    polygon: list[list[float]] | None = None

    @field_validator("polygon")
    @classmethod
    def _check_polygon(cls, v):
        return None if v is None else validate_polygon(v)


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    name: str
    zone_type: str
    polygon: list[list[float]]
    created_at: datetime


class AppSettingsOut(BaseModel):
    events_enabled: bool
    notifications_enabled: bool
    notify_severities: list[Severity]


class AppSettingsUpdate(BaseModel):
    events_enabled: bool | None = None
    notifications_enabled: bool | None = None
    notify_severities: list[Severity] | None = None
