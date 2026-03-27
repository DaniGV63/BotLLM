"""rename DESPEDIDA to INACTIVA in conversation estado

Revision ID: e1f2a3b4c5d6
Revises: d5e9b3c7f12a
Create Date: 2026-03-27

"""
from alembic import op

revision = "e1f2a3b4c5d6"
down_revision = "d5e9b3c7f12a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE conversations SET estado = 'INACTIVA' WHERE estado = 'DESPEDIDA'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE conversations SET estado = 'DESPEDIDA' WHERE estado = 'INACTIVA'"
    )
