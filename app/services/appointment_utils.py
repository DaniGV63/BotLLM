"""Helpers de disponibilidad de slots y conteo de citas activas."""

import asyncio
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build

from app.services.google_auth import get_google_creds

MADRID_TZ = ZoneInfo("Europe/Madrid")


def slot_is_available(dt_iso: str, slots: list[dict]) -> bool:
    """Comprueba si dt_iso aparece en la lista plana de slots [{datetime, display}]."""
    try:
        dt = datetime.fromisoformat(dt_iso)
    except ValueError:
        return False
    target = dt.strftime("%Y-%m-%dT%H:%M")
    return any(s["datetime"] == target for s in slots)


def format_slot_conflict_message(free_slots: list[dict]) -> str:
    """Mensaje de conflicto con hasta 3 alternativas del formato plano [{datetime, display}]."""
    alts = [f"* {s['display']}" for s in free_slots[:3]]
    if alts:
        return (
            "Ese hueco ya no está disponible, pero tengo estos:\n\n"
            + "\n".join(alts) + "\n\n¿Te viene bien alguno?"
        )
    return "Ese hueco ya no está disponible. Contacta directamente con la clínica."


async def count_active_appointments(
    tenant_id: uuid.UUID, phone: str,
) -> int:
    """Cuenta citas futuras del paciente en Calendar. Devuelve 0 si falla."""
    try:
        creds, tenant = await get_google_creds(tenant_id)
        svc = await asyncio.to_thread(
            build, "calendar", "v3", credentials=creds, cache_discovery=False
        )
        r = await asyncio.to_thread(
            svc.events().list(
                calendarId=tenant.google_calendar_id or "primary",
                timeMin=datetime.now(MADRID_TZ).isoformat(),
                q=phone, singleEvents=True, maxResults=20,
            ).execute
        )
        return sum(
            1 for ev in r.get("items", [])
            if phone in ev.get("extendedProperties", {}).get("private", {}).get("phone", "")
            or phone in ev.get("description", "")
        )
    except Exception:
        return 0
