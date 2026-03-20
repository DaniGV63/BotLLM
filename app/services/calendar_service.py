"""Servicio Calendar: stubs para Fase 3. Se implementa real en Fase 4."""

import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog

logger = structlog.get_logger()

MADRID_TZ = ZoneInfo("Europe/Madrid")

_DAY_NAMES = [
    "lunes", "martes", "miercoles", "jueves",
    "viernes", "sabado", "domingo",
]


async def get_free_slots(
    tenant_id: uuid.UUID,
    days_ahead: int = 7,
    duration_minutes: int = 60,
) -> list[dict]:
    """STUB: devuelve huecos de ejemplo para los proximos dias laborables."""
    log = logger.bind(tenant_id=str(tenant_id))
    log.info("get_free_slots_stub", days_ahead=days_ahead)

    now = datetime.now(MADRID_TZ)
    slots = []

    for day_offset in range(1, days_ahead + 1):
        day = now + timedelta(days=day_offset)
        if day.weekday() >= 5:  # Saltar fines de semana
            continue
        slots.append({
            "date": day.strftime("%Y-%m-%d"),
            "day_name": _DAY_NAMES[day.weekday()],
            "slots": ["09:00", "10:00", "11:00", "12:00", "16:00", "17:00"],
        })
        if len(slots) >= 3:
            break

    return slots


async def get_appointment_by_phone(
    tenant_id: uuid.UUID, phone: str
) -> dict | None:
    """STUB: siempre devuelve None (sin citas)."""
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=phone)
    log.info("get_appointment_by_phone_stub")
    return None


async def create_appointment(
    tenant_id: uuid.UUID,
    phone: str,
    client_name: str,
    datetime_iso: str,
    duration_minutes: int,
    service: str,
) -> str:
    """STUB: logea y devuelve event_id fake."""
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=phone)
    log.info(
        "create_appointment_stub",
        client_name=client_name,
        datetime_iso=datetime_iso,
        service=service,
    )
    return "stub_event_id"


async def modify_appointment(
    tenant_id: uuid.UUID, event_id: str, new_datetime_iso: str
) -> bool:
    """STUB: logea y devuelve True."""
    log = logger.bind(tenant_id=str(tenant_id))
    log.info(
        "modify_appointment_stub",
        event_id=event_id,
        new_datetime_iso=new_datetime_iso,
    )
    return True


async def cancel_appointment(
    tenant_id: uuid.UUID, event_id: str
) -> bool:
    """STUB: logea y devuelve True."""
    log = logger.bind(tenant_id=str(tenant_id))
    log.info("cancel_appointment_stub", event_id=event_id)
    return True
