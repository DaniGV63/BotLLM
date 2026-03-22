"""Helper compartido: obtiene credenciales OAuth2 de Google para un tenant."""

import asyncio
import uuid
from datetime import datetime, timezone

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


def _to_naive_utc(dt: datetime) -> datetime:
    """Convierte a naive UTC (lo que google-auth espera internamente)."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _to_aware_utc(dt: datetime) -> datetime:
    """Convierte a aware UTC (lo que PostgreSQL TIMESTAMPTZ espera)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def get_google_creds(tenant_id: uuid.UUID) -> tuple[Credentials, Tenant]:
    """Devuelve credenciales OAuth2 validas para el tenant.

    Refresca el access_token si ha expirado y persiste tokens actualizados.
    Maneja rotacion de refresh_token de Google.

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
    )

    # Restaurar expiry como naive UTC (google-auth compara con utcnow() naive)
    if tenant.google_token_expiry:
        creds.expiry = _to_naive_utc(tenant.google_token_expiry)

    # Refrescar si expirado o sin expiry (primera vez tras subir tokens)
    if not creds.valid or creds.expiry is None:
        log.info("google_token_refresh_start")
        await asyncio.to_thread(creds.refresh, Request())
        log.info("google_token_refreshed")

        # Persistir tokens actualizados (incluido refresh_token por rotacion)
        async with SessionLocal() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            t = result.scalar_one()
            t.google_access_token = encrypt(creds.token)
            if creds.refresh_token:
                t.google_refresh_token = encrypt(creds.refresh_token)
            if creds.expiry:
                t.google_token_expiry = _to_aware_utc(creds.expiry)
            await session.commit()

        # Refrescar objeto tenant para el caller
        async with SessionLocal() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.id == tenant_id)
            )
            tenant = result.scalar_one()

    return creds, tenant
