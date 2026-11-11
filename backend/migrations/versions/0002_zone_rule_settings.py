"""Zone-rule settings per camera: hand-wash duration, how long a wash counts, table clearing time.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-30
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("detection_configs") as batch:
        batch.add_column(sa.Column("handwash_min_s", sa.Float(), nullable=False, server_default="20"))
        batch.add_column(sa.Column("wash_valid_min", sa.Float(), nullable=False, server_default="30"))
        batch.add_column(sa.Column("table_clear_min", sa.Float(), nullable=False, server_default="10"))


def downgrade() -> None:
    with op.batch_alter_table("detection_configs") as batch:
        batch.drop_column("table_clear_min")
        batch.drop_column("wash_valid_min")
        batch.drop_column("handwash_min_s")
