from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_prefix="AICAM_")

    # Hardcoded single login (override with AICAM_ADMIN_USERNAME / AICAM_ADMIN_PASSWORD in .env)
    admin_username: str = "admin"
    admin_password: str = "admin123"

    # Used to sign login tokens. Change this before deploying anywhere.
    secret_key: str = "change-me-aicam-dev-secret"
    token_expire_minutes: int = 12 * 60

    host: str = "127.0.0.1"
    port: int = 8000

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    models_dir: Path = BASE_DIR / "models"

    # Live view (MJPEG)
    stream_max_fps: float = 15
    stream_max_width: int = 960
    stream_jpeg_quality: int = 75
    stream_idle_timeout_s: float = 10  # close the camera this long after the last viewer leaves
    media_token_minutes: int = 5  # short-lived token for <img src> URLs (streams, event images)

    # Detection
    detection_engine: str = "ppe"  # "ppe" (pose + SigLIP) or "fake" (scripted results, for tests and demos)
    fake_violations: list[str] = ["no_mask"]  # checks the fake engine reports as violated
    fake_person_box: list[float] | None = None  # fake person position [x0, y0, x1, y1] as fractions; None = centre
    fake_objects: list[list] = []  # fake tableware: [[label, x0, y0, x1, y1], ...] as fractions
    fake_zone_hits: list[str] = []  # image zone rules (e.g. "conveyor_spillage") the fake engine sees a problem for
    present_threshold: float = 0.6  # P(item present) above this = wearing it
    absent_threshold: float = 0.3  # below this = not wearing it; in between = unknown

    # Industry: a customer installation is locked to its industry (e.g. AICAM_INDUSTRY_LOCK=cement),
    # which hides the industry tabs. Unset = any industry can be chosen at login (demo laptops).
    industry_lock: str | None = None

    # SQLite by default; set AICAM_DATABASE_URL to a postgresql+psycopg2://... URL to switch.
    data_dir: Path = BASE_DIR / "data"
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'aicam.db').as_posix()}"


settings = Settings()
