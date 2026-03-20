"""Seed: crea el primer tenant en la base de datos."""

import asyncio
import uuid

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.tenant import Tenant

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
        result = await session.execute(
            select(Tenant).where(Tenant.slug == PRIMER_TENANT["slug"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Tenant '{PRIMER_TENANT['slug']}' ya existe (id={existing.id}). Sin cambios.")
            return

        tenant = Tenant(**PRIMER_TENANT)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        print(f"Tenant creado: slug='{tenant.slug}' id={tenant.id}")


if __name__ == "__main__":
    asyncio.run(seed())
