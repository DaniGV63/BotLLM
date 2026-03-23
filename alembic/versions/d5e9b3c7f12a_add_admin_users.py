"""add admin_users table, migrate admin credentials from tenants

Revision ID: d5e9b3c7f12a
Revises: c4f8a2b3e91d
Create Date: 2026-03-24 00:00:00.000000

Crea tabla admin_users con roles SUPER_ADMIN / TENANT_ADMIN.
Migra admin_username/admin_password_hash existentes como tenant_admin.
Elimina columnas admin_* de tenants.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "d5e9b3c7f12a"
down_revision: Union[str, None] = "c4f8a2b3e91d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Migrar credenciales existentes de tenants → admin_users como tenant_admin
    op.execute(
        """
        INSERT INTO admin_users (id, tenant_id, username, password_hash, role, email)
        SELECT
            gen_random_uuid(),
            id,
            admin_username,
            admin_password_hash,
            'tenant_admin',
            email_notificaciones
        FROM tenants
        WHERE admin_username IS NOT NULL
          AND admin_password_hash IS NOT NULL
        """
    )

    op.drop_column("tenants", "admin_username")
    op.drop_column("tenants", "admin_password_hash")


def downgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("admin_username", sa.String(100), unique=True, nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("admin_password_hash", sa.String(200), nullable=True),
    )
    # Restaurar datos (best effort — solo los tenant_admin)
    op.execute(
        """
        UPDATE tenants t
        SET admin_username = au.username,
            admin_password_hash = au.password_hash
        FROM admin_users au
        WHERE au.tenant_id = t.id
          AND au.role = 'tenant_admin'
        """
    )
    op.drop_table("admin_users")
