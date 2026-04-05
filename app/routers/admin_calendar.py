"""Router calendario admin: eventos unificados + bloqueo de huecos."""

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from googleapiclient.discovery import build
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.features import has_feature
from app.models.group_class import GroupClassSession, SessionState
from app.models.tenant import Tenant
from app.routers.admin import TokenData, get_current_user, require_tenant_scope
from app.services.google_auth import get_google_creds

router = APIRouter(prefix="/admin/calendar", tags=["admin-calendar"])
logger = structlog.get_logger()

MADRID_TZ = ZoneInfo("Europe/Madrid")
_FEATURE = "admin.calendar_view"


class BlockRequest(BaseModel):
    start: str
    end: str
    title: str = "Bloqueado"


@router.get("/events")
async def get_calendar_events(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    tenant: Tenant = Depends(require_tenant_scope),
    _user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    if not await has_feature(tenant.id, _FEATURE, db):
        raise HTTPException(status_code=403, detail="Feature no disponible")

    start_dt = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=MADRID_TZ)
    end_dt = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=MADRID_TZ)
    events: list[dict] = []

    # 1. Work blocks como background events
    wb = tenant.work_blocks or {}
    current = start_dt
    while current < end_dt:
        day_blocks = wb.get(str(current.weekday()), [])
        for block in day_blocks:
            bstart = current.replace(
                hour=int(block[0].split(":")[0]),
                minute=int(block[0].split(":")[1]),
            )
            bend = current.replace(
                hour=int(block[1].split(":")[0]),
                minute=int(block[1].split(":")[1]),
            )
            events.append({
                "title": "Horario abierto",
                "start": bstart.isoformat(),
                "end": bend.isoformat(),
                "display": "background",
                "color": "#d1fae5",
                "type": "work_block",
            })
        current += timedelta(days=1)

    # 2. Google Calendar events
    try:
        creds, _ = await get_google_creds(tenant.id)
        calendar_id = tenant.google_calendar_id or "primary"
        svc = await asyncio.to_thread(
            build, "calendar", "v3", credentials=creds, cache_discovery=False
        )
        result = await asyncio.to_thread(
            svc.events().list(
                calendarId=calendar_id,
                timeMin=start_dt.isoformat(),
                timeMax=end_dt.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            ).execute
        )
        for ev in result.get("items", []):
            ev_start = ev.get("start", {}).get("dateTime")
            ev_end = ev.get("end", {}).get("dateTime")
            if not ev_start or not ev_end:
                continue
            phone = (
                ev.get("extendedProperties", {})
                .get("private", {})
                .get("phone", "")
            )
            is_blocked = not phone and "Bloqueado" in ev.get("summary", "")
            events.append({
                "id": ev.get("id"),
                "title": ev.get("summary", "Cita"),
                "start": ev_start,
                "end": ev_end,
                "color": "#fca5a5" if is_blocked else "#3b82f6",
                "type": "blocked" if is_blocked else "appointment",
            })
    except Exception as e:
        logger.warning("calendar_events_fetch_error", error=str(e))

    # 3. Group class sessions
    try:
        from app.models.group_class import GroupClassDefinition, GroupClassInscription

        result = await db.execute(
            select(
                GroupClassSession,
                GroupClassDefinition.nombre,
                GroupClassDefinition.duracion_min,
                GroupClassDefinition.max_capacidad,
                func.count(GroupClassInscription.id).label("inscritos"),
            )
            .join(GroupClassDefinition, GroupClassSession.definition_id == GroupClassDefinition.id)
            .outerjoin(GroupClassInscription, GroupClassInscription.session_id == GroupClassSession.id)
            .where(
                GroupClassDefinition.tenant_id == tenant.id,
                GroupClassSession.fecha >= datetime.strptime(start, "%Y-%m-%d").date(),
                GroupClassSession.fecha <= datetime.strptime(end, "%Y-%m-%d").date(),
                GroupClassSession.estado == SessionState.PROGRAMADA.value,
            )
            .group_by(
                GroupClassSession.id,
                GroupClassDefinition.nombre,
                GroupClassDefinition.duracion_min,
                GroupClassDefinition.max_capacidad,
            )
        )
        for s, nombre, dur, cap, inscritos in result.all():
            fecha_str = s.fecha if isinstance(s.fecha, str) else s.fecha.isoformat()
            h, m = map(int, s.hora.split(":"))
            sess_start = datetime.strptime(fecha_str, "%Y-%m-%d").replace(
                hour=h, minute=m, tzinfo=MADRID_TZ,
            )
            sess_end = sess_start + timedelta(minutes=dur)
            events.append({
                "id": f"group_{s.id}",
                "title": f"{nombre} ({inscritos}/{cap})",
                "start": sess_start.isoformat(),
                "end": sess_end.isoformat(),
                "color": "#10b981",
                "type": "group_class",
            })
    except Exception as e:
        logger.warning("group_sessions_fetch_error", error=str(e))

    return events


@router.post("/block")
async def block_calendar_slot(
    body: BlockRequest,
    tenant: Tenant = Depends(require_tenant_scope),
    _user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not await has_feature(tenant.id, _FEATURE, db):
        raise HTTPException(status_code=403, detail="Feature no disponible")

    try:
        creds, _ = await get_google_creds(tenant.id)
        calendar_id = tenant.google_calendar_id or "primary"
        svc = await asyncio.to_thread(
            build, "calendar", "v3", credentials=creds, cache_discovery=False
        )

        event_body = {
            "summary": f"Bloqueado - {body.title}",
            "start": {"dateTime": body.start, "timeZone": "Europe/Madrid"},
            "end": {"dateTime": body.end, "timeZone": "Europe/Madrid"},
        }
        event = await asyncio.to_thread(
            svc.events().insert(
                calendarId=calendar_id, body=event_body,
            ).execute
        )
        return {"ok": True, "event_id": event.get("id")}
    except Exception as e:
        logger.error("block_slot_error", error=str(e))
        raise HTTPException(status_code=500, detail="Error al bloquear horario")
