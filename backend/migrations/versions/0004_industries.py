"""Industries: each camera and event belongs to an industry; one industry is active at a time.

Existing cameras and events were all restaurant ones.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cameras") as batch:
        batch.add_column(sa.Column("industry", sa.String(32), nullable=False, server_default="restaurant"))
        batch.create_index("ix_cameras_industry", ["industry"])
    with op.batch_alter_table("events") as batch:
        batch.add_column(sa.Column("industry", sa.String(32), nullable=False, server_default="restaurant"))
        batch.create_index("ix_events_industry", ["industry"])
    with op.batch_alter_table("app_settings") as batch:
        batch.add_column(sa.Column("active_industry", sa.String(32), nullable=False, server_default="restaurant"))


def downgrade() -> None:
    with op.batch_alter_table("app_settings") as batch:
        batch.drop_column("active_industry")
    with op.batch_alter_table("events") as batch:
        batch.drop_index("ix_events_industry")
        batch.drop_column("industry")
    with op.batch_alter_table("cameras") as batch:
        batch.drop_index("ix_cameras_industry")
        batch.drop_column("industry")
