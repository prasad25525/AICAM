import asyncio

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.db import SessionLocal
from app.models import Camera
from app.services.capture import encode_jpeg
from app.services.streams import streams

router = APIRouter(tags=["live"])

BOUNDARY = "frame"


class StreamInfo(BaseModel):
    camera_id: int
    state: str  # connecting | live | error | stopped
    error: str | None
    fps: float
    width: int | None
    height: int | None
    viewers: int


@router.get("/streams", response_model=list[StreamInfo])
def list_streams():
    """Currently open camera streams (cameras with at least one recent viewer)."""
    return [s.info() for s in streams.all()]


FRAME_WAIT_S = 8.0  # first request may have to open the camera


def _enabled_source(camera_id: int) -> str:
    with SessionLocal() as db:
        camera = db.get(Camera, camera_id)
        if not camera:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
        if not camera.enabled:
            raise HTTPException(status.HTTP_409_CONFLICT, "Camera is disabled")
        return camera.source_url


@router.get("/cameras/{camera_id}/frame", response_class=Response, responses={200: {"content": {"image/jpeg": {}}}})
async def camera_frame(camera_id: int):
    """The newest live frame as a single JPEG. For grids of many cameras: each request is short, so
    it doesn't hold one of the browser's ~6 connections per server the way an MJPEG stream does.
    Keeps the camera open while it is being polled (released after the idle timeout).
    Authenticate with ?token= (media token)."""
    source = _enabled_source(camera_id)
    stream = streams.acquire(camera_id, source)
    try:
        deadline = asyncio.get_running_loop().time() + FRAME_WAIT_S
        while (jpeg := stream.fresh_jpeg()) is None and (frame := stream.latest_frame()) is None:
            if stream.stopped or asyncio.get_running_loop().time() > deadline:
                raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, stream.info()["error"] or "No video from this camera yet")
            await asyncio.sleep(0.1)
        if jpeg is None:  # first poll: the reader hasn't encoded one yet
            jpeg = await asyncio.to_thread(encode_jpeg, frame, settings.stream_max_width, settings.stream_jpeg_quality)
    finally:
        streams.release(stream)
    return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get(
    "/cameras/{camera_id}/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {f"multipart/x-mixed-replace; boundary={BOUNDARY}": {}}}},
)
async def camera_stream(
    camera_id: int,
    request: Request,
    limit: int | None = Query(None, ge=1, description="Stop after this many frames (for tests / thumbnails)"),
):
    """Live MJPEG stream for <img src>. Authenticate with ?token= from POST /api/auth/media-token."""
    # Not using the get_db dependency: its session would stay open for the whole stream.
    with SessionLocal() as db:
        camera = db.get(Camera, camera_id)
        if not camera:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
        if not camera.enabled:
            raise HTTPException(status.HTTP_409_CONFLICT, "Camera is disabled")
        source = camera.source_url

    stream = streams.acquire(camera_id, source)
    poll_s = 1 / (settings.stream_max_fps * 2)

    async def frames():
        sent, last_id = 0, 0
        try:
            while not stream.stopped:
                jpeg, jpeg_id = stream.latest_jpeg()
                if jpeg is not None and jpeg_id != last_id:
                    last_id = jpeg_id
                    yield (
                        f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n".encode()
                        + jpeg
                        + b"\r\n"
                    )
                    sent += 1
                    if limit and sent >= limit:
                        break
                if await request.is_disconnected():
                    break
                await asyncio.sleep(poll_s)
        finally:
            streams.release(stream)

    return StreamingResponse(
        frames(),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
