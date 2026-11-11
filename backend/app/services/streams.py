"""Continuous camera readers, one per camera, shared by every viewer (and later the detection workers).

A stream opens its camera when the first viewer arrives, keeps the newest frame in memory, encodes
JPEGs only while someone is watching, reconnects with backoff on failure, and closes the camera
`stream_idle_timeout_s` after the last viewer leaves.
"""

import logging
import threading
import time
from collections import deque
from collections.abc import Callable

import cv2
import numpy as np

from app.config import settings
from app.schemas import source_type
from app.services import camera_status
from app.services.capture import CaptureError, Grab, encode_jpeg, grab_frame, lock_for, open_capture, open_error

log = logging.getLogger(__name__)

STATUS_REPORT_INTERVAL_S = 5
POLL_VIEWER_S = 2.0  # a frame poll counts as "watching" for this long
FPS_WINDOW_S = 3.0  # fps = frames delivered over this window
MAX_BACKOFF_S = 30
NOT_LIVE_GRACE_S = 5.0  # idle timeout floor for a camera that isn't live (its tile retries every 3 s)


class CameraStream:
    def __init__(self, manager: "StreamManager", camera_id: int, source: str):
        self.manager = manager
        self.camera_id = camera_id
        self.source = source
        self.kind = source_type(source)

        # Guarded by manager._lock
        self.viewers = 0
        self.last_viewer_at = time.monotonic()

        # Guarded by self._lock
        self._lock = threading.Lock()
        self.state = "connecting"  # connecting | live | error | stopped
        self.error: str | None = None
        self.fps = 0.0
        self.width: int | None = None
        self.height: int | None = None
        self._frame: np.ndarray | None = None
        self._frame_at = 0.0
        self._frame_times: deque[float] = deque()
        self._jpeg: bytes | None = None
        self._jpeg_id = 0
        self._jpeg_at = 0.0
        self._hooks: dict[object, Callable[[np.ndarray, float], None]] = {}  # called with every frame

        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"stream-{camera_id}", daemon=True)

    # --- public -----------------------------------------------------------

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def stopped(self) -> bool:
        return self._stop.is_set()

    def add_frame_hook(self, key: object, fn: Callable[[np.ndarray, float], None]) -> None:
        """Call fn(frame, monotonic time) on every frame this stream reads (e.g. a bag counter, which
        must see every frame). Runs on the reader thread, so it has to be quick."""
        with self._lock:
            self._hooks[key] = fn

    def remove_frame_hook(self, key: object) -> None:
        with self._lock:
            self._hooks.pop(key, None)

    def latest_jpeg(self) -> tuple[bytes | None, int]:
        with self._lock:
            return self._jpeg, self._jpeg_id

    def fresh_jpeg(self, max_age_s: float = 0.5) -> bytes | None:
        """The reader's last encoded JPEG if recent (so frame polling doesn't re-encode)."""
        with self._lock:
            if self._jpeg is not None and self.state == "live" and time.monotonic() - self._jpeg_at <= max_age_s:
                return self._jpeg
            return None

    def latest_frame(self, max_age_s: float = 2.0) -> np.ndarray | None:
        """Newest frame if it is recent; lets snapshots reuse the stream instead of reopening the camera."""
        with self._lock:
            if self._frame is not None and self.state == "live" and time.monotonic() - self._frame_at <= max_age_s:
                return self._frame
            return None

    def info(self) -> dict:
        with self._lock:
            return {
                "camera_id": self.camera_id,
                "state": self.state,
                "error": self.error,
                "fps": round(self.fps, 1),
                "width": self.width,
                "height": self.height,
                "viewers": self.viewers,
            }

    # --- reader thread ----------------------------------------------------

    def _run(self) -> None:
        backoff = 1.0
        try:
            while not self._stop.is_set() and not self.manager._expire_if_idle(self):
                lock = lock_for(self.source)
                if not lock.acquire(timeout=1):  # a one-off snapshot has the camera open; try again
                    continue
                cap = None
                try:
                    self._set(state="connecting")
                    cap = open_capture(self.source)
                    if not cap.isOpened():
                        # Explain the first failure in a row; repeats (backoff > 1) keep that message
                        # instead of probing the camera again, which would only slow down reconnects.
                        raise CaptureError(self.error if backoff > 1.0 and self.error else open_error(self.source))
                    if self.kind in ("rtsp", "http"):
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # prefer the newest frame over a backlog
                    backoff = 1.0
                    self._read_loop(cap)
                except CaptureError as e:
                    self._set(state="error", error=str(e), fps=0.0)
                    camera_status.record_error(self.camera_id, str(e))
                finally:
                    if cap is not None:
                        cap.release()
                    lock.release()
                if not self._stop.is_set():
                    self._wait_unless_idle(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF_S)
        finally:
            self._set(state="stopped", fps=0.0)
            self.manager._remove(self)

    def _wait_unless_idle(self, seconds: float) -> None:
        """Wait before retrying a failed camera, but notice within a second if everyone has left
        (a long retry wait would otherwise keep a dead camera's stream around)."""
        deadline = time.monotonic() + seconds
        while not self._stop.is_set() and not self.manager._expire_if_idle(self):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self._stop.wait(min(1.0, remaining))

    def _read_loop(self, cap: cv2.VideoCapture) -> None:
        src_fps = cap.get(cv2.CAP_PROP_FPS)
        # Video files would otherwise be read as fast as the disk allows; play them at their own speed.
        interval = 1 / src_fps if self.kind == "file" and 0 < src_fps < 1000 else 0.0
        next_at = time.monotonic()
        last_report = 0.0
        read_failures = 0

        while not self._stop.is_set() and not self.manager._expire_if_idle(self):
            ok, frame = cap.read()
            if not ok:
                if self.kind == "file" and read_failures < 3:
                    read_failures += 1
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop the video
                    continue
                raise CaptureError("The camera stopped sending frames. Reconnecting…")
            read_failures = 0

            now = time.monotonic()
            self._publish(frame, now)
            with self._lock:
                hooks = list(self._hooks.values())
            for hook in hooks:
                try:
                    hook(frame, now)
                except Exception:  # a broken hook must not stop the video
                    log.exception("Frame hook failed on camera %s", self.camera_id)
            if now - last_report >= STATUS_REPORT_INTERVAL_S:
                camera_status.record_online(self.camera_id, self.width or 0, self.height or 0, round(self.fps, 1) or None)
                last_report = now

            if interval:
                next_at += interval
                delay = next_at - time.monotonic()
                if delay > 0:
                    self._stop.wait(delay)
                else:
                    next_at = time.monotonic()

    def _publish(self, frame: np.ndarray, now: float) -> None:
        with self._lock:
            # Frames actually delivered over the last few seconds (a running average of instant
            # rates spiked when a looping video jumped back to its start).
            self._frame_times.append(now)
            while self._frame_times and now - self._frame_times[0] > FPS_WINDOW_S:
                self._frame_times.popleft()
            span = self._frame_times[-1] - self._frame_times[0]
            if len(self._frame_times) >= 2 and span > 0:
                self.fps = (len(self._frame_times) - 1) / span
            self._frame, self._frame_at = frame, now
            self.height, self.width = frame.shape[:2]
            self.state, self.error = "live", None
            # Encode while someone watches: an open MJPEG stream (viewers > 0) or a recent frame poll.
            watched = self.viewers > 0 or now - self.last_viewer_at <= POLL_VIEWER_S
            want_jpeg = watched and now - self._jpeg_at >= 1 / settings.stream_max_fps
        if want_jpeg:
            jpeg = encode_jpeg(frame, settings.stream_max_width, settings.stream_jpeg_quality)
            with self._lock:
                self._jpeg, self._jpeg_id, self._jpeg_at = jpeg, self._jpeg_id + 1, now

    def _set(self, **fields) -> None:
        with self._lock:
            for k, v in fields.items():
                setattr(self, k, v)


class StreamManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._streams: dict[int, CameraStream] = {}

    def acquire(self, camera_id: int, source: str) -> CameraStream:
        """Join (or start) the camera's stream as a viewer. Pair with release()."""
        with self._lock:
            stream = self._streams.get(camera_id)
            if stream and (stream.stopped or stream.source != source):
                stream.stop()
                stream = None
            if stream is None:
                stream = CameraStream(self, camera_id, source)
                self._streams[camera_id] = stream
                stream.start()
            stream.viewers += 1
            stream.last_viewer_at = time.monotonic()
            return stream

    def release(self, stream: CameraStream) -> None:
        with self._lock:
            stream.viewers = max(0, stream.viewers - 1)
            stream.last_viewer_at = time.monotonic()

    def get(self, camera_id: int) -> CameraStream | None:
        with self._lock:
            return self._streams.get(camera_id)

    def find_by_source(self, source: str) -> CameraStream | None:
        with self._lock:
            return next((s for s in self._streams.values() if s.source == source), None)

    def all(self) -> list[CameraStream]:
        with self._lock:
            return list(self._streams.values())

    def stop(self, camera_id: int) -> None:
        with self._lock:
            stream = self._streams.pop(camera_id, None)
        if stream:
            stream.stop()

    def stop_all(self) -> None:
        with self._lock:
            streams, self._streams = list(self._streams.values()), {}
        for s in streams:
            s.stop()

    def _expire_if_idle(self, stream: CameraStream) -> bool:
        """Called from the reader thread. True if the stream should shut down."""
        with self._lock:
            if stream.stopped:
                return True
            # Tiles poll a failing camera only every few seconds (vs ~5x a second when live): give it
            # at least NOT_LIVE_GRACE_S, or it would be dropped between polls and lose its error message.
            idle_after = settings.stream_idle_timeout_s if stream.state == "live" else max(settings.stream_idle_timeout_s, NOT_LIVE_GRACE_S)
            if stream.viewers == 0 and time.monotonic() - stream.last_viewer_at > idle_after:
                stream.stop()
                if self._streams.get(stream.camera_id) is stream:
                    del self._streams[stream.camera_id]
                return True
            return False

    def _remove(self, stream: CameraStream) -> None:
        with self._lock:
            if self._streams.get(stream.camera_id) is stream:
                del self._streams[stream.camera_id]


streams = StreamManager()


def grab(source: str) -> Grab:
    """One frame from a source: the live stream's newest frame if it is streaming (a webcam can't be
    opened twice), otherwise open the source briefly. Raises CaptureError."""
    stream = streams.find_by_source(source)
    frame = stream.latest_frame() if stream else None
    if frame is not None:
        height, width = frame.shape[:2]
        return Grab(frame=frame, width=width, height=height, fps=round(stream.fps, 1) or None, latency_ms=0)
    return grab_frame(source)
