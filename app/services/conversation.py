"""Servicio de conversacion: historial Redis + sync PG."""

import json
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models.conversation import Conversation
from app.models.enums import ConversationState
from app.models.message import Message

logger = structlog.get_logger()

HISTORY_TTL = 86400  # 24 horas
MAX_HISTORY = 20


def _redis_key(tenant_id: uuid.UUID, wa_phone: str) -> str:
    """Genera clave Redis para el historial."""
    return f"conversation:{tenant_id}:{wa_phone}"


async def get_or_create_conversation(
    tenant_id: uuid.UUID, wa_phone: str, db: AsyncSession
) -> Conversation:
    """Obtiene la conversacion activa o crea una nueva."""
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=wa_phone)

    result = await db.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant_id,
            Conversation.wa_phone == wa_phone,
        )
    )
    conversation = result.scalar_one_or_none()

    if conversation:
        log.debug("conversation_found", conversation_id=str(conversation.id))
        return conversation

    conversation = Conversation(
        tenant_id=tenant_id,
        wa_phone=wa_phone,
        estado=ConversationState.ACTIVA.value,
    )
    db.add(conversation)
    await db.flush()
    log.info("conversation_created", conversation_id=str(conversation.id))
    return conversation


async def get_history(
    tenant_id: uuid.UUID,
    wa_phone: str,
    db: AsyncSession,
    max_messages: int = MAX_HISTORY,
) -> list[dict]:
    """Lee historial de Redis. Si no existe, reconstruye desde PG."""
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=wa_phone)
    redis = await get_redis()
    key = _redis_key(tenant_id, wa_phone)

    cached = await redis.get(key)
    if cached:
        history = json.loads(cached)
        log.debug("history_from_redis", count=len(history))
        return history[-max_messages:]

    # Fallback: reconstruir desde PG
    result = await db.execute(
        select(Conversation.id).where(
            Conversation.tenant_id == tenant_id,
            Conversation.wa_phone == wa_phone,
        )
    )
    conv_id = result.scalar_one_or_none()
    if not conv_id:
        return []

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .limit(max_messages)
    )
    messages = result.scalars().all()

    history = [{"role": m.role, "content": m.content} for m in messages]

    if history:
        await redis.set(key, json.dumps(history), ex=HISTORY_TTL)
        log.debug("history_rebuilt_from_pg", count=len(history))

    return history


async def append_message(
    tenant_id: uuid.UUID,
    wa_phone: str,
    role: str,
    content: str,
    db: AsyncSession,
    conversation_id: uuid.UUID,
    intent: str | None = None,
    action: str | None = None,
    wa_message_id: str | None = None,
    processing_ms: int | None = None,
) -> None:
    """Guarda mensaje en PG (fuente de verdad) y actualiza Redis (cache)."""
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=wa_phone)

    # PG primero
    message = Message(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role=role,
        content=content,
        intent=intent,
        action_executed=action,
        wa_message_id=wa_message_id,
        processing_ms=processing_ms,
    )
    db.add(message)
    await db.flush()
    log.debug("message_persisted_pg", role=role, message_id=str(message.id))

    # Redis despues
    redis = await get_redis()
    key = _redis_key(tenant_id, wa_phone)
    cached = await redis.get(key)

    history = json.loads(cached) if cached else []
    history.append({"role": role, "content": content})
    history = history[-MAX_HISTORY:]

    await redis.set(key, json.dumps(history), ex=HISTORY_TTL)
    log.debug("message_cached_redis", role=role, history_size=len(history))


async def reset_conversation(
    conversation: Conversation, db: AsyncSession
) -> Conversation:
    """Resetea conversacion expirada: limpia nombre y cache Redis."""
    log = logger.bind(
        tenant_id=str(conversation.tenant_id),
        wa_phone=conversation.wa_phone,
    )

    # Reusar fila (UniqueConstraint impide crear nueva para mismo tenant+phone)
    conversation.nombre_paciente = None
    conversation.estado = ConversationState.ACTIVA.value
    await db.flush()

    # Limpiar cache Redis
    redis = await get_redis()
    key = _redis_key(conversation.tenant_id, conversation.wa_phone)
    await redis.delete(key)

    log.info("conversation_reset", conversation_id=str(conversation.id))
    return conversation
