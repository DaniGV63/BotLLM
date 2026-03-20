"""Servicio Email: stub para Fase 3. Se implementa real en Fase 4."""

import uuid

import structlog

logger = structlog.get_logger()


async def send_notification_email(
    tenant_id: uuid.UUID,
    patient_name: str | None,
    patient_phone: str,
    motivo: str,
) -> bool:
    """STUB: logea la notificacion y devuelve True."""
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=patient_phone)
    log.info(
        "send_notification_email_stub",
        patient_name=patient_name,
        motivo=motivo,
    )
    return True
