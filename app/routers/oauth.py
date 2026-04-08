"""Router OAuth: autorización de Google Calendar + Gmail para tenants."""

import secrets
import uuid
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import encrypt
from app.models.tenant import Tenant
from app.routers.admin import TokenData, require_super_admin

router = APIRouter(prefix="/oauth", tags=["oauth"])
logger = structlog.get_logger()

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPES = " ".join([
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
])
_STATE_TTL = 600  # 10 minutos
_STATE_PREFIX = "oauth_state:"


@router.get("/google/start")
async def google_oauth_start(
    tenant_id: uuid.UUID,
    _: TokenData = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Inicia el flujo OAuth de Google para el tenant indicado.

    Requiere JWT de SuperAdmin. Redirige al consent screen de Google.
    """
    # Verificar que el tenant existe
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    # Generar state aleatorio y guardarlo en Redis (single-use, 10min TTL)
    state = secrets.token_urlsafe(32)
    redis = await get_redis()
    await redis.set(f"{_STATE_PREFIX}{state}", str(tenant_id), ex=_STATE_TTL)

    redirect_uri = f"{settings.BASE_URL}/oauth/callback"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": _SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    auth_url = f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"
    logger.info("oauth_google_start", tenant_id=str(tenant_id))
    return RedirectResponse(url=auth_url)


@router.get("/callback", response_class=HTMLResponse)
async def google_oauth_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Callback de Google OAuth. Intercambia code por tokens y los guarda en BD.

    Sin autenticación: Google redirige aquí tras el consent.
    """
    redis = await get_redis()
    redis_key = f"{_STATE_PREFIX}{state}"
    tenant_id_str = await redis.get(redis_key)

    if not tenant_id_str:
        raise HTTPException(status_code=400, detail="State inválido o expirado")

    # Consumir state (single-use)
    await redis.delete(redis_key)
    tenant_id = uuid.UUID(tenant_id_str)

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    # Intercambiar code por tokens
    redirect_uri = f"{settings.BASE_URL}/oauth/callback"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if resp.status_code != 200:
        logger.error(
            "oauth_token_exchange_failed",
            tenant_id=str(tenant_id),
            status=resp.status_code,
            body=resp.text,
        )
        raise HTTPException(status_code=502, detail="Error al obtener tokens de Google")

    tokens = resp.json()
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if not access_token:
        raise HTTPException(status_code=502, detail="Google no devolvió access_token")

    # Guardar tokens encriptados en el tenant
    tenant.google_access_token = encrypt(access_token)
    if refresh_token:
        tenant.google_refresh_token = encrypt(refresh_token)

    await db.commit()
    logger.info("oauth_google_ok", tenant_id=str(tenant_id), slug=tenant.slug)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Google autorizado</title>
<style>
  body{{font-family:system-ui,sans-serif;display:flex;align-items:center;
       justify-content:center;height:100vh;margin:0;background:#f0fdf4}}
  .card{{background:#fff;padding:2rem 3rem;border-radius:1rem;text-align:center;
         box-shadow:0 4px 20px rgba(0,0,0,.08)}}
  h1{{color:#16a34a;margin-bottom:.5rem}}
  p{{color:#6b7280}}
</style>
</head>
<body>
<div class="card">
  <h1>&#10003; Google autorizado</h1>
  <p>Tokens guardados para <strong>{tenant.nombre_negocio}</strong>.</p>
  <p>Puedes cerrar esta pestaña.</p>
</div>
</body>
</html>"""
    return HTMLResponse(content=html)
