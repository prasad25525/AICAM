"""Production counts per camera and minute (e.g. cement bags passing a counting line).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-23
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "production_counts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True),
        sa.Column("camera_name", sa.String(100), nullable=False),
        sa.Column("industry", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("minute", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_counts_camera_kind_minute", "production_counts", ["camera_id", "kind", "minute"], unique=True)
    op.create_index("ix_production_counts_industry", "production_counts", ["industry"])
    op.create_index("ix_production_counts_minute", "production_counts", ["minute"])


def downgrade() -> None:
    op.drop_table("production_counts")
