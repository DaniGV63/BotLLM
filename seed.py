"""Seed: crea el primer tenant en la base de datos."""

import asyncio
import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.tenant import Tenant

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin_temporal_2024"

PRIMER_TENANT = {
    "slug": "fisio-cliente",
    "nombre_negocio": "[COMPLETAR]",
    "email_notificaciones": "[COMPLETAR]",
    "whatsapp_phone_number_id": "1023364914199630",
    "whatsapp_verify_token": str(uuid.uuid4()),
    "bot_activo": True,
    "admin_username": ADMIN_USERNAME,
    "admin_password_hash": hash_password(ADMIN_PASSWORD),
}


async def seed() -> None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.slug == PRIMER_TENANT["slug"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            if not existing.admin_username:
                existing.admin_username = PRIMER_TENANT["admin_username"]
                existing.admin_password_hash = PRIMER_TENANT["admin_password_hash"]
                await session.commit()
                print(f"Tenant '{existing.slug}' actualizado con credenciales admin.")
            else:
                print(f"Tenant '{existing.slug}' ya existe con admin configurado.")
        else:
            tenant = Tenant(**PRIMER_TENANT)
            session.add(tenant)
            await session.commit()
            await session.refresh(tenant)
            print(f"Tenant creado: slug='{tenant.slug}' id={tenant.id}")

        print(f"\n  Admin username: {ADMIN_USERNAME}")
        print(f"  Admin password: {ADMIN_PASSWORD}")
        print("  IMPORTANTE: Cambia la contrasena por defecto en produccion.\n")


if __name__ == "__main__":
    asyncio.run(seed())
