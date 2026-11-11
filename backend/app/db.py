from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

is_sqlite = settings.database_url.startswith("sqlite")
if is_sqlite:
    settings.data_dir.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if is_sqlite else {},
)

if is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")  # enforce ON DELETE rules
        cur.execute("PRAGMA journal_mode=WAL")  # detection workers write while the API reads
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


BASELINE_REVISION = "0001"


def init_db() -> None:
    """Bring the database schema up to date with the migrations in backend/migrations."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_dir / "migrations"))

    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        tables = set(inspect(conn).get_table_names())
        if "cameras" in tables and "alembic_version" not in tables:
            # Created before migrations existed: it already matches the baseline.
            command.stamp(cfg, BASELINE_REVISION)
        command.upgrade(cfg, "head")
