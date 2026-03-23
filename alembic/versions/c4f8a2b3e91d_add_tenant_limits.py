"""add tenant limits (rate_limit_per_minute, max_citas_activas)

Revision ID: c4f8a2b3e91d
Revises: 952d9ada3e6d
Create Date: 2026-03-23 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4f8a2b3e91d"
down_revision: Union[str, None] = "952d9ada3e6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column(
        "tenants",
        sa.Column("max_citas_activas", sa.Integer(), nullable=False, server_default="5"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "max_citas_activas")
    op.drop_column("tenants", "rate_limit_per_minute")
