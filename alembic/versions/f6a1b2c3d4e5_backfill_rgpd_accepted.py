"""backfill rgpd_accepted for existing conversations

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2026-04-12
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a1b2c3d4e5"
down_revision = "e5f6a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Las conversaciones con al menos 1 mensaje ya interactuaron → aceptaron RGPD.
    # Se marcan como aceptadas para no volver a pedirles el aviso.
    op.execute(
        """
        UPDATE conversations
        SET rgpd_accepted = TRUE
        WHERE rgpd_accepted = FALSE
          AND id IN (
              SELECT DISTINCT conversation_id FROM messages
          )
        """
    )


def downgrade() -> None:
    # No se puede revertir el backfill de forma fiable — no hacer nada
    pass
