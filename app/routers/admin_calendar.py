"""Router calendario admin: eventos unificados + bloqueo de huecos + gestión sesiones grupales."""

import asyncio
import json
import uuid
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
from app.models.group_class import (
    GroupClassDefinition,
    GroupClassInscription,
    GroupClassSession,
    SessionState,
)
from app.models.tenant import Tenant
from app.routers.admin import TokenData, get_current_user, require_tenant_scope
from app.schemas.admin import CalendarClassCreate, CalendarSessionDetail, GroupInscriptionRead
from app.services.google_auth import get_google_creds
from app.services.group_class_service import (
    _validate_against_work_blocks,
    create_definition,
    generate_upcoming_sessions,
)

router = APIRouter(prefix="/admin/calendar", tags=["admin-calendar"])
logger = structlog.get_logger()

MADRID_TZ = ZoneInfo("Europe/Madrid")
_FEATURE = "admin.calendar_view"


class BlockRequest(BaseModel):
    start: str
    end: str
    title: str = "Bloqueado"


class BlockPatchRequest(BaseModel):
    start: str
    end: str
    title: str | None = None


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
                "definition_id": str(s.definition_id),
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
            "colorId": "11",
        }
        event = await asyncio.to_thread(
            svc.events().insert(
                calendarId=calendar_id, body=event_body,
            ).execute
        )
        result = {"ok": True, "event_id": event.get("id")}
        try:
            from app.services.websocket_manager import manager
            await manager.broadcast_to_tenant(
                str(tenant.id), {"type": "calendar_event_changed"}
            )
        except Exception:
            pass
        return result
    except Exception as e:
        logger.error("block_slot_error", error=str(e))
        raise HTTPException(status_code=500, detail="Error al bloquear horario")


@router.delete("/block/{event_id}", status_code=204)
async def delete_block(
    event_id: str,
    tenant: Tenant = Depends(require_tenant_scope),
    _user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not await has_feature(tenant.id, _FEATURE, db):
        raise HTTPException(status_code=403, detail="Feature no disponible")
    try:
        creds, _ = await get_google_creds(tenant.id)
        calendar_id = tenant.google_calendar_id or "primary"
        svc = await asyncio.to_thread(
            build, "calendar", "v3", credentials=creds, cache_discovery=False
        )
        await asyncio.to_thread(
            svc.events().delete(calendarId=calendar_id, eventId=event_id).execute
        )
    except Exception as e:
        logger.error("delete_block_error", error=str(e))
        raise HTTPException(status_code=500, detail="Error al borrar el bloqueo")
    try:
        from app.services.websocket_manager import manager
        await manager.broadcast_to_tenant(
            str(tenant.id), {"type": "calendar_event_changed"}
        )
    except Exception:
        pass


@router.patch("/block/{event_id}")
async def update_block(
    event_id: str,
    body: BlockPatchRequest,
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
        patch_body: dict = {
            "start": {"dateTime": body.start, "timeZone": "Europe/Madrid"},
            "end": {"dateTime": body.end, "timeZone": "Europe/Madrid"},
        }
        if body.title is not None:
            patch_body["summary"] = f"Bloqueado - {body.title}"
        event = await asyncio.to_thread(
            svc.events().patch(
                calendarId=calendar_id, eventId=event_id, body=patch_body,
            ).execute
        )
    except Exception as e:
        logger.error("update_block_error", error=str(e))
        raise HTTPException(status_code=500, detail="Error al actualizar el bloqueo")
    try:
        from app.services.websocket_manager import manager
        await manager.broadcast_to_tenant(
            str(tenant.id), {"type": "calendar_event_changed"}
        )
    except Exception:
        pass
    return {"ok": True, "event_id": event.get("id")}


_FEATURE_GROUPS = "groups.templates"


@router.post("/create-class")
async def create_class_from_calendar(
    body: CalendarClassCreate,
    tenant: Tenant = Depends(require_tenant_scope),
    _user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Crear sesión grupal (puntual o recurrente) desde el calendario."""
    if not await has_feature(tenant.id, _FEATURE_GROUPS, db):
        raise HTTPException(status_code=403, detail="No disponible en tu plan")

    from datetime import date as date_type

    try:
        fecha = date_type.fromisoformat(body.fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")

    if fecha < datetime.now(MADRID_TZ).date():
        raise HTTPException(status_code=400, detail="No se puede crear sesión en el pasado")

    if body.recurrente:
        if not body.dias_semana:
            raise HTTPException(status_code=400, detail="Selecciona al menos un día para sesión recurrente")
        try:
            definition = await create_definition(
                tenant.id, body.nombre, body.dias_semana, body.hora,
                body.duracion_min, body.max_capacidad, db,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        await generate_upcoming_sessions(tenant.id, definition.id, 30, db)
        await db.commit()
        return {"ok": True, "definition_id": str(definition.id), "recurrente": True}
    else:
        dias_semana = [fecha.weekday()]
        err = _validate_against_work_blocks(
            tenant.work_blocks, dias_semana, body.hora, body.duracion_min,
        )
        if err:
            raise HTTPException(status_code=400, detail=err)

        definition = GroupClassDefinition(
            tenant_id=tenant.id,
            nombre=body.nombre,
            dias_semana=json.dumps(dias_semana),
            hora=body.hora,
            duracion_min=body.duracion_min,
            max_capacidad=body.max_capacidad,
            activa=False,
        )
        db.add(definition)
        await db.flush()

        session = GroupClassSession(
            id=uuid.uuid4(),
            definition_id=definition.id,
            tenant_id=tenant.id,
            fecha=fecha,
            hora=body.hora,
            estado=SessionState.PROGRAMADA.value,
        )
        db.add(session)
        await db.commit()
        return {"ok": True, "definition_id": str(definition.id), "recurrente": False}


@router.get("/session/{session_id}")
async def get_session_detail(
    session_id: uuid.UUID,
    tenant: Tenant = Depends(require_tenant_scope),
    _user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CalendarSessionDetail:
    """Detalle de una sesión grupal con inscripciones."""
    if not await has_feature(tenant.id, _FEATURE_GROUPS, db):
        raise HTTPException(status_code=403, detail="No disponible en tu plan")

    result = await db.execute(
        select(GroupClassSession).where(
            GroupClassSession.id == session_id,
            GroupClassSession.tenant_id == tenant.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    def_result = await db.execute(
        select(GroupClassDefinition).where(GroupClassDefinition.id == session.definition_id)
    )
    definition = def_result.scalar_one()

    insc_result = await db.execute(
        select(GroupClassInscription).where(
            GroupClassInscription.session_id == session_id,
        ).order_by(GroupClassInscription.created_at)
    )
    inscriptions = insc_result.scalars().all()

    try:
        dias = json.loads(definition.dias_semana)
    except (json.JSONDecodeError, TypeError):
        dias = []

    fecha_str = session.fecha if isinstance(session.fecha, str) else session.fecha.isoformat()

    return CalendarSessionDetail(
        session_id=session.id,
        definition_id=definition.id,
        nombre=definition.nombre,
        fecha=fecha_str,
        hora=session.hora,
        duracion_min=definition.duracion_min,
        max_capacidad=definition.max_capacidad,
        estado=session.estado,
        activa=definition.activa,
        dias_semana=dias,
        inscritos=len(inscriptions),
        inscriptions=[
            GroupInscriptionRead(
                id=i.id,
                wa_phone=i.wa_phone,
                nombre_paciente=i.nombre_paciente,
                created_at=i.created_at,
            )
            for i in inscriptions
        ],
    )


@router.delete("/session/{session_id}")
async def cancel_session(
    session_id: uuid.UUID,
    tenant: Tenant = Depends(require_tenant_scope),
    _user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cancelar una sesión grupal específica."""
    if not await has_feature(tenant.id, _FEATURE_GROUPS, db):
        raise HTTPException(status_code=403, detail="No disponible en tu plan")

    result = await db.execute(
        select(GroupClassSession).where(
            GroupClassSession.id == session_id,
            GroupClassSession.tenant_id == tenant.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    google_event_id = session.google_event_id
    session.estado = SessionState.CANCELADA.value
    await db.commit()
    if google_event_id:
        from app.services.calendar_service import delete_group_calendar_event
        await delete_group_calendar_event(tenant.id, google_event_id)
    try:
        from app.services.websocket_manager import manager
        await manager.broadcast_to_tenant(
            str(tenant.id), {"type": "calendar_event_changed"}
        )
    except Exception:
        pass
    return {"ok": True}
