"""Background detection: one thread that analyses frames from every camera with detection on.

It keeps each such camera's live stream open (as a viewer), runs the engine on the newest frame
every `interval_s`, feeds the results to the alert rules, and records events with an annotated
snapshot. One shared engine, because the GPU is shared.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.detection.annotate import annotate, annotate_zone
from app.detection.counting import LineCounter
from app.detection.rules import CheckTracker, camera_observation
from app.detection.tracking import Tracker
from app.detection.types import Analysis
from app.detection.zone_rules import RuleEvent, RuleParams, ZoneRuleEngine
from app.detection.zones import ZoneShape, zone_for_person
from app.industries import ALL_PPE_CHECKS, ALL_ZONE_RULES
from app.models import Camera, DetectionConfig, Zone
from app.services.app_settings import get_settings
from app.services.counts import add_count
from app.services.events import create_event
from app.services.industry import active_industry
from app.services.streams import CameraStream, streams

log = logging.getLogger("aicam.detection")

CONFIG_REFRESH_S = 2.0
ENGINE_RETRY_S = 60.0  # after a failed model load
FOCUS_TTL_S = 30.0  # focus mode ends unless renewed within this time
FOCUS_INTERVAL_S = 0.25  # how often the focused camera may be analysed
IDLE_SLEEP_S = 0.05


@dataclass
class CameraRun:
    camera_id: int
    camera_name: str
    source: str
    config: DetectionConfig
    stream: CameraStream
    trackers: dict[str, CheckTracker] = field(default_factory=dict)
    last_run: float = 0.0
    runs: list[float] = field(default_factory=list)  # recent analysis times, for the rate
    latest: Analysis | None = None
    latest_at: datetime | None = None
    latest_objects: list = field(default_factory=list)  # tableware seen in the latest frame (TableObject)
    latest_tables: list[dict] = field(default_factory=list)  # each dining table's rule state
    latest_intrusions: list[dict] = field(default_factory=list)  # people inside restricted zones
    latest_zone_states: list[dict] = field(default_factory=list)  # image zone rules, e.g. spillage per floor zone
    observations: dict[str, str] = field(default_factory=dict)
    zones: list[ZoneShape] = field(default_factory=list)
    error: str | None = None
    person_tracker: Tracker = field(default_factory=Tracker)
    zone_rules: ZoneRuleEngine = field(default_factory=ZoneRuleEngine)
    rule_fired_at: dict[str, float] = field(default_factory=dict)  # zone-rule cooldowns
    holding: bool = True  # False while paused by focus mode: its video is let go so it stops decoding
    # Counting lines (e.g. bags on a packing belt), fed every frame by a hook on the stream.
    counters: list[LineCounter] = field(default_factory=list)
    count_kind: str | None = None


class DetectionService:
    def __init__(self):
        self._lock = threading.Lock()
        self._runs: dict[int, CameraRun] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.engine = None
        self.engine_state = "idle"  # idle | loading | ready | error
        self.engine_error: str | None = None
        self._last_config_refresh = 0.0
        self._last_load_attempt = 0.0
        self._focus: tuple[int, float] | None = None  # (camera id, expires at)

    # --- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="detection", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        with self._lock:
            for run in self._runs.values():
                self._let_go(run)
            self._runs.clear()

    @staticmethod
    def _let_go(run: CameraRun) -> None:
        if run.holding:
            run.stream.remove_frame_hook(("count", run.camera_id))
            streams.release(run.stream)
            run.holding = False

    @staticmethod
    def _hold(run: CameraRun) -> None:
        if not run.holding or run.stream.stopped:
            if run.holding:
                streams.release(run.stream)
            run.stream = streams.acquire(run.camera_id, run.source)
            run.holding = True
        DetectionService._attach_counters(run)

    @staticmethod
    def _attach_counters(run: CameraRun) -> None:
        """Counting needs every frame, not just the analysed ones: hook the counters onto the stream."""
        key = ("count", run.camera_id)
        if run.counters and run.holding:
            run.stream.add_frame_hook(key, lambda frame, now: [c.feed(frame, now) for c in run.counters])
        else:
            run.stream.remove_frame_hook(key)

    def _apply_focus(self, focus: int | None) -> None:
        """In focus mode, let go of the paused cameras' videos (they stop decoding once nobody
        watches), freeing the CPU for the focused camera; take them back when focus ends."""
        with self._lock:
            focusing = focus is not None and focus in self._runs
            for run in self._runs.values():
                # Counting cameras keep their video: a missed frame is a missed bag.
                if focusing and run.camera_id != focus and not run.counters:
                    self._let_go(run)
                else:
                    self._hold(run)

    def refresh_soon(self) -> None:
        """Re-read camera settings on the next loop (after a config or camera change)."""
        self._last_config_refresh = 0.0

    # --- focus mode -------------------------------------------------------------

    def set_focus(self, camera_id: int | None) -> None:
        """Analyse only this camera (others pause) until FOCUS_TTL_S passes without a renewal.
        The Live View renews it while someone is watching one camera; if the page closes, normal
        detection resumes by itself."""
        self._focus = (camera_id, time.monotonic() + FOCUS_TTL_S) if camera_id is not None else None

    def focus_camera_id(self) -> int | None:
        focus = self._focus
        if focus is None or time.monotonic() > focus[1]:
            return None
        return focus[0]

    # --- read-only views for the API -----------------------------------------

    def status(self) -> dict:
        now = time.monotonic()
        focus = self.focus_camera_id()
        with self._lock:
            cameras = [
                {
                    "camera_id": r.camera_id,
                    "camera_name": r.camera_name,
                    "analyses_per_s": round(len([t for t in r.runs if now - t <= 5]) / 5, 1),
                    "last_ms": round(r.latest.inference_ms) if r.latest else None,
                    "last_at": r.latest_at,
                    "persons": len(r.latest.persons) if r.latest else 0,
                    "observations": dict(r.observations),
                    "error": r.error,
                    "paused": focus is not None and focus in self._runs and r.camera_id != focus,
                }
                for r in self._runs.values()
            ]
        return {
            "focus_camera_id": focus,
            "engine": {
                "state": self.engine_state,
                "name": getattr(self.engine, "name", None),
                "device": getattr(self.engine, "device", None),
                "error": self.engine_error,
            },
            "cameras": cameras,
        }

    def latest(self, camera_id: int) -> tuple[Analysis, datetime, list, list[dict], list[dict], list[dict]] | None:
        """Newest analysis, when it was made, tableware seen, dining-table states, people in restricted zones,
        and image zone rule states."""
        with self._lock:
            run = self._runs.get(camera_id)
            if run and run.latest:
                return run.latest, run.latest_at, run.latest_objects, run.latest_tables, run.latest_intrusions, run.latest_zone_states
        return None

    # --- worker ----------------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                if time.monotonic() - self._last_config_refresh >= CONFIG_REFRESH_S:
                    self._sync_cameras()
                    self._last_config_refresh = time.monotonic()
                did_work = self._analyse_due_cameras()
                self._save_counts()
            except Exception:  # never let one bad frame kill detection
                log.exception("Detection loop error")
                did_work = False
            if not did_work:
                self._stop.wait(IDLE_SLEEP_S)

    def _sync_cameras(self) -> None:
        with SessionLocal() as db:
            # Only the active industry's cameras run; switching industry stops the others.
            industry = active_industry(db).key
            rows = db.execute(
                select(Camera, DetectionConfig)
                .join(DetectionConfig, DetectionConfig.camera_id == Camera.id)
                .where(Camera.enabled, DetectionConfig.enabled, Camera.industry == industry)
            ).all()
            wanted = {cam.id: (cam, cfg) for cam, cfg in rows}
            for _, cfg in rows:
                db.expunge(cfg)
            zones_by_camera: dict[int, list[ZoneShape]] = {}
            if wanted:
                for z in db.scalars(select(Zone).where(Zone.camera_id.in_(wanted))):
                    zones_by_camera.setdefault(z.camera_id, []).append(
                        ZoneShape(id=z.id, name=z.name, polygon=tuple(tuple(p) for p in z.polygon), zone_type=str(z.zone_type))
                    )

        with self._lock:
            for camera_id in list(self._runs):
                run = self._runs[camera_id]
                cam_cfg = wanted.get(camera_id)
                if cam_cfg is None or cam_cfg[0].source_url != run.source:
                    self._let_go(run)
                    del self._runs[camera_id]
            for camera_id, (cam, cfg) in wanted.items():
                run = self._runs.get(camera_id)
                if run is None:
                    run = self._runs[camera_id] = CameraRun(
                        camera_id=camera_id, camera_name=cam.name, source=cam.source_url, config=cfg,
                        stream=streams.acquire(camera_id, cam.source_url),
                        zones=zones_by_camera.get(camera_id, []),
                    )
                else:
                    run.config, run.camera_name = cfg, cam.name
                    run.zones = zones_by_camera.get(camera_id, [])
                    if run.holding and run.stream.stopped:  # stream was restarted elsewhere (e.g. camera edited)
                        self._hold(run)
                self._update_counters(run)

        retry_ok = self.engine_state != "error" or time.monotonic() - self._last_load_attempt >= ENGINE_RETRY_S
        if wanted and self.engine is None and self.engine_state != "loading" and retry_ok:
            self._load_engine()

    def _update_counters(self, run: CameraRun) -> None:
        """One counter per counting zone of the camera's counting rules (e.g. bag_count on packing
        lines). A zone that didn't change keeps its counter, so the running total survives."""
        rules = [ALL_ZONE_RULES[c] for c in run.config.checks if c in ALL_ZONE_RULES and ALL_ZONE_RULES[c].counts]
        wanted = [z for z in run.zones if any(z.zone_type in group for r in rules for group in r.zone_types)]
        old = {c.zone: c for c in run.counters}
        run.counters = [old.get(z) or LineCounter(z) for z in wanted]
        run.count_kind = rules[0].counts if rules else None
        self._attach_counters(run)

    def _save_counts(self) -> None:
        """Write what the counters counted since last time (they run on the stream threads)."""
        with self._lock:
            pending = [(r.camera_id, r.count_kind, n) for r in self._runs.values() for c in r.counters if (n := c.take_unsaved())]
        if not pending:
            return
        with SessionLocal() as db:
            for camera_id, kind, n in pending:
                camera = db.get(Camera, camera_id)
                if camera is not None and kind:
                    add_count(db, camera, kind, n)

    def counters(self, camera_id: int) -> list[dict]:
        """The camera's counting lines now, for the live view."""
        now = time.monotonic()
        with self._lock:
            run = self._runs.get(camera_id)
            if run is None:
                return []
            return [
                {
                    "zone_id": c.zone.id, "name": c.zone.name, "kind": run.count_kind or "", "total": c.total,
                    "per_minute": c.per_minute(now), "line": [round(v, 4) for v in c.line], "passing": c.passing,
                }
                for c in run.counters
            ]

    def _load_engine(self) -> None:
        self._last_load_attempt = time.monotonic()
        self.engine_state, self.engine_error = "loading", None
        try:
            if settings.detection_engine == "fake":
                from app.detection.engine import FakeEngine

                self.engine = FakeEngine(settings.fake_violations, settings.fake_person_box, settings.fake_objects)
            else:
                from app.detection.engine import PPEEngine

                self.engine = PPEEngine(settings.models_dir)
            self.engine_state = "ready"
            log.info("Detection engine ready: %s on %s", self.engine.name, self.engine.device)
        except Exception as e:
            log.exception("Could not load detection engine")
            self.engine_state, self.engine_error = "error", str(e)

    def _analyse_due_cameras(self) -> bool:
        if self.engine is None:
            return False
        focus = self.focus_camera_id()
        self._apply_focus(focus)
        with self._lock:
            if focus is not None and focus in self._runs:
                # Focus mode: only the watched camera, as often as the GPU allows.
                run = self._runs[focus]
                interval = min(run.config.interval_s, FOCUS_INTERVAL_S)
                due = [run] if time.monotonic() - run.last_run >= interval else []
            else:
                due = [r for r in self._runs.values() if time.monotonic() - r.last_run >= r.config.interval_s]
        did_work = False
        for run in sorted(due, key=lambda r: r.last_run):
            frame = run.stream.latest_frame()
            if frame is None:
                run.error = run.stream.info()["error"] or "Waiting for video…"
                continue
            run.last_run = time.monotonic()
            self._analyse(run, frame)
            did_work = True
        return did_work

    def _analyse(self, run: CameraRun, frame) -> None:
        cfg = run.config
        checks = [c for c in cfg.checks if c in ALL_PPE_CHECKS]
        rules = {c for c in cfg.checks if c in ALL_ZONE_RULES}
        analysis = self.engine.analyze(frame, checks, settings.present_threshold, settings.absent_threshold)
        now = time.monotonic()

        # Zone rules follow each person over time, so give every person a stable id.
        tracks = run.person_tracker.update([p.box for p in analysis.persons], now)
        rule_events, objects = [], []
        if rules and run.zones:
            tables = [z for z in run.zones if z.zone_type == "dining_table"]
            objects = self.engine.detect_objects(frame, tables) if "table_not_cleared" in rules and tables else []
            # Image zone rules (e.g. spillage): judge each matching zone's picture.
            visual = [(r, z) for r in sorted(rules) if ALL_ZONE_RULES[r].is_visual for z in run.zones
                      if any(z.zone_type in group for group in ALL_ZONE_RULES[r].zone_types)]
            zone_probs = dict(zip(((r, z.id) for r, z in visual), self.engine.zone_probabilities(frame, visual))) if visual else {}
            # Restricted areas and image zone rules use the camera's 'alert after' time, like a missing helmet does.
            params = RuleParams(cfg.handwash_min_s, cfg.wash_valid_min, cfg.table_clear_min,
                                restricted_min_s=cfg.min_duration_s, visual_min_s=cfg.min_duration_s)
            rule_events = run.zone_rules.update(now, tracks, run.zones, analysis.width, analysis.height, params, rules, objects, zone_probs)
            for ev in rule_events:
                # Same rule on the same camera: at most once per cooldown (like the PPE alerts).
                last = run.rule_fired_at.get(ev.event_type)
                if last is not None and now - last < cfg.cooldown_s:
                    continue
                run.rule_fired_at[ev.event_type] = now
                self._record_rule(run, frame, analysis, ev, objects)

        fired = []
        observations = {}
        for check in checks:
            state, p = camera_observation(analysis, check)
            observations[check] = state
            tracker = run.trackers.setdefault(check, CheckTracker())
            if tracker.update(state, p, now, cfg.min_duration_s, cfg.cooldown_s):
                fired.append((check, tracker.confidence))

        with self._lock:
            run.latest, run.latest_at = analysis, datetime.now(UTC)
            run.latest_objects = objects
            run.latest_tables = run.zone_rules.table_view if rules and run.zones else []
            run.latest_intrusions = run.zone_rules.intrusions if rules and run.zones else []
            run.latest_zone_states = run.zone_rules.zone_view if rules and run.zones else []
            run.observations, run.error = observations, None
            run.runs = [t for t in run.runs if now - t <= 5] + [now]

        for check, confidence in fired:
            self._record(run, frame, analysis, check, confidence)

    def _record(self, run: CameraRun, frame, analysis: Analysis, check: str, confidence: float | None) -> None:
        violators = [p for p in analysis.persons if check in p.checks and p.checks[check].state == "violation"]
        # Where the (first) person in violation is standing, if zones are drawn for this camera.
        zone = next(
            (z for p in violators if (z := zone_for_person(p.box, analysis.width, analysis.height, run.zones))), None
        )
        with SessionLocal() as db:
            camera = db.get(Camera, run.camera_id)
            if camera is None or not get_settings(db).events_enabled:
                return
            event = create_event(
                db,
                camera=camera,
                event_type=check,
                frame=annotate(frame, analysis, highlight=check),
                confidence=confidence,
                zone_id=zone.id if zone else None,
                details={
                    "engine": self.engine.name,
                    "persons_in_view": len(analysis.persons),
                    "persons_in_violation": len(violators),
                    "boxes": [list(p.box) for p in violators],
                    "min_duration_s": run.config.min_duration_s,
                },
            )
        log.info("Event %s: %s on %s (confidence %s)", event.id, check, run.camera_name, confidence)

    def _record_rule(self, run: CameraRun, frame, analysis: Analysis, ev: RuleEvent, objects) -> None:
        with SessionLocal() as db:
            camera = db.get(Camera, run.camera_id)
            if camera is None or not get_settings(db).events_enabled:
                return
            event = create_event(
                db,
                camera=camera,
                event_type=ev.event_type,
                frame=annotate_zone(frame, analysis, ev.zone, ev.box, objects),
                message=ev.message,
                confidence=ev.details.get("p"),  # image zone rules: how sure the model was
                zone_id=ev.zone.id,
                details={"engine": self.engine.name, "rule": ev.event_type, **ev.details},
            )
        log.info("Event %s: %s on %s (%s)", event.id, ev.event_type, run.camera_name, ev.message)


detection = DetectionService()
