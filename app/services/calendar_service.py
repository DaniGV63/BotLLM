"""Servicio Calendar: integracion real con Google Calendar API."""

import asyncio
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from googleapiclient.discovery import build

from app.services.google_auth import get_google_creds

logger = structlog.get_logger()

MADRID_TZ = ZoneInfo("Europe/Madrid")

_DAY_NAMES = [
    "lunes", "martes", "miercoles", "jueves",
    "viernes", "sabado", "domingo",
]

# Bloques horarios por dia de semana (L-J: 09-14 + 16-20:30 | V: 09-15 | S-D cerrado)
WORK_BLOCKS: dict[int, list[tuple[str, str]]] = {
    0: [("09:00", "14:00"), ("16:00", "20:30")],
    1: [("09:00", "14:00"), ("16:00", "20:30")],
    2: [("09:00", "14:00"), ("16:00", "20:30")],
    3: [("09:00", "14:00"), ("16:00", "20:30")],
    4: [("09:00", "15:00")],
}


def _parse_hhmm(hhmm: str, base: datetime) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return base.replace(hour=h, minute=m, second=0, microsecond=0)


def _generate_day_slots(day: datetime, duration_minutes: int) -> list[datetime]:
    slots = []
    for start_str, end_str in WORK_BLOCKS.get(day.weekday(), []):
        slot = _parse_hhmm(start_str, day)
        block_end = _parse_hhmm(end_str, day)
        while slot + timedelta(minutes=duration_minutes) <= block_end:
            slots.append(slot)
            slot += timedelta(hours=1)
    return slots


def _overlaps(slot: datetime, duration_minutes: int, event: dict) -> bool:
    slot_end = slot + timedelta(minutes=duration_minutes)
    ev_start_str = event.get("start", {}).get("dateTime")
    ev_end_str = event.get("end", {}).get("dateTime")
    if not ev_start_str or not ev_end_str:
        return False
    ev_start = datetime.fromisoformat(ev_start_str).astimezone(MADRID_TZ)
    ev_end = datetime.fromisoformat(ev_end_str).astimezone(MADRID_TZ)
    return slot < ev_end and slot_end > ev_start


async def get_free_slots(
    tenant_id: uuid.UUID,
    days_ahead: int = 7,
    duration_minutes: int = 60,
) -> list[dict]:
    """Devuelve huecos libres respetando horario laboral y citas existentes.

    Returns:
        [{"date": "2025-03-20", "day_name": "jueves", "slots": ["09:00", ...]}]
    """
    log = logger.bind(tenant_id=str(tenant_id))
    log.info("get_free_slots_start", days_ahead=days_ahead)

    creds, tenant = await get_google_creds(tenant_id)
    calendar_id = tenant.google_calendar_id or "primary"
    now = datetime.now(MADRID_TZ)
    time_max = now + timedelta(days=days_ahead)

    svc = await asyncio.to_thread(
        build, "calendar", "v3", credentials=creds, cache_discovery=False
    )
    events_result = await asyncio.to_thread(
        svc.events().list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute
    )
    existing_events = events_result.get("items", [])

    result = []
    days_found, day_offset = 0, 1
    while days_found < days_ahead and day_offset <= days_ahead * 2:
        day = (now + timedelta(days=day_offset)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_offset += 1
        if day.weekday() not in WORK_BLOCKS:
            continue
        free_slots = [
            s for s in _generate_day_slots(day, duration_minutes)
            if s > now and not any(_overlaps(s, duration_minutes, ev) for ev in existing_events)
        ]
        if free_slots:
            result.append({
                "date": day.strftime("%Y-%m-%d"),
                "day_name": _DAY_NAMES[day.weekday()],
                "slots": [s.strftime("%H:%M") for s in free_slots],
            })
            days_found += 1

    log.info("get_free_slots_done", days_returned=len(result))
    return result


async def get_appointment_by_phone(
    tenant_id: uuid.UUID,
    phone: str,
) -> dict | None:
    """Busca la proxima cita activa de ese telefono en Calendar.

    Returns:
        {"event_id": str, "datetime": str, "service": str, "client_name": str} o None
    """
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=phone)
    log.info("get_appointment_by_phone_start")

    creds, tenant = await get_google_creds(tenant_id)
    calendar_id = tenant.google_calendar_id or "primary"
    now = datetime.now(MADRID_TZ)

    svc = await asyncio.to_thread(
        build, "calendar", "v3", credentials=creds, cache_discovery=False
    )
    events_result = await asyncio.to_thread(
        svc.events().list(
            calendarId=calendar_id,
            timeMin=now.isoformat(),
            q=phone,
            singleEvents=True,
            orderBy="startTime",
            maxResults=5,
        ).execute
    )

    for event in events_result.get("items", []):
        ext_phone = event.get("extendedProperties", {}).get("private", {}).get("phone", "")
        description = event.get("description", "")
        if phone in ext_phone or phone in description:
            start_str = event.get("start", {}).get("dateTime", "")
            parts = event.get("summary", "").split(" - ", 1)
            log.info("appointment_found", event_id=event["id"])
            return {
                "event_id": event["id"],
                "datetime": start_str,
                "service": parts[0] if parts else "",
                "client_name": parts[1] if len(parts) > 1 else "",
            }

    log.info("appointment_not_found")
    return None


async def create_appointment(
    tenant_id: uuid.UUID,
    phone: str,
    client_name: str,
    datetime_iso: str,
    duration_minutes: int,
    service: str,
) -> str:
    """Crea evento en Calendar. Devuelve event_id."""
    log = logger.bind(tenant_id=str(tenant_id), wa_phone=phone)
    log.info("create_appointment_start", client_name=client_name, service=service)

    creds, tenant = await get_google_creds(tenant_id)
    calendar_id = tenant.google_calendar_id or "primary"

    start_dt = datetime.fromisoformat(datetime_iso)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=MADRID_TZ)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    event_body = {
        "summary": f"{service} - {client_name}",
        "description": f"Paciente: {client_name}\nTelefono: {phone}",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Madrid"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Madrid"},
        "extendedProperties": {"private": {"phone": phone}},
    }

    svc = await asyncio.to_thread(
        build, "calendar", "v3", credentials=creds, cache_discovery=False
    )
    event = await asyncio.to_thread(
        svc.events().insert(calendarId=calendar_id, body=event_body).execute
    )
    log.info("create_appointment_done", event_id=event["id"])
    return event["id"]


async def modify_appointment(
    tenant_id: uuid.UUID,
    event_id: str,
    new_datetime_iso: str,
) -> bool:
    """Modifica fecha/hora de un evento. True si OK."""
    log = logger.bind(tenant_id=str(tenant_id))
    log.info("modify_appointment_start", event_id=event_id)

    creds, tenant = await get_google_creds(tenant_id)
    calendar_id = tenant.google_calendar_id or "primary"
    svc = await asyncio.to_thread(
        build, "calendar", "v3", credentials=creds, cache_discovery=False
    )

    try:
        existing = await asyncio.to_thread(
            svc.events().get(calendarId=calendar_id, eventId=event_id).execute
        )
    except Exception as e:
        log.error("modify_get_event_error", error=str(e))
        return False

    old_start = existing["start"].get("dateTime", "")
    old_end = existing["end"].get("dateTime", "")
    duration = (
        datetime.fromisoformat(old_end) - datetime.fromisoformat(old_start)
        if old_start and old_end else timedelta(hours=1)
    )

    new_start = datetime.fromisoformat(new_datetime_iso)
    if new_start.tzinfo is None:
        new_start = new_start.replace(tzinfo=MADRID_TZ)
    new_end = new_start + duration

    patch_body = {
        "start": {"dateTime": new_start.isoformat(), "timeZone": "Europe/Madrid"},
        "end": {"dateTime": new_end.isoformat(), "timeZone": "Europe/Madrid"},
    }

    try:
        await asyncio.to_thread(
            svc.events().patch(
                calendarId=calendar_id, eventId=event_id, body=patch_body
            ).execute
        )
        log.info("modify_appointment_done", event_id=event_id)
        return True
    except Exception as e:
        log.error("modify_appointment_error", event_id=event_id, error=str(e))
        return False


async def cancel_appointment(
    tenant_id: uuid.UUID,
    event_id: str,
) -> bool:
    """Elimina evento de Calendar. True si OK."""
    log = logger.bind(tenant_id=str(tenant_id))
    log.info("cancel_appointment_start", event_id=event_id)

    creds, tenant = await get_google_creds(tenant_id)
    calendar_id = tenant.google_calendar_id or "primary"
    svc = await asyncio.to_thread(
        build, "calendar", "v3", credentials=creds, cache_discovery=False
    )

    try:
        await asyncio.to_thread(
            svc.events().delete(calendarId=calendar_id, eventId=event_id).execute
        )
        log.info("cancel_appointment_done", event_id=event_id)
        return True
    except Exception as e:
        log.error("cancel_appointment_error", event_id=event_id, error=str(e))
        return False


