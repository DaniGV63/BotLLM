"""Servicio de derivacion handoff: orquesta estado, notificaciones y timeout."""

import asyncio
import base64
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import structlog
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models.admin_user import AdminUser
from app.models.conversation import Conversation
from app.models.enums import ConversationState
from app.models.message import Message
from app.models.tenant import Tenant
from app.services.google_auth import get_google_creds

logger = structlog.get_logger()

MADRID_TZ = ZoneInfo("Europe/Madrid")

# Redis keys
_BRIDGE_MAPPINGS_KEY = "bridge:{tenant_id}:mappings"
_BRIDGE_COUNTER_KEY = "bridge:{tenant_id}:counter"


async def derivate_conversation(
    conversation: Conversation,
    tenant: Tenant,
    motivo: str,
    history: list[dict],
    db: AsyncSession,
) -> int:
    """Cambia estado a DERIVADA, asigna numero de derivacion, notifica al fisio.

    Returns:
        Numero de derivacion asignado (1, 2, ...).
    """
    log = logger.bind(
        tenant_id=str(tenant.id),
        conversation_id=str(conversation.id),
    )

    # 1. Cambiar estado a DERIVADA y registrar timestamp de inicio
    conversation.estado = ConversationState.DERIVADA.value
    conversation.derivation_started_at = datetime.now(timezone.utc)
    await db.flush()
    log.info("conversation_derivated")

    # 2. Asignar numero de derivacion en Redis
    counter_key = _BRIDGE_COUNTER_KEY.format(tenant_id=tenant.id)
    mappings_key = _BRIDGE_MAPPINGS_KEY.format(tenant_id=tenant.id)
    redis = await get_redis()

    ttl_seconds = (tenant.derivation_timeout_minutes or 60) * 60
    numero = await redis.incr(counter_key)
    await redis.expire(counter_key, ttl_seconds)

    import json

    mapping_entry = {
        "phone": conversation.wa_phone,
        "conv_id": str(conversation.id),
        "name": conversation.nombre_paciente or "Desconocido",
    }
    current_raw = await redis.hget(mappings_key, f"{numero}.")
    if not current_raw:
        await redis.hset(mappings_key, f"{numero}.", json.dumps(mapping_entry))
        await redis.expire(mappings_key, ttl_seconds)

    log.info("derivation_number_assigned", numero=numero)

    # 3. Construir resumen del historial (ultimos 4 mensajes)
    summary_parts = []
    for m in history[-4:]:
        role_label = "Paciente" if m["role"] == "user" else "Bot"
        summary_parts.append(f"{role_label}: {m['content'][:200]}")
    summary = "\n".join(summary_parts) if summary_parts else "Sin historial previo"

    # 4. Notificar al fisio (email + push WS)
    await _notify_derivation(
        tenant=tenant,
        conversation=conversation,
        numero=numero,
        motivo=motivo,
        summary=summary,
        db=db,
    )

    return numero


async def end_derivation(
    conversation: Conversation,
    tenant: Tenant,
    reason: str,
    db: AsyncSession,
) -> None:
    """Finaliza derivacion: estado ACTIVA, limpia Redis, notifica si timeout."""
    log = logger.bind(
        tenant_id=str(tenant.id),
        conversation_id=str(conversation.id),
    )

    # 1. Buscar numero de derivacion en Redis para limpiar mapping
    mappings_key = _BRIDGE_MAPPINGS_KEY.format(tenant_id=tenant.id)
    redis = await get_redis()

    import json

    all_mappings = await redis.hgetall(mappings_key)
    numero_to_remove = None
    for prefix, raw in all_mappings.items():
        try:
            entry = json.loads(raw)
            if entry.get("conv_id") == str(conversation.id):
                numero_to_remove = prefix
                break
        except Exception:
            pass

    if numero_to_remove:
        await redis.hdel(mappings_key, numero_to_remove)
        log.info("derivation_mapping_removed", prefix=numero_to_remove)

    # 2. Restaurar estado: INACTIVA si timeout, ACTIVA si cierre manual
    if reason == "timeout":
        conversation.estado = ConversationState.INACTIVA.value
    else:
        conversation.estado = ConversationState.ACTIVA.value
    conversation.derivation_started_at = None
    await db.flush()
    log.info("derivation_ended", reason=reason)

    # 3. Si fue por timeout, enviar email al fisio
    if reason == "timeout":
        await _send_timeout_email(tenant, conversation)


async def check_derivation_timeout(
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Revisa conversaciones DERIVADAS y cierra las que superaron el timeout.

    Lógica dual:
    - Si el fisio nunca respondió: timeout desde derivation_started_at
      (derivation_timeout_no_reply_minutes, default 480 = 8h)
    - Si el fisio ya respondió: timeout desde su último mensaje
      (derivation_timeout_after_reply_minutes, default 120 = 2h)
    """
    from sqlalchemy import select

    from app.models.message import Message

    result = await db.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant_id,
            Conversation.estado == ConversationState.DERIVADA.value,
        )
    )
    conversations = result.scalars().all()
    if not conversations:
        return

    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        return

    no_reply_timeout = tenant.derivation_timeout_no_reply_minutes or 480
    after_reply_timeout = tenant.derivation_timeout_after_reply_minutes or 120
    now = datetime.now(timezone.utc)

    for conv in conversations:
        # Buscar último mensaje del fisio (role=assistant) desde que se derivó
        started_at = conv.derivation_started_at
        if started_at and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        fisio_reply = None
        if started_at:
            msg_result = await db.execute(
                select(Message)
                .where(
                    Message.conversation_id == conv.id,
                    Message.role == "assistant",
                    Message.created_at > started_at,
                )
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            fisio_reply = msg_result.scalar_one_or_none()

        if fisio_reply:
            # El fisio respondió — timeout desde su último mensaje
            last = fisio_reply.created_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed = now - last
            timeout_minutes = after_reply_timeout
        else:
            # El fisio nunca respondió — timeout desde inicio de derivación
            reference = started_at or conv.ultimo_mensaje_at
            if reference and reference.tzinfo is None:
                reference = reference.replace(tzinfo=timezone.utc)
            elapsed = now - reference if reference else timedelta(0)
            timeout_minutes = no_reply_timeout

        if elapsed > timedelta(minutes=timeout_minutes):
            await end_derivation(conv, tenant, "timeout", db)
            logger.info(
                "derivation_timeout_ended",
                conversation_id=str(conv.id),
                tenant_id=str(tenant_id),
            )


async def _notify_derivation(
    tenant: Tenant,
    conversation: Conversation,
    numero: int,
    motivo: str,
    summary: str,
    db: AsyncSession,
) -> None:
    """Envia email al fisio con datos de la derivacion."""
    log = logger.bind(tenant_id=str(tenant.id))

    # Push WebSocket (fire and forget — no bloquea si no hay conexion)
    try:
        from app.services.websocket_manager import manager

        await manager.broadcast_to_tenant(
            str(tenant.id),
            {
                "type": "derivation_new",
                "conversation_id": str(conversation.id),
                "patient_name": conversation.nombre_paciente or "Desconocido",
                "phone": conversation.wa_phone,
                "motivo": motivo,
                "summary": summary,
                "numero": numero,
            },
        )
    except Exception:
        log.warning("ws_push_failed_on_derivation")

    # Email
    try:
        creds, _ = await get_google_creds(tenant.id)
    except ValueError as e:
        log.error("derivation_email_no_creds", error=str(e))
        return

    nombre_display = conversation.nombre_paciente or "Desconocido"
    body_text = (
        f"Paciente necesita atencion personal.\n\n"
        f"Nombre:   {nombre_display}\n"
        f"Telefono: {conversation.wa_phone}\n"
        f"Motivo:   {motivo}\n\n"
        f"Ultimos mensajes:\n{summary}\n\n"
        f"Responde con '{numero}.' en el chat web o en WhatsApp personal "
        f"para hablar directamente con este paciente."
    )

    msg = MIMEText(body_text, "plain", "utf-8")
    msg["To"] = tenant.email_notificaciones
    msg["Subject"] = f"[Atendoo] Paciente solicita atencion ({numero}.)"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    gmail_service = await asyncio.to_thread(
        build, "gmail", "v1", credentials=creds, cache_discovery=False
    )

    def _sync_send():
        return gmail_service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

    try:
        result = await asyncio.to_thread(_sync_send)
        log.info("derivation_email_sent", message_id=result.get("id"))
    except Exception as e:
        log.error("derivation_email_error", error=str(e))


async def _send_timeout_email(tenant: Tenant, conversation: Conversation) -> None:
    """Envia email al fisio avisando que una derivacion expiro por timeout."""
    log = logger.bind(tenant_id=str(tenant.id))
    try:
        creds, _ = await get_google_creds(tenant.id)
    except ValueError:
        log.warning("timeout_email_no_creds")
        return

    nombre = conversation.nombre_paciente or "Desconocido"
    timeout_min = tenant.derivation_timeout_minutes or 60
    body_text = (
        f"La derivacion del siguiente paciente ha expirado sin respuesta.\n\n"
        f"Nombre:   {nombre}\n"
        f"Telefono: {conversation.wa_phone}\n"
        f"Timeout:  {timeout_min} minutos\n\n"
        f"El paciente ha sido devuelto al bot automaticamente."
    )

    msg = MIMEText(body_text, "plain", "utf-8")
    msg["To"] = tenant.email_notificaciones
    msg["Subject"] = "[Atendoo] Derivacion expirada por timeout"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    gmail_service = await asyncio.to_thread(
        build, "gmail", "v1", credentials=creds, cache_discovery=False
    )

    def _sync_send():
        return gmail_service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

    try:
        await asyncio.to_thread(_sync_send)
        log.info("timeout_email_sent")
    except Exception as e:
        log.error("timeout_email_error", error=str(e))
