"""add tenant plan and features

Revision ID: f7a1b2c3d4e5
Revises: e1f2a3b4c5d6
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "f7a1b2c3d4e5"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("plan", sa.String(20), nullable=False, server_default="SIN_PLAN"))
    op.add_column("tenants", sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("feature_overrides", JSONB(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("tenants", "feature_overrides")
    op.drop_column("tenants", "plan_expires_at")
    op.drop_column("tenants", "plan")
