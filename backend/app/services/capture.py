"""Grab single frames from webcams, RTSP/HTTP streams and video files, with hard timeouts."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass

import cv2
import numpy as np

from app.schemas import mask_source, source_type
from app.services.rtsp_probe import diagnose

log = logging.getLogger(__name__)

cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)

STREAM_TIMEOUT_MS = 6000  # OpenCV/FFmpeg open + read timeout for network streams (the CP Plus over TLS needs ~2 s)
GRAB_TIMEOUT_S = 35  # overall guard (open + read timeouts, plus the failure diagnosis), in case a driver ignores the timeouts above
# Webcam auto-exposure needs ~2-4s after opening; read until brightness is steady or the time is up.
WEBCAM_WARMUP_MIN_FRAMES = 5
WEBCAM_WARMUP_MAX_S = 2.5
WEBCAM_STEADY_WINDOW = 8  # frames
WEBCAM_STEADY_DELTA = 2.0  # mean brightness change (0-255) across the window


class CaptureError(Exception):
    pass


@dataclass
class Grab:
    frame: np.ndarray
    width: int
    height: int
    fps: float | None
    latency_ms: int


# A webcam can only be opened once at a time, so grabs of the same source are serialised.
_source_locks: dict[str, threading.Lock] = {}
_source_locks_guard = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="grab")


def lock_for(source: str) -> threading.Lock:
    """Held by whoever has the source open (a one-off grab or a live stream).

    Only webcams need this: a webcam can be opened by one reader at a time. Video files and
    network streams can be opened by several readers at once (e.g. two cameras on the same RTSP
    URL with different zones), so they get a fresh, uncontended lock."""
    if source_type(source) != "webcam":
        return threading.Lock()
    with _source_locks_guard:
        return _source_locks.setdefault(source, threading.Lock())


def open_capture(source: str) -> cv2.VideoCapture:
    kind = source_type(source)
    if kind == "webcam":
        return cv2.VideoCapture(int(source), cv2.CAP_DSHOW)
    if kind in ("rtsp", "http"):
        return cv2.VideoCapture(
            source,
            cv2.CAP_FFMPEG,
            [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, STREAM_TIMEOUT_MS, cv2.CAP_PROP_READ_TIMEOUT_MSEC, STREAM_TIMEOUT_MS],
        )
    return cv2.VideoCapture(source)


def open_error(source: str) -> str:
    kind = source_type(source)
    if kind == "webcam":
        return f"Webcam {source} could not be opened. It may be unplugged or in use by another app (Zoom, Teams, Camera)."
    if kind == "rtsp":
        try:
            reason = diagnose(source)
        except Exception:  # noqa: BLE001 - the probe is a best-effort explanation
            reason = None
        if reason:
            log.warning("Camera %s: %s", mask_source(source), reason)
            return reason
    if kind in ("rtsp", "http"):
        return "Could not connect to the stream. Check the address, username/password, and that the camera is reachable from this machine."
    return "Could not open the video file. It may be missing or in an unsupported format."


def _read_one(cap: cv2.VideoCapture) -> np.ndarray | None:
    ok, frame = cap.read()
    return frame if ok else None


def _read_webcam_settled(cap: cv2.VideoCapture) -> np.ndarray | None:
    frame, brightness = None, []
    deadline = time.perf_counter() + WEBCAM_WARMUP_MAX_S
    while time.perf_counter() < deadline:
        ok, f = cap.read()
        if not ok:
            continue
        frame = f
        brightness.append(float(f.mean()))
        window = brightness[-WEBCAM_STEADY_WINDOW:]
        if len(brightness) >= max(WEBCAM_WARMUP_MIN_FRAMES, WEBCAM_STEADY_WINDOW) and max(window) - min(window) < WEBCAM_STEADY_DELTA:
            break
    return frame


def _grab(source: str) -> Grab:
    with lock_for(source):
        start = time.perf_counter()
        cap = open_capture(source)
        try:
            if not cap.isOpened():
                raise CaptureError(open_error(source))
            frame = _read_webcam_settled(cap) if source_type(source) == "webcam" else _read_one(cap)
            if frame is None:
                raise CaptureError("Connected, but no video frame was received.")
            fps = cap.get(cv2.CAP_PROP_FPS)
            height, width = frame.shape[:2]
            return Grab(
                frame=frame,
                width=width,
                height=height,
                fps=round(fps, 1) if fps and 0 < fps < 1000 else None,
                latency_ms=int((time.perf_counter() - start) * 1000),
            )
        finally:
            cap.release()


def grab_frame(source: str) -> Grab:
    """Open the source, read one frame, close it. Raises CaptureError on failure or timeout."""
    future = _executor.submit(_grab, source)
    try:
        return future.result(timeout=GRAB_TIMEOUT_S)
    except FutureTimeout:
        raise CaptureError(f"Timed out after {GRAB_TIMEOUT_S}s waiting for a frame.") from None


def encode_jpeg(frame: np.ndarray, max_width: int = 1280, quality: int = 85) -> bytes:
    height, width = frame.shape[:2]
    if width > max_width:
        frame = cv2.resize(frame, (max_width, int(height * max_width / width)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise CaptureError("Could not encode the frame as JPEG.")
    return buf.tobytes()
