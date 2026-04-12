"""add derivation timeout fields

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-04-12
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a1b2c3d4"
down_revision = "d4e5f6a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Dos timeouts separados en tenants
    op.add_column(
        "tenants",
        sa.Column(
            "derivation_timeout_no_reply_minutes",
            sa.Integer(),
            nullable=False,
            server_default="480",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "derivation_timeout_after_reply_minutes",
            sa.Integer(),
            nullable=False,
            server_default="120",
        ),
    )
    # Timestamp de inicio de derivacion en conversations
    op.add_column(
        "conversations",
        sa.Column(
            "derivation_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "derivation_timeout_no_reply_minutes")
    op.drop_column("tenants", "derivation_timeout_after_reply_minutes")
    op.drop_column("conversations", "derivation_started_at")
