"""Helpers de disponibilidad de slots y conteo de citas activas."""

import asyncio
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build

from app.services.google_auth import get_google_creds

MADRID_TZ = ZoneInfo("Europe/Madrid")


def slot_is_available(dt_iso: str, slots: list[dict]) -> bool:
    try:
        dt = datetime.fromisoformat(dt_iso)
    except ValueError:
        return False
    d, t = dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    return any(x["date"] == d and t in x["slots"] for x in slots)


def format_slot_conflict_message(free_slots: list[dict]) -> str:
    """Mensaje de conflicto con las 3 primeras alternativas disponibles."""
    alts = [
        f"* {d['day_name'].capitalize()} {datetime.fromisoformat(d['date']).day} a las {s}"
        for d in free_slots for s in d["slots"]
    ][:3]
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
