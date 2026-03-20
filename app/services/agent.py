"""Agente orquestador: flujo completo de procesamiento de mensajes."""

import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.calendar_service import (
    cancel_appointment,
    create_appointment,
    get_appointment_by_phone,
    get_free_slots,
    modify_appointment,
)
from app.services.conversation import (
    append_message,
    get_history,
    get_or_create_conversation,
    reset_conversation,
)
from app.services.email_service import send_notification_email
from app.services.llm_service import detect_intent, generate_response, load_prompt
from app.services.whatsapp_service import send_text

logger = structlog.get_logger()

MADRID_TZ = ZoneInfo("Europe/Madrid")
EXPIRATION_HOURS = 24

FALLBACK_MSG = (
    "Disculpa, ha habido un problema tecnico. "
    "He avisado a la clinica para que te contacten lo antes posible."
)

CONFIRMATION_WORDS = {
    "si", "sí", "confirmo", "vale", "ok", "adelante",
    "perfecto", "correcto", "confirmar", "claro", "venga", "dale",
}

NEGATION_WORDS = {
    "no", "cancelar", "espera", "para", "cambiar", "anular", "mejor no",
}

_DAY_NAMES_ES = [
    "lunes", "martes", "miercoles", "jueves",
    "viernes", "sabado", "domingo",
]

_MONTH_NAMES_ES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _now_madrid() -> datetime:
    """Devuelve fecha/hora actual en zona horaria de Madrid."""
    return datetime.now(MADRID_TZ)


def _format_datetime_es(dt: datetime) -> str:
    """Formatea datetime en espanol sin depender del locale del sistema."""
    day_name = _DAY_NAMES_ES[dt.weekday()]
    month_name = _MONTH_NAMES_ES[dt.month]
    return f"{day_name} {dt.day} de {month_name} de {dt.year}, {dt.strftime('%H:%M')}"


def _is_expired(conversation) -> bool:
    """Comprueba si la conversacion ha expirado (>24h sin actividad)."""
    if conversation.ultimo_mensaje_at is None:
        return False
    now = _now_madrid()
    last = conversation.ultimo_mensaje_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=MADRID_TZ)
    return (now - last) > timedelta(hours=EXPIRATION_HOURS)


def user_confirmed(message: str) -> bool:
    """Safety net: verifica si el usuario confirmo una accion."""
    words = set(message.lower().split())
    has_confirm = bool(words & CONFIRMATION_WORDS)
    has_negation = bool(words & NEGATION_WORDS)
    return has_confirm and not has_negation


async def _execute_action(
    action: dict, tenant_id: uuid.UUID, wa_phone: str
) -> None:
    """Ejecuta una accion de Calendar."""
    action_type = action["type"]

    if action_type == "create":
        await create_appointment(
            tenant_id=tenant_id,
            phone=wa_phone,
            client_name=action.get("client_name", ""),
            datetime_iso=action.get("datetime", ""),
            duration_minutes=action.get("duration", 60),
            service=action.get("service", ""),
        )
    elif action_type == "modify":
        await modify_appointment(
            tenant_id=tenant_id,
            event_id=action.get("event_id", ""),
            new_datetime_iso=action.get("new_datetime", ""),
        )
    elif action_type == "cancel":
        await cancel_appointment(
            tenant_id=tenant_id,
            event_id=action.get("event_id", ""),
        )


async def handle_message(
    tenant_id: uuid.UUID,
    wa_phone: str,
    message_text: str,
    wa_message_id: str,
    db: AsyncSession,
) -> None:
    """Punto de entrada del agente. Llamado desde BackgroundTask del webhook.

    Flujo: detect_intent -> preparar contexto -> generate_response ->
    ejecutar action -> persistir -> enviar WhatsApp.
    """
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=wa_phone)
    start_time = time.monotonic()

    try:
        # 1. Obtener o crear conversacion
        conversation = await get_or_create_conversation(
            tenant_id, wa_phone, db
        )

        # 2. Expiracion: si >24h sin actividad, resetear
        if _is_expired(conversation):
            log.info("conversation_expired_reset")
            conversation = await reset_conversation(conversation, db)

        # 3. Cargar historial
        history = await get_history(tenant_id, wa_phone, db)

        # 4. Detectar intencion (llamada 1 al LLM)
        try:
            intent = await detect_intent(message_text, history)
        except Exception as e:
            log.error("detect_intent_error", error=str(e))
            intent = "faq"

        log.info("intent_result", intent=intent)

        # 5. Preparar contexto segun intencion
        context: dict = {
            "business_info": load_prompt("negocio.md"),
            "current_datetime": _format_datetime_es(_now_madrid()),
            "nombre_paciente": conversation.nombre_paciente,
            "es_primera_interaccion": len(history) == 0,
        }

        if intent == "agendar_cita":
            context["free_slots"] = await get_free_slots(tenant_id)
        elif intent in ("cancelar_cita", "modificar_cita"):
            context["appointment"] = await get_appointment_by_phone(
                tenant_id, wa_phone
            )

        # 6. Generar respuesta (llamada 2 al LLM)
        try:
            response = await generate_response(
                message_text, intent, context, history
            )
        except Exception as e:
            log.error("generate_response_error", error=str(e))
            await send_text(tenant_id, wa_phone, FALLBACK_MSG, db)
            await send_notification_email(
                tenant_id, None, wa_phone, "Error tecnico LLM"
            )
            return

        reply_text = response.get("message", FALLBACK_MSG)

        # 7. Guardar nombre si se detecto
        nombre = response.get("nombre_detectado")
        if nombre and not conversation.nombre_paciente:
            conversation.nombre_paciente = nombre
            log.info("nombre_saved", nombre=nombre)

        # 8. Ejecutar accion si existe (con safety net)
        action = response.get("action")
        action_executed = None

        if action:
            action_type = action.get("type")

            if action_type in ("create", "modify", "cancel"):
                if user_confirmed(message_text):
                    try:
                        await _execute_action(action, tenant_id, wa_phone)
                        action_executed = action_type
                        log.info("action_executed", action=action_type)
                    except Exception as e:
                        log.error(
                            "action_error",
                            action=action_type,
                            error=str(e),
                        )
                        reply_text = (
                            "Disculpa, ha habido un problema al procesar "
                            "tu solicitud. He avisado a la clinica."
                        )
                        await send_notification_email(
                            tenant_id,
                            conversation.nombre_paciente,
                            wa_phone,
                            f"Error en {action_type}",
                        )
                else:
                    log.warning("safety_net_triggered", action=action_type)

            elif action_type == "derivar":
                await send_notification_email(
                    tenant_id,
                    conversation.nombre_paciente,
                    wa_phone,
                    action.get("motivo", "Paciente quiere hablar con persona"),
                )
                action_executed = "derivar"

        # 9. Calcular processing_ms
        processing_ms = int((time.monotonic() - start_time) * 1000)

        # 10. Persistir mensajes (PG primero, Redis despues)
        await append_message(
            tenant_id=tenant_id,
            wa_phone=wa_phone,
            role="user",
            content=message_text,
            db=db,
            conversation_id=conversation.id,
            intent=intent,
            wa_message_id=wa_message_id,
        )
        await append_message(
            tenant_id=tenant_id,
            wa_phone=wa_phone,
            role="assistant",
            content=reply_text,
            db=db,
            conversation_id=conversation.id,
            action=action_executed,
            processing_ms=processing_ms,
        )

        # 11. Enviar respuesta por WhatsApp
        await send_text(tenant_id, wa_phone, reply_text, db)

        # 12. Actualizar timestamp y commit
        conversation.ultimo_mensaje_at = _now_madrid()
        await db.commit()

        log.info(
            "message_handled",
            intent=intent,
            action=action_executed,
            processing_ms=processing_ms,
        )

    except Exception as e:
        log.error("handle_message_error", error=str(e), exc_info=True)
        try:
            await send_text(tenant_id, wa_phone, FALLBACK_MSG, db)
        except Exception:
            log.error("fallback_send_failed", exc_info=True)
