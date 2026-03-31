"""WA Bridge: fisio responde desde su WhatsApp personal con prefijos N."""

import json
import re
import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models.admin_user import AdminUser
from app.models.conversation import Conversation
from app.models.enums import ConversationState
from app.models.tenant import Tenant

logger = structlog.get_logger()

# Cache Redis para deteccion fisio (5 min)
_FISIO_CACHE_TTL = 300
_FISIO_CACHE_KEY = "bridge:{tenant_id}:fisio_phones"

_MAPPINGS_KEY = "bridge:{tenant_id}:mappings"

_PREFIX_RE = re.compile(r"^(\d+)\.\s*(.*)", re.DOTALL)
_BOT_CMD_RE = re.compile(r"^/bot\s*$", re.IGNORECASE)


async def is_therapist_phone(
    wa_phone: str,
    tenant: Tenant,
    db: AsyncSession,
) -> bool:
    """Comprueba si wa_phone pertenece al fisio (tenant o admin_user).

    Usa cache Redis 5 min para no consultar BD en cada mensaje.
    """
    redis = await get_redis()
    cache_key = _FISIO_CACHE_KEY.format(tenant_id=tenant.id)
    cached = await redis.get(cache_key)

    if cached:
        phones: list[str] = json.loads(cached)
    else:
        phones = []
        if tenant.wa_personal_phone:
            phones.append(tenant.wa_personal_phone)

        result = await db.execute(
            select(AdminUser.wa_personal_phone).where(
                AdminUser.tenant_id == tenant.id,
                AdminUser.wa_personal_phone.isnot(None),
            )
        )
        for row in result.scalars().all():
            if row and row not in phones:
                phones.append(row)

        await redis.set(cache_key, json.dumps(phones), ex=_FISIO_CACHE_TTL)

    return wa_phone in phones


async def handle_therapist_message(
    wa_phone_fisio: str,
    text: str,
    tenant: Tenant,
    db: AsyncSession,
) -> str | None:
    """Procesa mensaje del fisio via WA bridge.

    Returns:
        Mensaje de respuesta para enviar al fisio (o None si no hay que responder).
    """
    log = logger.bind(tenant_id=str(tenant.id), wa_phone_fisio=wa_phone_fisio)

    # Comando /bot → fin derivacion
    if _BOT_CMD_RE.match(text.strip()):
        return await _handle_bot_command(tenant, db, log)

    redis = await get_redis()
    mappings_key = _MAPPINGS_KEY.format(tenant_id=tenant.id)
    all_mappings_raw = await redis.hgetall(mappings_key)

    # Filtrar solo los que siguen DERIVADA en PG
    active_mappings = {}
    for prefix, raw in all_mappings_raw.items():
        try:
            entry = json.loads(raw)
            conv_id = uuid.UUID(entry["conv_id"])
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == conv_id,
                    Conversation.estado == ConversationState.DERIVADA.value,
                )
            )
            if result.scalar_one_or_none():
                active_mappings[prefix] = entry
        except Exception:
            pass

    if not active_mappings:
        log.info("bridge_no_active_derivations")
        return None  # fisio escribe sin derivaciones → ignorar silenciosamente

    # Parsear prefijo N.
    match = _PREFIX_RE.match(text)
    if match:
        numero_str = match.group(1)
        content = match.group(2).strip()
        prefix = f"{numero_str}."
        entry = active_mappings.get(prefix)
        if not entry:
            active_list = ", ".join(sorted(active_mappings.keys()))
            return f"No hay derivacion activa con el numero {prefix}. Activas: {active_list}"
        return await _forward_to_patient(entry, content, tenant, db, log)

    # Sin prefijo
    if len(active_mappings) == 1:
        # Una sola derivacion activa → enviar directamente
        entry = next(iter(active_mappings.values()))
        return await _forward_to_patient(entry, text, tenant, db, log)
    else:
        # Multiples derivaciones → pedir prefijo
        names = ", ".join(
            f"{p} {e['name']}" for p, e in sorted(active_mappings.items())
        )
        return (
            f"Tienes {len(active_mappings)} derivaciones activas. "
            f"Usa el numero para indicar a quien respondes:\n{names}"
        )


async def _forward_to_patient(
    entry: dict,
    content: str,
    tenant: Tenant,
    db: AsyncSession,
    log,
) -> str | None:
    """Guarda mensaje del fisio y lo envia al paciente por WA."""
    from app.services.conversation import append_therapist_message
    from app.services.whatsapp_service import send_text

    try:
        conv_id = uuid.UUID(entry["conv_id"])
        wa_phone = entry["phone"]

        result = await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            return "Error interno: conversacion no encontrada."

        await append_therapist_message(
            tenant_id=tenant.id,
            wa_phone=wa_phone,
            content=content,
            sender_name="fisio-wa",
            db=db,
            conversation_id=conv_id,
        )
        await send_text(tenant.id, wa_phone, content, db)
        await db.commit()

        log.info("bridge_message_forwarded", wa_phone=wa_phone)
        return None  # No responder al fisio si todo OK

    except Exception as e:
        log.error("bridge_forward_error", error=str(e))
        return "Error al enviar el mensaje al paciente."


async def _handle_bot_command(tenant: Tenant, db: AsyncSession, log) -> str:
    """Finaliza todas las derivaciones activas del tenant (/bot)."""
    from app.services.derivation_service import end_derivation

    redis = await get_redis()
    mappings_key = _MAPPINGS_KEY.format(tenant_id=tenant.id)
    all_mappings_raw = await redis.hgetall(mappings_key)

    ended = 0
    for prefix, raw in all_mappings_raw.items():
        try:
            entry = json.loads(raw)
            conv_id = uuid.UUID(entry["conv_id"])
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == conv_id,
                    Conversation.tenant_id == tenant.id,
                )
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                await end_derivation(conversation, tenant, "bot_command", db)
                ended += 1
        except Exception:
            pass

    await db.commit()
    log.info("bridge_bot_command_ended", count=ended)

    if ended == 0:
        return "No habia derivaciones activas."
    return f"Se han cerrado {ended} derivacion(es). El bot retoma el control."


async def invalidate_fisio_cache(tenant_id: uuid.UUID) -> None:
    """Invalida la cache de telefonos de fisio (tras cambios en BD)."""
    redis = await get_redis()
    await redis.delete(_FISIO_CACHE_KEY.format(tenant_id=tenant_id))
