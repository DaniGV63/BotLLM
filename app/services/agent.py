"""Agente orquestador: flujo completo de procesamiento de mensajes."""

import time
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.features import get_tenant_features
from app.core.redis import acquire_lock
from app.models.enums import ConversationState
from app.models.tenant import Tenant
from app.services.appointment_utils import (
    count_active_appointments,
    format_slot_conflict_message,
    slot_is_available,
)
from app.services.calendar_service import (
    cancel_appointment,
    create_appointment,
    format_work_blocks_for_prompt,
    get_appointment_by_phone,
    get_free_slots,
    get_past_appointments,
    modify_appointment,
)
from app.services.conversation import (
    append_message,
    deactivate_conversation,
    get_history,
    get_or_create_conversation,
    reactivate_conversation,
)
from app.services.email_service import send_cancellation_alert_email, send_notification_email
from app.services.group_class_service import (
    cancel_inscription,
    get_group_slots_for_bot,
    get_patient_upcoming_inscriptions,
    inscribe_patient,
)
from app.services.llm_service import detect_intent, generate_response, load_prompt
from app.services.whatsapp_service import send_text

logger = structlog.get_logger()

MADRID_TZ = ZoneInfo("Europe/Madrid")
EXPIRATION_HOURS = 24

FALLBACK_MSG = "Disculpa, ha habido un problema tecnico. He avisado a la clinica para que te contacten lo antes posible."
FEATURE_NOT_AVAILABLE_MSG = "Esta funcionalidad no esta disponible en tu plan actual. Contacta con nosotros para mas informacion."

CONFIRMATION_WORDS = {
    "si", "sí", "confirmo", "vale", "ok", "adelante",
    "perfecto", "correcto", "confirmar", "claro", "venga", "dale",
}

NEGATION_WORDS = {"no", "cancelar", "espera", "para", "cambiar", "anular", "mejor no"}

MAX_CITAS_ACTIVAS = 5
MAX_CITAS_MSG = "Ya tienes varias citas agendadas. Si necesitas otra, contacta con la clinica."

_DAY_NAMES_ES = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

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
    words = set(message.lower().split())
    return bool(words & CONFIRMATION_WORDS) and not bool(words & NEGATION_WORDS)


async def _execute_action(action: dict, tenant_id: uuid.UUID, wa_phone: str) -> None:
    t = action["type"]
    if t == "create":
        await create_appointment(
            tenant_id=tenant_id, phone=wa_phone,
            client_name=action.get("client_name", ""),
            datetime_iso=action.get("datetime", ""),
            duration_minutes=action.get("duration", 60),
            service=action.get("service", ""),
        )
    elif t == "modify":
        await modify_appointment(
            tenant_id=tenant_id, event_id=action.get("event_id", ""),
            new_datetime_iso=action.get("new_datetime", ""),
        )
    elif t == "cancel":
        await cancel_appointment(
            tenant_id=tenant_id, event_id=action.get("event_id", ""),
        )


async def _handle_derivada_message(
    conversation,
    tenant_id: uuid.UUID,
    wa_phone: str,
    message_text: str,
    wa_message_id: str,
    db: AsyncSession,
) -> None:
    """Guarda mensaje del paciente en PG y notifica al fisio via WS (estado DERIVADA)."""
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=wa_phone)

    await append_message(
        tenant_id=tenant_id,
        wa_phone=wa_phone,
        role="user",
        content=message_text,
        db=db,
        conversation_id=conversation.id,
        wa_message_id=wa_message_id,
    )
    conversation.ultimo_mensaje_at = _now_madrid()
    await db.commit()

    # Notificar al fisio por WebSocket
    try:
        from app.services.websocket_manager import manager
        await manager.broadcast_to_tenant(
            str(tenant_id),
            {
                "type": "patient_message",
                "conversation_id": str(conversation.id),
                "content": message_text,
                "timestamp": _now_madrid().isoformat(),
            },
        )
    except Exception:
        log.warning("ws_patient_message_push_failed")

    log.info("derivada_message_stored", conversation_id=str(conversation.id))


def _appointment_is_within_24h(appointment: dict | None) -> bool:
    """True si la cita esta a menos de 24h del momento actual."""
    dt_str = (appointment or {}).get("start") or (appointment or {}).get("datetime")
    if not dt_str:
        return False
    try:
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=MADRID_TZ)
        diff = dt - _now_madrid()
        return timedelta(0) <= diff <= timedelta(hours=24)
    except Exception:
        return False


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

        # 2a. Si DERIVADA → mensajes van al fisio via WS/WA, no al LLM
        #     Aun asi guardamos el mensaje del paciente y lo retransmitimos por WS
        if conversation.estado == ConversationState.DERIVADA.value:
            await _handle_derivada_message(
                conversation, tenant_id, wa_phone, message_text, wa_message_id, db
            )
            return

        # 2b. Si INACTIVA (paciente vuelve tras despedida) o expirada (>24h sin mensaje)
        #    → reactivar: historial limpio, nombre conservado
        if conversation.estado == ConversationState.INACTIVA.value or _is_expired(conversation):
            log.info("conversation_reactivated", estado=conversation.estado)
            await reactivate_conversation(conversation, db)

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
        _t = await db.get(Tenant, tenant_id)
        max_citas = (_t.max_citas_activas if _t else None) or MAX_CITAS_ACTIVAS

        # Feature check
        features = await get_tenant_features(tenant_id, db)

        # Horarios dinámicos del tenant para el LLM
        business_hours = ""
        if _t and getattr(_t, "work_blocks", None):
            business_hours = format_work_blocks_for_prompt(_t.work_blocks)

        # RGPD: primera interaccion solo si no ha aceptado aun (persiste en PG)
        es_primera_interaccion = not conversation.rgpd_accepted

        context: dict = {
            "business_info": load_prompt("negocio.md"),
            "business_hours": business_hours,
            "current_datetime": _format_datetime_es(_now_madrid()),
            "nombre_paciente": conversation.nombre_paciente,
            "es_primera_interaccion": es_primera_interaccion,
        }

        if intent == "agendar_cita":
            if not features.get("calendar.schedule", False):
                await send_text(tenant_id, wa_phone, FEATURE_NOT_AVAILABLE_MSG, db)
                return
            if (await count_active_appointments(tenant_id, wa_phone)) >= max_citas:
                await send_text(tenant_id, wa_phone, MAX_CITAS_MSG, db)
                return
            context["free_slots"] = await get_free_slots(tenant_id)
            if features.get("groups.sessions", False):
                group_slots = await get_group_slots_for_bot(tenant_id, 7, db)
                if group_slots:
                    context["group_slots"] = group_slots
        elif intent in ("cancelar_cita", "modificar_cita"):
            feature_key = "calendar.cancel" if intent == "cancelar_cita" else "calendar.modify"
            if not features.get(feature_key, False):
                await send_text(tenant_id, wa_phone, FEATURE_NOT_AVAILABLE_MSG, db)
                return
            context["appointment"] = await get_appointment_by_phone(
                tenant_id, wa_phone
            )
            if features.get("groups.sessions", False):
                context["group_inscriptions"] = await get_patient_upcoming_inscriptions(
                    tenant_id, wa_phone, db
                )
            if intent == "modificar_cita":
                context["free_slots"] = await get_free_slots(tenant_id)
                if features.get("groups.sessions", False):
                    context["group_slots"] = await get_group_slots_for_bot(tenant_id, 7, db)

        elif intent == "consultar_historial":
            context["past_appointments"] = await get_past_appointments(tenant_id, wa_phone)
            context["upcoming_appointments"] = await get_appointment_by_phone(tenant_id, wa_phone)
            context["upcoming_group_inscriptions"] = await get_patient_upcoming_inscriptions(
                tenant_id, wa_phone, db
            )

        # 6. Generar respuesta (llamada 2 al LLM)
        try:
            response = await generate_response(
                message_text, intent, context, history
            )
        except Exception as e:
            log.error("generate_response_error", error=str(e))
            await send_text(tenant_id, wa_phone, FALLBACK_MSG, db)
            await append_message(
                tenant_id=tenant_id, wa_phone=wa_phone, role="user",
                content=message_text, db=db, conversation_id=conversation.id,
                wa_message_id=wa_message_id,
            )
            await append_message(
                tenant_id=tenant_id, wa_phone=wa_phone, role="assistant",
                content=FALLBACK_MSG, db=db, conversation_id=conversation.id,
            )
            _t_err = await db.get(Tenant, tenant_id)
            from app.services.derivation_service import derivate_conversation
            await derivate_conversation(
                conversation=conversation, tenant=_t_err,
                motivo="Error tecnico automatico", history=history, db=db,
            )
            await db.commit()
            return

        reply_text = response.get("message", FALLBACK_MSG)

        # 7. Guardar nombre si se detecto
        nombre = response.get("nombre_detectado")
        if nombre:
            conversation.nombre_paciente = nombre
            log.info("nombre_saved", nombre=nombre)

        # 7b. Marcar RGPD como aceptado tras primer mensaje exitoso
        if es_primera_interaccion and not conversation.rgpd_accepted:
            conversation.rgpd_accepted = True

        # 8. Ejecutar accion si existe (con safety net)
        action = response.get("action")
        action_executed = None

        if action:
            action_type = action.get("type")

            if action_type in ("create", "modify", "cancel"):
                if user_confirmed(message_text):
                    # 2.2 Idempotencia: evita ejecucion duplicada por retry de Meta
                    action_lock_key = f"action_lock:{tenant_id}:{wa_phone}"
                    if not await acquire_lock(action_lock_key, ttl=30):
                        log.warning("action_skipped_duplicate", action=action_type)
                    else:
                        execute = True
                        # 2.3 Race condition: re-validar slot justo antes de crear
                        if action_type == "create" and not action.get("is_group_class"):
                            dt_iso = action.get("datetime", "")
                            slot_key = f"slot_lock:{tenant_id}:{dt_iso}"
                            if not await acquire_lock(slot_key, ttl=60):
                                log.warning("slot_concurrent", datetime=dt_iso)
                                reply_text = format_slot_conflict_message(
                                    await get_free_slots(tenant_id)
                                )
                                execute = False
                            else:
                                fresh = await get_free_slots(tenant_id)
                                if not slot_is_available(dt_iso, fresh):
                                    log.warning("slot_taken", datetime=dt_iso)
                                    reply_text = format_slot_conflict_message(fresh)
                                    execute = False
                        if execute:
                            try:
                                if action_type == "create" and action.get("is_group_class"):
                                    session_id_str = action.get("session_id", "")
                                    result = await inscribe_patient(
                                        tenant_id=tenant_id,
                                        session_id=uuid.UUID(session_id_str),
                                        wa_phone=wa_phone,
                                        nombre=conversation.nombre_paciente,
                                        db=db,
                                    )
                                    if not result.get("ok"):
                                        reason = result.get("reason", "")
                                        if reason == "full":
                                            fresh_grp = await get_group_slots_for_bot(tenant_id, 7, db)
                                            reply_text = (
                                                "Lo siento, esa clase ya no tiene plazas. "
                                                f"Otras opciones disponibles: {fresh_grp}"
                                            )
                                        else:
                                            reply_text = "No se pudo completar la inscripción. Por favor, contacta con la clínica."
                                        execute = False
                                    else:
                                        action_executed = action_type
                                        log.info("group_inscription_done", session_id=session_id_str)
                                elif action_type == "cancel" and action.get("is_group_class"):
                                    session_id_str = action.get("session_id", "")
                                    cancelled = await cancel_inscription(
                                        tenant_id=tenant_id,
                                        session_id=uuid.UUID(session_id_str),
                                        wa_phone=wa_phone,
                                        db=db,
                                    )
                                    if not cancelled:
                                        reply_text = "No encontré tu inscripción en esa clase. Puede que ya estuviera cancelada."
                                        execute = False
                                    else:
                                        action_executed = action_type
                                        log.info("group_inscription_cancelled", session_id=session_id_str)
                                else:
                                    await _execute_action(action, tenant_id, wa_phone)
                                    action_executed = action_type
                                log.info("action_executed", action=action_type)
                                # Alerta cancelacion <24h
                                if action_type == "cancel" and features.get("handoff.cancellation_alert", False):
                                    appt = context.get("appointment")
                                    if _appointment_is_within_24h(appt):
                                        appt_dt = (appt or {}).get("start") or (appt or {}).get("datetime", "")
                                        await send_cancellation_alert_email(
                                            tenant_id,
                                            conversation.nombre_paciente,
                                            wa_phone,
                                            appt_dt,
                                        )
                            except Exception as e:
                                log.error("action_error", action=action_type, error=str(e))
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
                if not features.get("email.derivation", False):
                    reply_text = FEATURE_NOT_AVAILABLE_MSG
                else:
                    _t_obj = await db.get(Tenant, tenant_id)
                    from app.services.derivation_service import derivate_conversation
                    await derivate_conversation(
                        conversation=conversation,
                        tenant=_t_obj,
                        motivo=action.get("motivo", "Paciente quiere hablar con persona"),
                        history=history,
                        db=db,
                    )
                    action_executed = "derivar"

            elif action_type == "despedida":
                await deactivate_conversation(conversation, db)
                action_executed = "despedida"

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

        # 13. Broadcast WS → actualización en tiempo real del panel admin
        try:
            from app.services.websocket_manager import manager
            await manager.broadcast_to_tenant(
                str(tenant_id),
                {
                    "type": "conversation_updated",
                    "conversation_id": str(conversation.id),
                    "wa_phone": wa_phone,
                    "intent": intent,
                    "action": action_executed,
                },
            )
        except Exception:
            log.warning("ws_conversation_updated_failed")

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
            conv = await get_or_create_conversation(tenant_id, wa_phone, db)
            await append_message(
                tenant_id=tenant_id, wa_phone=wa_phone, role="user",
                content=message_text, db=db, conversation_id=conv.id,
            )
            await append_message(
                tenant_id=tenant_id, wa_phone=wa_phone, role="assistant",
                content=FALLBACK_MSG, db=db, conversation_id=conv.id,
            )
            _t_err = await db.get(Tenant, tenant_id)
            from app.services.derivation_service import derivate_conversation
            await derivate_conversation(
                conversation=conv, tenant=_t_err,
                motivo="Error tecnico automatico", history=[], db=db,
            )
            await db.commit()
        except Exception:
            log.error("fallback_send_failed", exc_info=True)
