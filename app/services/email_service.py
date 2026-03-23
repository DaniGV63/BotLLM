"""Servicio Email: notificaciones via Gmail API."""

import asyncio
import base64
import uuid
from email.mime.text import MIMEText

import structlog
from googleapiclient.discovery import build

from app.services.google_auth import get_google_creds

logger = structlog.get_logger()


async def send_notification_email(
    tenant_id: uuid.UUID,
    patient_name: str | None,
    patient_phone: str,
    motivo: str,
) -> bool:
    """Envia email al fisio avisando que un paciente quiere contacto.

    Args:
        tenant_id: UUID del tenant.
        patient_name: Nombre del paciente (puede ser None).
        patient_phone: Telefono WhatsApp del paciente.
        motivo: Razon del contacto o descripcion del error.

    Returns:
        True si el email se envio correctamente, False si hubo error.
    """
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=patient_phone)
    log.info("send_notification_email_start", motivo=motivo)

    try:
        creds, tenant = await get_google_creds(tenant_id)
    except ValueError as e:
        log.error("send_notification_email_no_creds", error=str(e))
        return False

    nombre_display = patient_name or "Desconocido"
    body_text = (
        f"Un paciente solicita contacto a traves del bot de WhatsApp.\n\n"
        f"Nombre:   {nombre_display}\n"
        f"Telefono: {patient_phone}\n"
        f"Motivo:   {motivo}\n\n"
        f"Por favor, contacta con el paciente a la brevedad posible."
    )

    msg = MIMEText(body_text, "plain", "utf-8")
    msg["To"] = tenant.email_notificaciones
    msg["Subject"] = "[BotLLM] Paciente solicita contacto"
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
        log.info("send_notification_email_done", message_id=result.get("id"))
        return True
    except Exception as e:
        log.error("send_notification_email_error", error=str(e))
        return False


async def send_bot_status_email(tenant_id: uuid.UUID, activated: bool) -> None:
    """Notifica al fisio que el bot ha sido activado o desactivado."""
    try:
        creds, tenant = await get_google_creds(tenant_id)
    except ValueError:
        return

    status = "activado" if activated else "desactivado"
    body_text = (
        "Tu bot de WhatsApp ha sido activado.\n\n"
        "A partir de ahora, el bot respondera automaticamente a tus pacientes."
        if activated else
        "Tu bot de WhatsApp ha sido desactivado.\n\n"
        "Los mensajes llegaran a tu WhatsApp Business pero el bot no respondera. "
        "Recuerda responder manualmente."
    )
    msg = MIMEText(body_text, "plain", "utf-8")
    msg["To"] = tenant.email_notificaciones
    msg["Subject"] = f"[BotLLM] Bot {status}"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    gmail_service = await asyncio.to_thread(
        build, "gmail", "v1", credentials=creds, cache_discovery=False
    )
    try:
        await asyncio.to_thread(
            gmail_service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute
        )
        logger.info("bot_status_email_sent", status=status)
    except Exception as e:
        logger.error("bot_status_email_error", error=str(e))
