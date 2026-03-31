"""add derivation and wa fields

Revision ID: a1b2c3d4e5f6
Revises: f7a1b2c3d4e5
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f7a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # tenants: wa_personal_phone + derivation_timeout_minutes
    op.add_column("tenants", sa.Column("wa_personal_phone", sa.String(20), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("derivation_timeout_minutes", sa.Integer(), nullable=False, server_default="60"),
    )

    # admin_users: wa_personal_phone
    op.add_column("admin_users", sa.Column("wa_personal_phone", sa.String(20), nullable=True))

    # messages: sender_name
    op.add_column("messages", sa.Column("sender_name", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("messages", "sender_name")
    op.drop_column("admin_users", "wa_personal_phone")
    op.drop_column("tenants", "derivation_timeout_minutes")
    op.drop_column("tenants", "wa_personal_phone")
