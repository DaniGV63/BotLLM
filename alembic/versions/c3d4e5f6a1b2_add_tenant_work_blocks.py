"""add tenant work_blocks and slot_duration_minutes

Revision ID: c3d4e5f6a1b2
Revises: b2c3d4e5f6a1
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "c3d4e5f6a1b2"
down_revision = "b2c3d4e5f6a1"
branch_labels = None
depends_on = None

DEFAULT_WORK_BLOCKS = '{"0":[["09:00","14:00"],["16:00","20:30"]],"1":[["09:00","14:00"],["16:00","20:30"]],"2":[["09:00","14:00"],["16:00","20:30"]],"3":[["09:00","14:00"],["16:00","20:30"]],"4":[["09:00","15:00"]]}'


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "work_blocks",
            JSONB,
            nullable=False,
            server_default=DEFAULT_WORK_BLOCKS,
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "slot_duration_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "slot_duration_minutes")
    op.drop_column("tenants", "work_blocks")
