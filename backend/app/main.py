from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import require_user
from app.config import settings
from app.db import get_db, init_db
from app.detection.service import detection as detection_service
from app.routers import auth, cameras, counts, dashboard, detection, events, industries, reports, settings as settings_router, streams, system, zones
from app.services.industry import check_lock_setting
from app.services.streams import streams as stream_manager


@asynccontextmanager
async def lifespan(_: FastAPI):
    check_lock_setting()
    init_db()
    detection_service.start()  # idle until a camera has detection switched on
    yield
    detection_service.stop()
    stream_manager.stop_all()  # release webcams / network cameras


app = FastAPI(title="VigilSiddhi API", description="VigilSiddhi – A Vision AI Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes: health check and login only.
public = APIRouter(prefix="/api")


@public.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


public.include_router(auth.router)
public.include_router(industries.public_router)  # the login page lists industries before signing in

# Every router included here requires a valid login token.
protected = APIRouter(prefix="/api", dependencies=[Depends(require_user)])
protected.include_router(system.router)
protected.include_router(cameras.router)
protected.include_router(streams.router)
protected.include_router(events.router)
protected.include_router(dashboard.router)
protected.include_router(detection.router)
protected.include_router(zones.router)
protected.include_router(reports.router)
protected.include_router(settings_router.router)
protected.include_router(industries.router)
protected.include_router(counts.router)

app.include_router(public)
app.include_router(protected)
