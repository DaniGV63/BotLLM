"""Helper compartido: obtiene credenciales OAuth2 de Google para un tenant."""

import asyncio
import uuid
from datetime import timezone

import structlog
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decrypt, encrypt
from app.models.tenant import Tenant

logger = structlog.get_logger()

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
]


async def get_google_creds(tenant_id: uuid.UUID) -> tuple[Credentials, Tenant]:
    """Devuelve credenciales OAuth2 validas para el tenant.

    Refresca el access_token si ha expirado y persiste el nuevo en BD.

    Returns:
        (Credentials, Tenant) — credenciales listas para usar + objeto tenant.

    Raises:
        ValueError: si el tenant no existe o no tiene tokens configurados.
    """
    log = logger.bind(tenant_id=str(tenant_id))

    async with SessionLocal() as session:
        result = await session.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()

    if not tenant:
        raise ValueError(f"Tenant {tenant_id} no encontrado")
    if not tenant.google_access_token or not tenant.google_refresh_token:
        raise ValueError(
            f"Tenant {tenant_id} no tiene credenciales Google configuradas"
        )

    creds = Credentials(
        token=decrypt(tenant.google_access_token),
        refresh_token=decrypt(tenant.google_refresh_token),
        token_uri=GOOGLE_TOKEN_URI,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=GOOGLE_SCOPES,
    )

    # Restaurar expiry si esta guardado en BD
    if tenant.google_token_expiry:
        expiry = tenant.google_token_expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        creds.expiry = expiry

    # Refrescar si expirado
    if not creds.valid:
        log.info("google_token_refresh_start")
        await asyncio.to_thread(creds.refresh, Request())
        log.info("google_token_refreshed")

        # Persistir nuevo token
        async with SessionLocal() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            t = result.scalar_one()
            t.google_access_token = encrypt(creds.token)
            if creds.expiry:
                expiry = creds.expiry
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                t.google_token_expiry = expiry
            await session.commit()

        # Devolver tenant actualizado (refrescar objeto)
        async with SessionLocal() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one()

    return creds, tenant
