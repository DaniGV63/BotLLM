"""Seed: crea tenant demo + super admin + tenant admin inicial."""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.admin_user import AdminRole, AdminUser
from app.models.tenant import Tenant

SUPER_ADMIN_USERNAME = os.environ.get("SUPER_ADMIN_USERNAME", "superadmin")
SUPER_ADMIN_PASSWORD = os.environ.get("SUPER_ADMIN_PASSWORD", "")

TENANT_ADMIN_USERNAME = os.environ.get("TENANT_ADMIN_USERNAME", "demo")
TENANT_ADMIN_PASSWORD = os.environ.get("TENANT_ADMIN_PASSWORD", "")

if not SUPER_ADMIN_PASSWORD:
    raise RuntimeError("SUPER_ADMIN_PASSWORD no está configurada. Exporta la variable antes de ejecutar seed.py")
if not TENANT_ADMIN_PASSWORD:
    raise RuntimeError("TENANT_ADMIN_PASSWORD no está configurada. Exporta la variable antes de ejecutar seed.py")

PRIMER_TENANT = {
    "slug": "demo",
    "nombre_negocio": "Clínica Demo Atendoo",
    "email_notificaciones": os.environ.get("TENANT_EMAIL", "atendoo.app@gmail.com"),
    "whatsapp_phone_number_id": os.environ.get("WA_PHONE_NUMBER_ID", ""),
    "whatsapp_verify_token": str(uuid.uuid4()),
    "bot_activo": True,
    "plan": "FREE_TRIAL",
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

        if not tenant.plan_expires_at:
            tenant.plan = "FREE_TRIAL"
            tenant.plan_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            await session.commit()

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
    print(f"  Super admin:  {SUPER_ADMIN_USERNAME} / (ver SUPER_ADMIN_PASSWORD)")
    print(f"  Tenant admin: {TENANT_ADMIN_USERNAME} / (ver TENANT_ADMIN_PASSWORD)")
    print(f"  Verify token: {PRIMER_TENANT['whatsapp_verify_token']}")
    print("  Guarda el verify token — lo necesitarás al configurar el webhook en Meta.\n")


if __name__ == "__main__":
    asyncio.run(seed())
