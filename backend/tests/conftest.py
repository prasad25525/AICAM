import os
import sys
import tempfile
from pathlib import Path

import pytest

# Point the app at a throwaway database before anything imports app.config.
_tmp = Path(tempfile.mkdtemp(prefix="aicam-tests-"))
os.environ["AICAM_DATABASE_URL"] = f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["AICAM_DATA_DIR"] = str(_tmp / "data")  # event snapshots go here, not into backend/data
os.environ["AICAM_DETECTION_ENGINE"] = "fake"  # scripted detections: no GPU or model loading in tests

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR / "scripts"))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DEFAULT_INDUSTRY, AppSettings, Camera, DetectionConfig, Event, ProductionCount  # noqa: E402
from app.services import camera_status  # noqa: E402
from app.services.streams import streams  # noqa: E402
from make_test_video import make_test_video  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def auth(client) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session", autouse=True)
def database():
    """Create the schema (via the migrations) before any test, even pure-logic ones."""
    init_db()


def _reset_state() -> None:
    """Database rows and in-memory state, so nothing from one test shows up in the next. Camera ids
    are reused after a reset, so a lingering video stream or remembered online/offline status
    would otherwise land on the next test's camera."""
    streams.stop_all()
    camera_status.clear()
    with SessionLocal() as db:
        db.execute(delete(Event))
        db.execute(delete(DetectionConfig))
        db.execute(delete(ProductionCount))
        db.execute(delete(Camera))
        if (row := db.get(AppSettings, 1)) is not None:
            row.active_industry = DEFAULT_INDUSTRY
        db.commit()


@pytest.fixture(autouse=True)
def clean_db(database):
    yield
    _reset_state()
    camera_status.clear()  # again: a stream thread may have reported once more while stopping


@pytest.fixture(scope="session")
def test_video() -> str:
    return make_test_video(_tmp / "test_pattern.mp4").as_posix()
