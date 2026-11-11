from alembic import context

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.db import Base, engine

target_metadata = Base.metadata


def run_migrations() -> None:
    # Reuse a connection handed over by init_db(), otherwise open one with the app's engine.
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _run(connection)
    else:
        with engine.begin() as conn:
            _run(conn)


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite can't ALTER most things; batch mode rebuilds the table safely
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


run_migrations()
