"""Servicio WhatsApp: parseo de webhooks de Meta y envío de mensajes."""

import uuid

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt
from app.models.tenant import Tenant

logger = structlog.get_logger()

META_GRAPH_URL = "https://graph.facebook.com/v19.0"


def parse_incoming_webhook(body: dict) -> dict | None:
    """Extrae datos de un webhook de mensaje entrante de Meta.

    Returns:
        Dict con phone_number_id, wa_phone, wa_message_id, message_type,
        text (None si no es texto), contact_name. O None si no es un mensaje.
    """
    try:
        value = body["entry"][0]["changes"][0]["value"]
        phone_number_id = value["metadata"]["phone_number_id"]

        messages = value.get("messages")
        if not messages:
            return None

        msg = messages[0]
        contact_name = None
        contacts = value.get("contacts")
        if contacts:
            contact_name = contacts[0].get("profile", {}).get("name")

        return {
            "phone_number_id": phone_number_id,
            "wa_phone": msg["from"],
            "wa_message_id": msg["id"],
            "message_type": msg["type"],
            "text": msg["text"]["body"] if msg["type"] == "text" else None,
            "contact_name": contact_name,
        }
    except (KeyError, IndexError, TypeError):
        logger.warning("webhook_parse_error", body_keys=list(body.keys()))
        return None


def parse_status_update(body: dict) -> dict | None:
    """Extrae datos de un webhook de status (delivered/read/sent).

    Returns:
        Dict con wa_message_id, status, phone_number_id. O None si no es status.
    """
    try:
        value = body["entry"][0]["changes"][0]["value"]
        statuses = value.get("statuses")
        if not statuses:
            return None

        status = statuses[0]
        return {
            "wa_message_id": status["id"],
            "status": status["status"],
            "phone_number_id": value["metadata"]["phone_number_id"],
        }
    except (KeyError, IndexError, TypeError):
        return None


async def get_tenant_by_phone_number_id(
    phone_number_id: str, db: AsyncSession
) -> Tenant | None:
    """Busca tenant activo por whatsapp_phone_number_id."""
    result = await db.execute(
        select(Tenant).where(
            Tenant.whatsapp_phone_number_id == phone_number_id,
            Tenant.activo.is_(True),
            Tenant.bot_activo.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def send_text(
    tenant_id: uuid.UUID,
    wa_phone: str,
    message: str,
    db: AsyncSession,
) -> dict | None:
    """Envía mensaje de texto plano via WhatsApp Cloud API.

    Args:
        tenant_id: UUID del tenant.
        wa_phone: Número de teléfono del destinatario.
        message: Texto a enviar.
        db: Sesión de base de datos.

    Returns:
        Response de Meta o None si error.
    """
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=wa_phone)

    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.whatsapp_token:
        log.error("send_text_no_tenant_or_token")
        return None

    token = decrypt(tenant.whatsapp_token)
    url = f"{META_GRAPH_URL}/{tenant.whatsapp_phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "to": wa_phone,
        "type": "text",
        "text": {"body": message},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if response.status_code == 200:
            log.info("message_sent")
            log.debug("message_sent_content", content=message)
            return response.json()

        log.error(
            "send_text_error",
            status_code=response.status_code,
            response_body=response.text,
        )
        return None

    except httpx.HTTPError as e:
        log.error("send_text_http_error", error=str(e))
        return None
