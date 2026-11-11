from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Always store UTC and always return timezone-aware UTC (SQLite drops the timezone otherwise)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


def str_enum(enum_cls: type[StrEnum]) -> Enum:
    """Store enum values ('kitchen') as plain strings, not names or native DB enums."""
    return Enum(enum_cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


# Areas and zone types depend on the industry (see app/industries); they are stored as plain text
# and validated against the camera's industry pack.
DEFAULT_INDUSTRY = "restaurant"


class Severity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class EventStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_ALARM = "false_alarm"


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    location: Mapped[str | None] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(32), default=DEFAULT_INDUSTRY, server_default=DEFAULT_INDUSTRY, index=True)
    area: Mapped[str] = mapped_column(String(32), default="kitchen")
    # RTSP/HTTP URL, a webcam index like "0", or a local video file path.
    source_url: Mapped[str] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    zones: Mapped[list["Zone"]] = relationship(back_populates="camera", cascade="all, delete-orphan", passive_deletes=True)
    events: Mapped[list["Event"]] = relationship(back_populates="camera", passive_deletes=True)


class DetectionConfig(Base):
    """Per-camera detection settings. A missing row means detection is off with default settings."""

    __tablename__ = "detection_configs"

    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    checks: Mapped[list[str]] = mapped_column(JSON, default=list)  # event types to detect (from the camera's industry pack)
    min_duration_s: Mapped[float] = mapped_column(Float, default=5.0)  # violation must last this long
    cooldown_s: Mapped[float] = mapped_column(Float, default=120.0)  # before the same alert repeats
    interval_s: Mapped[float] = mapped_column(Float, default=0.5)  # time between analysed frames
    # Zone rules
    handwash_min_s: Mapped[float] = mapped_column(Float, default=20.0, server_default="20")  # a proper hand wash
    wash_valid_min: Mapped[float] = mapped_column(Float, default=30.0, server_default="30")  # a wash counts this long
    table_clear_min: Mapped[float] = mapped_column(Float, default=10.0, server_default="10")  # table left uncleared
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    camera: Mapped["Camera"] = relationship()


class AppSettings(Base):
    """App-wide switches (a single row, id 1). A missing row means the defaults: everything on."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    events_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # save detected violations as events
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # pop-up alerts for new events
    notify_severities: Mapped[list[str]] = mapped_column(JSON, default=lambda: ["critical", "warning", "info"])
    # The industry shown and analysed right now; only its cameras run detection.
    active_industry: Mapped[str] = mapped_column(String(32), default=DEFAULT_INDUSTRY, server_default=DEFAULT_INDUSTRY)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class ProductionCount(Base):
    """Things counted per camera and minute, e.g. cement bags passing a counting line."""

    __tablename__ = "production_counts"
    __table_args__ = (Index("ix_counts_camera_kind_minute", "camera_id", "kind", "minute", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Kept if the camera is deleted (like events), so totals in reports don't change.
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"))
    camera_name: Mapped[str] = mapped_column(String(100))
    industry: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # e.g. "bags"
    minute: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)  # start of the minute (UTC)
    count: Mapped[int] = mapped_column(default=0)


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    zone_type: Mapped[str] = mapped_column(String(32), default="other")
    # Polygon points normalised to 0..1 of frame size: [[x, y], ...], so it survives resolution changes.
    polygon: Mapped[list[list[float]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    camera: Mapped[Camera] = relationship(back_populates="zones")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_camera_occurred", "camera_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Events are kept as history even if the camera or zone is deleted.
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"))
    zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id", ondelete="SET NULL"))
    # Copied from the camera, so the event stays in its industry even if the camera is deleted.
    industry: Mapped[str] = mapped_column(String(32), default=DEFAULT_INDUSTRY, server_default=DEFAULT_INDUSTRY, index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)  # e.g. "no_gloves", "no_mask"
    severity: Mapped[Severity] = mapped_column(str_enum(Severity), default=Severity.WARNING)
    status: Mapped[EventStatus] = mapped_column(str_enum(EventStatus), default=EventStatus.OPEN, index=True)
    message: Mapped[str] = mapped_column(String(300))
    confidence: Mapped[float | None] = mapped_column(Float)
    snapshot_path: Mapped[str | None] = mapped_column(String(500))
    clip_path: Mapped[str | None] = mapped_column(String(500))
    details: Mapped[dict | None] = mapped_column(JSON)  # boxes, track ids, model name, etc.
    note: Mapped[str | None] = mapped_column(Text)  # reviewer comment
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    camera: Mapped[Camera | None] = relationship(back_populates="events")
    zone: Mapped[Zone | None] = relationship()
