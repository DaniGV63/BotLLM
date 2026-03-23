"""Seed: crea tenant demo + super admin + tenant admin inicial."""

import asyncio
import os
import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.admin_user import AdminRole, AdminUser
from app.models.tenant import Tenant

SUPER_ADMIN_USERNAME = os.environ.get("SUPER_ADMIN_USERNAME", "superadmin")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "superadmin_temporal_2024")

TENANT_ADMIN_USERNAME = os.environ.get("TENANT_ADMIN_USERNAME", "admin")
TENANT_ADMIN_PASSWORD = os.environ.get("TENANT_ADMIN_PASSWORD", "admin_temporal_2024")

PRIMER_TENANT = {
    "slug": "fisio-cliente",
    "nombre_negocio": "[COMPLETAR]",
    "email_notificaciones": "[COMPLETAR]",
    "whatsapp_phone_number_id": "1023364914199630",
    "whatsapp_verify_token": str(uuid.uuid4()),
    "bot_activo": True,
}


async def seed() -> None:
    async with SessionLocal() as session:
        # --- Tenant demo ---
        result = await session.execute(
            select(Tenant).where(Tenant.slug == PRIMER_TENANT["slug"])
        )
        tenant = result.scalar_one_or_none()

        if not tenant:
            tenant = Tenant(**PRIMER_TENANT)
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
            print(f"Tenant creado: slug='{tenant.slug}' id={tenant.id}")
        else:
            print(f"Tenant '{tenant.slug}' ya existe (id={tenant.id})")

        # --- Super admin ---
        sa_result = await session.execute(
            select(AdminUser).where(AdminUser.username == SUPER_ADMIN_USERNAME)
        )
        if not sa_result.scalar_one_or_none():
            super_admin = AdminUser(
                tenant_id=None,
                username=SUPER_ADMIN_USERNAME,
                password_hash=hash_password(SUPER_ADMIN_PASSWORD),
                role=AdminRole.SUPER_ADMIN,
            )
            session.add(super_admin)
            await session.commit()
            print(f"Super admin creado: username='{SUPER_ADMIN_USERNAME}'")
        else:
            print(f"Super admin '{SUPER_ADMIN_USERNAME}' ya existe")

        # --- Tenant admin para el tenant demo ---
        ta_result = await session.execute(
            select(AdminUser).where(AdminUser.username == TENANT_ADMIN_USERNAME)
        )
        if not ta_result.scalar_one_or_none():
            tenant_admin = AdminUser(
                tenant_id=tenant.id,
                username=TENANT_ADMIN_USERNAME,
                password_hash=hash_password(TENANT_ADMIN_PASSWORD),
                role=AdminRole.TENANT_ADMIN,
            )
            session.add(tenant_admin)
            await session.commit()
            print(f"Tenant admin creado: username='{TENANT_ADMIN_USERNAME}' → tenant '{tenant.slug}'")
        else:
            print(f"Tenant admin '{TENANT_ADMIN_USERNAME}' ya existe")

    print("\n--- Credenciales ---")
    print(f"  Super admin:  {SUPER_ADMIN_USERNAME} / {SUPER_ADMIN_PASSWORD}")
    print(f"  Tenant admin: {TENANT_ADMIN_USERNAME} / {TENANT_ADMIN_PASSWORD}")
    print("  IMPORTANTE: Cambia las contraseñas por defecto en producción.\n")


if __name__ == "__main__":
    asyncio.run(seed())
