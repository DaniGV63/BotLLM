"""Router del webhook de Meta WhatsApp."""

import uuid

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.core.features import has_feature
from app.core.redis import check_rate_limit, get_redis
from app.core.security import decrypt, validate_meta_signature
from app.models.message import Message
from app.models.tenant import Tenant
from app.services.agent import handle_message
from app.services.wa_bridge_service import handle_therapist_message, is_therapist_phone
from app.services.whatsapp_service import (
    get_tenant_by_phone_number_id,
    parse_incoming_webhook,
    parse_status_update,
    send_text,
)

router = APIRouter(tags=["webhook"])
logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# GET /webhook — Verificación de Meta
# ---------------------------------------------------------------------------


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Meta envía GET para verificar el webhook. Devolver challenge si token OK."""
    if hub_mode != "subscribe":
        return Response(status_code=403)

    result = await db.execute(
        select(Tenant).where(
            Tenant.whatsapp_verify_token == hub_verify_token,
            Tenant.activo.is_(True),
        )
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        logger.warning("webhook_verify_failed", verify_token=hub_verify_token)
        return Response(status_code=403)

    logger.info("webhook_verified", tenant_id=str(tenant.id))
    return Response(content=hub_challenge, media_type="text/plain")


# ---------------------------------------------------------------------------
# POST /webhook — Recepción de mensajes
# ---------------------------------------------------------------------------


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Recibe webhooks de Meta. Siempre devuelve 200 (Meta reintenta non-200)."""
    raw_body = await request.body()
    body = await request.json()

    # --- Intentar parsear como mensaje ---
    parsed = parse_incoming_webhook(body)

    if parsed is None:
        # Puede ser un status update (delivered/read/sent)
        status_data = parse_status_update(body)
        if status_data:
            background_tasks.add_task(process_status_update, status_data)
        return {"status": "ok"}

    phone_number_id = parsed["phone_number_id"]
    wa_message_id = parsed["wa_message_id"]
    log = logger.bind(
        phone_number_id=phone_number_id,
        wa_phone=parsed["wa_phone"],
        wa_message_id=wa_message_id,
    )

    # --- Buscar tenant ---
    tenant = await get_tenant_by_phone_number_id(phone_number_id, db)
    if not tenant:
        log.warning("unknown_phone_number_id")
        return {"status": "ok"}

    log = log.bind(tenant_id=str(tenant.id))

    # --- Validar HMAC ---
    signature = request.headers.get("X-Hub-Signature-256", "")
    app_secret = ""
    if tenant.meta_app_secret:
        app_secret = decrypt(tenant.meta_app_secret)
    elif settings.META_APP_SECRET:
        app_secret = settings.META_APP_SECRET

    if app_secret and signature:
        if not validate_meta_signature(raw_body, signature, app_secret):
            log.warning("invalid_hmac_signature")
            return {"status": "ok"}
    elif not app_secret:
        log.warning("no_app_secret_configured_skipping_hmac")

    # --- Bot inactivo: ignorar sin responder ---
    if not tenant.bot_activo:
        log.info("bot_inactive_message_ignored")
        return {"status": "ok"}

    # --- Deduplicar via Redis (TTL 5 min) ---
    redis = await get_redis()
    dedup_key = f"dedup:{wa_message_id}"
    was_set = await redis.set(dedup_key, "1", nx=True, ex=300)
    if not was_set:
        log.info("duplicate_message")
        return {"status": "ok"}

    # --- Rate limiting por paciente ---
    rate_key = f"rate:{tenant.id}:{parsed['wa_phone']}"
    if await check_rate_limit(rate_key, limit=tenant.rate_limit_per_minute or 10):
        log.warning("rate_limit_exceeded", wa_phone=parsed["wa_phone"])
        return {"status": "ok"}

    # --- Encolar procesamiento en background ---
    log.info("webhook_received", message_type=parsed["message_type"])
    background_tasks.add_task(process_incoming_message, tenant.id, parsed)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------


async def process_incoming_message(
    tenant_id: uuid.UUID, parsed: dict
) -> None:
    """Procesa mensaje entrante: no-texto responde directo, texto va al agente."""
    log = logger.bind(
        tenant_id=str(tenant_id), wa_phone=parsed["wa_phone"]
    )

    async with SessionLocal() as db:
        try:
            message_type = parsed["message_type"]
            log.info(
                "processing_message",
                message_type=message_type,
                wa_message_id=parsed["wa_message_id"],
            )

            # Mensajes no-texto: respuesta fija sin LLM
            if message_type != "text":
                reply = (
                    "Solo puedo leer mensajes de texto. "
                    "Por favor, escribe tu mensaje."
                )
                await send_text(tenant_id, parsed["wa_phone"], reply, db)
                return

            # Detectar si el remitente es el fisio (WA bridge)
            tenant_obj = await db.get(Tenant, tenant_id)
            if tenant_obj and await has_feature(tenant_id, "handoff.wa_bridge", db):
                if await is_therapist_phone(parsed["wa_phone"], tenant_obj, db):
                    reply = await handle_therapist_message(
                        wa_phone_fisio=parsed["wa_phone"],
                        text=parsed["text"],
                        tenant=tenant_obj,
                        db=db,
                    )
                    if reply:
                        await send_text(tenant_id, parsed["wa_phone"], reply, db)
                    return

            # Mensajes de texto: delegar al agente
            await handle_message(
                tenant_id=tenant_id,
                wa_phone=parsed["wa_phone"],
                message_text=parsed["text"],
                wa_message_id=parsed["wa_message_id"],
                db=db,
            )

            log.info("message_processed", wa_message_id=parsed["wa_message_id"])

        except Exception:
            log.error("process_message_error", exc_info=True)


async def process_status_update(status_data: dict) -> None:
    """Actualiza el status de un mensaje en BD (sent/delivered/read)."""
    async with SessionLocal() as db:
        try:
            wa_message_id = status_data["wa_message_id"]
            new_status = status_data["status"]

            result = await db.execute(
                select(Message).where(
                    Message.wa_message_id == wa_message_id
                )
            )
            message = result.scalar_one_or_none()

            if message:
                message.status = new_status
                await db.commit()
                logger.info(
                    "status_updated",
                    wa_message_id=wa_message_id,
                    status=new_status,
                )
            else:
                logger.debug(
                    "status_update_no_message",
                    wa_message_id=wa_message_id,
                )

        except Exception:
            logger.error("status_update_error", exc_info=True)
