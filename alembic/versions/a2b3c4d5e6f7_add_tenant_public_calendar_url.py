"""add public_calendar_url to tenants

Revision ID: a2b3c4d5e6f7
Revises: f6a1b2c3d4e5
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f7"
down_revision = "f6a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("public_calendar_url", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "public_calendar_url")
