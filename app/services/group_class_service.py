"""Servicio de clases grupales: CRUD definiciones, sesiones, inscripciones."""

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.group_class import (
    GroupClassDefinition,
    GroupClassInscription,
    GroupClassSession,
    SessionState,
)
from app.models.tenant import Tenant
from app.services.calendar_service import (
    create_group_calendar_event,
    update_group_calendar_attendees,
)
from app.services.email_service import send_cancellation_alert_email

logger = structlog.get_logger()
MADRID_TZ = ZoneInfo("Europe/Madrid")

_DAY_NAMES_ES = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def _validate_against_work_blocks(
    work_blocks: dict | None,
    dias_semana: list[int],
    hora: str,
    duracion_min: int,
) -> str | None:
    """Valida que la clase cae dentro de los work_blocks del tenant.

    Returns:
        None si es valido, string con error si no.
    """
    if not work_blocks:
        return None
    h, m = map(int, hora.split(":"))
    class_start_min = h * 60 + m
    class_end_min = class_start_min + duracion_min
    for day in dias_semana:
        blocks = work_blocks.get(str(day), [])
        if not blocks:
            return f"El día {_DAY_NAMES_ES[day]} está cerrado según el horario configurado"
        fits = False
        for block in blocks:
            bh, bm = map(int, block[0].split(":"))
            eh, em = map(int, block[1].split(":"))
            block_start = bh * 60 + bm
            block_end = eh * 60 + em
            if class_start_min >= block_start and class_end_min <= block_end:
                fits = True
                break
        if not fits:
            return f"La clase {hora} ({duracion_min}min) no cabe en los bloques del {_DAY_NAMES_ES[day]}"
    return None


# ---------------------------------------------------------------------------
# CRUD definiciones
# ---------------------------------------------------------------------------


async def create_definition(
    tenant_id: uuid.UUID,
    nombre: str,
    dias_semana: list[int],
    hora: str,
    duracion_min: int,
    max_capacidad: int,
    db: AsyncSession,
) -> GroupClassDefinition:
    # Validar contra work_blocks del tenant
    tenant = await db.get(Tenant, tenant_id)
    if tenant:
        err = _validate_against_work_blocks(
            getattr(tenant, "work_blocks", None), dias_semana, hora, duracion_min,
        )
        if err:
            raise ValueError(err)

    definition = GroupClassDefinition(
        tenant_id=tenant_id,
        nombre=nombre,
        dias_semana=json.dumps(dias_semana),
        hora=hora,
        duracion_min=duracion_min,
        max_capacidad=max_capacidad,
    )
    db.add(definition)
    await db.flush()
    logger.bind(tenant_id=str(tenant_id)).info("group_class_definition_created", id=str(definition.id))
    return definition


async def update_definition(
    tenant_id: uuid.UUID,
    definition_id: uuid.UUID,
    updates: dict,
    db: AsyncSession,
) -> GroupClassDefinition | None:
    result = await db.execute(
        select(GroupClassDefinition).where(
            GroupClassDefinition.id == definition_id,
            GroupClassDefinition.tenant_id == tenant_id,
        )
    )
    definition = result.scalar_one_or_none()
    if not definition:
        return None
    # Validar contra work_blocks si cambian dias/hora/duracion
    if any(k in updates for k in ("dias_semana", "hora", "duracion_min")):
        tenant = await db.get(Tenant, tenant_id)
        if tenant:
            check_dias = updates.get("dias_semana", json.loads(definition.dias_semana))
            check_hora = updates.get("hora", definition.hora)
            check_dur = updates.get("duracion_min", definition.duracion_min)
            err = _validate_against_work_blocks(
                getattr(tenant, "work_blocks", None), check_dias, check_hora, check_dur,
            )
            if err:
                raise ValueError(err)
    if "dias_semana" in updates:
        updates["dias_semana"] = json.dumps(updates["dias_semana"])
    for field, value in updates.items():
        setattr(definition, field, value)
    await db.flush()
    return definition


async def delete_definition(
    tenant_id: uuid.UUID,
    definition_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    result = await db.execute(
        select(GroupClassDefinition).where(
            GroupClassDefinition.id == definition_id,
            GroupClassDefinition.tenant_id == tenant_id,
        )
    )
    definition = result.scalar_one_or_none()
    if not definition:
        return False
    await db.delete(definition)
    await db.flush()
    return True


async def list_definitions(
    tenant_id: uuid.UUID,
    db: AsyncSession,
    only_active: bool = True,
) -> list[GroupClassDefinition]:
    query = select(GroupClassDefinition).where(GroupClassDefinition.tenant_id == tenant_id)
    if only_active:
        query = query.where(GroupClassDefinition.activa.is_(True))
    result = await db.execute(query.order_by(GroupClassDefinition.nombre))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Sesiones — generación lazy e idempotente
# ---------------------------------------------------------------------------


async def generate_upcoming_sessions(
    tenant_id: uuid.UUID,
    definition_id: uuid.UUID,
    days_ahead: int,
    db: AsyncSession,
) -> None:
    """Genera sesiones faltantes para los próximos N días (idempotente)."""
    result = await db.execute(
        select(GroupClassDefinition).where(
            GroupClassDefinition.id == definition_id,
            GroupClassDefinition.tenant_id == tenant_id,
            GroupClassDefinition.activa.is_(True),
        )
    )
    definition = result.scalar_one_or_none()
    if not definition:
        return

    try:
        dias = json.loads(definition.dias_semana)
    except (json.JSONDecodeError, TypeError):
        return

    today = datetime.now(MADRID_TZ).date()
    for offset in range(1, days_ahead + 1):
        day = today + timedelta(days=offset)
        if day.weekday() not in dias:
            continue
        new_id = uuid.uuid4()
        stmt = (
            pg_insert(GroupClassSession)
            .values(
                id=new_id,
                definition_id=definition_id,
                tenant_id=tenant_id,
                fecha=day,
                hora=definition.hora,
                estado=SessionState.PROGRAMADA.value,
            )
            .on_conflict_do_nothing(constraint="uq_session_definition_fecha")
        )
        await db.execute(stmt)
        # Intentar obtener la sesión recién insertada (None si ya existía → idempotente)
        sess_result = await db.execute(
            select(GroupClassSession).where(
                GroupClassSession.id == new_id,
                GroupClassSession.google_event_id.is_(None),
            )
        )
        session = sess_result.scalar_one_or_none()
        if session:
            h, m = map(int, definition.hora.split(":"))
            dt_iso = datetime(
                day.year, day.month, day.day, h, m, tzinfo=MADRID_TZ
            ).isoformat()
            gev_id = await create_group_calendar_event(
                tenant_id, definition.nombre, dt_iso, definition.duracion_min
            )
            if gev_id:
                session.google_event_id = gev_id


async def get_available_sessions(
    tenant_id: uuid.UUID,
    days_ahead: int,
    db: AsyncSession,
) -> list[dict]:
    """Devuelve sesiones con plazas disponibles en los próximos N días."""
    definitions = await list_definitions(tenant_id, db)
    for defn in definitions:
        await generate_upcoming_sessions(tenant_id, defn.id, days_ahead, db)

    today = datetime.now(MADRID_TZ).date()
    fecha_max = today + timedelta(days=days_ahead)

    sessions_result = await db.execute(
        select(GroupClassSession, GroupClassDefinition)
        .join(GroupClassDefinition, GroupClassSession.definition_id == GroupClassDefinition.id)
        .where(
            GroupClassSession.tenant_id == tenant_id,
            GroupClassSession.estado == SessionState.PROGRAMADA.value,
            GroupClassSession.fecha > today,
            GroupClassSession.fecha <= fecha_max,
        )
        .order_by(GroupClassSession.fecha, GroupClassSession.hora)
    )
    rows = sessions_result.all()

    available = []
    for session, definition in rows:
        count_result = await db.execute(
            select(func.count()).where(GroupClassInscription.session_id == session.id)
        )
        inscritos = count_result.scalar() or 0
        plazas_libres = definition.max_capacidad - inscritos
        if plazas_libres > 0:
            available.append({
                "session_id": session.id,
                "definition_id": definition.id,
                "nombre": definition.nombre,
                "fecha": session.fecha,
                "hora": session.hora,
                "plazas_libres": plazas_libres,
                "max_capacidad": definition.max_capacidad,
            })
    return available


# ---------------------------------------------------------------------------
# Inscripciones
# ---------------------------------------------------------------------------


async def inscribe_patient(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    wa_phone: str,
    nombre: str | None,
    db: AsyncSession,
) -> dict:
    """Inscribe al paciente. Retorna {"ok": True} o {"ok": False, "reason": ...}."""
    log = logger.bind(tenant_id=str(tenant_id), session_id=str(session_id))

    session_result = await db.execute(
        select(GroupClassSession)
        .where(GroupClassSession.id == session_id, GroupClassSession.tenant_id == tenant_id)
        .with_for_update()
    )
    session = session_result.scalar_one_or_none()
    if not session or session.estado != SessionState.PROGRAMADA.value:
        return {"ok": False, "reason": "session_not_found"}

    def_result = await db.execute(
        select(GroupClassDefinition).where(GroupClassDefinition.id == session.definition_id)
    )
    definition = def_result.scalar_one()

    count_result = await db.execute(
        select(func.count()).where(GroupClassInscription.session_id == session_id)
    )
    inscritos = count_result.scalar() or 0
    if inscritos >= definition.max_capacidad:
        return {"ok": False, "reason": "full"}

    existing = await db.execute(
        select(GroupClassInscription).where(
            GroupClassInscription.session_id == session_id,
            GroupClassInscription.wa_phone == wa_phone,
        )
    )
    if existing.scalar_one_or_none():
        return {"ok": False, "reason": "already_inscribed"}

    inscription = GroupClassInscription(
        session_id=session_id,
        tenant_id=tenant_id,
        wa_phone=wa_phone,
        nombre_paciente=nombre,
    )
    db.add(inscription)
    await db.flush()
    log.info("patient_inscribed", wa_phone=wa_phone)

    # Actualizar descripción del evento GCal con la lista de inscritos
    if session.google_event_id:
        all_insc_result = await db.execute(
            select(GroupClassInscription).where(GroupClassInscription.session_id == session_id)
        )
        all_insc = all_insc_result.scalars().all()
        insc_list = [{"nombre": i.nombre_paciente, "phone": i.wa_phone} for i in all_insc]
        await update_group_calendar_attendees(tenant_id, session.google_event_id, insc_list)

    return {"ok": True, "plazas_libres": definition.max_capacidad - inscritos - 1}


async def cancel_inscription(
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    wa_phone: str,
    db: AsyncSession,
) -> bool:
    """Cancela inscripción. Dispara alerta si es <24h antes de la sesión."""
    result = await db.execute(
        select(GroupClassInscription, GroupClassSession)
        .join(GroupClassSession, GroupClassInscription.session_id == GroupClassSession.id)
        .where(
            GroupClassInscription.session_id == session_id,
            GroupClassInscription.wa_phone == wa_phone,
            GroupClassInscription.tenant_id == tenant_id,
        )
    )
    row = result.first()
    if not row:
        return False

    inscription, session = row
    google_event_id = session.google_event_id
    await db.delete(inscription)
    await db.flush()
    logger.bind(tenant_id=str(tenant_id)).info("inscription_cancelled", wa_phone=wa_phone)

    # Alerta <24h
    session_dt = datetime.combine(session.fecha, _parse_hora(session.hora), tzinfo=MADRID_TZ)
    now = datetime.now(MADRID_TZ)
    if 0 < (session_dt - now).total_seconds() < 86400:
        appointment_str = f"{session.fecha.strftime('%d/%m/%Y')} {session.hora}"
        await send_cancellation_alert_email(
            tenant_id=tenant_id,
            patient_name=inscription.nombre_paciente,
            patient_phone=wa_phone,
            appointment_datetime=appointment_str,
        )

    # Actualizar descripción del evento GCal con la lista de inscritos restantes
    if google_event_id:
        all_insc_result = await db.execute(
            select(GroupClassInscription).where(GroupClassInscription.session_id == session_id)
        )
        all_insc = all_insc_result.scalars().all()
        insc_list = [{"nombre": i.nombre_paciente, "phone": i.wa_phone} for i in all_insc]
        await update_group_calendar_attendees(tenant_id, google_event_id, insc_list)

    return True


def _parse_hora(hora: str) -> object:
    from datetime import time as dtime
    h, m = hora.split(":")
    return dtime(int(h), int(m))


# ---------------------------------------------------------------------------
# Formato para el bot
# ---------------------------------------------------------------------------


async def get_group_slots_for_bot(
    tenant_id: uuid.UUID,
    days_ahead: int,
    db: AsyncSession,
) -> list[dict]:
    """Slots grupales con plazas, agrupados por fecha. Cada slot incluye session_id para el LLM."""
    sessions = await get_available_sessions(tenant_id, days_ahead, db)
    by_date: dict[date, list[dict]] = {}
    for s in sessions:
        slot = {
            "label": f"{s['hora']} - {s['nombre']} grupal ({s['plazas_libres']} plazas)",
            "session_id": str(s["session_id"]),
            "hora": s["hora"],
        }
        by_date.setdefault(s["fecha"], []).append(slot)

    return [
        {
            "date": d.strftime("%Y-%m-%d"),
            "day_name": _DAY_NAMES_ES[d.weekday()],
            "slots": slots,
        }
        for d, slots in sorted(by_date.items())
    ]


async def get_patient_upcoming_inscriptions(
    tenant_id: uuid.UUID,
    wa_phone: str,
    db: AsyncSession,
) -> list[dict]:
    """Devuelve las inscripciones futuras del paciente en clases grupales.

    Returns:
        [{"session_id": str, "nombre": str, "fecha": str, "hora": str}]
    """
    today = datetime.now(MADRID_TZ).date()
    result = await db.execute(
        select(GroupClassInscription, GroupClassSession, GroupClassDefinition)
        .join(GroupClassSession, GroupClassInscription.session_id == GroupClassSession.id)
        .join(GroupClassDefinition, GroupClassSession.definition_id == GroupClassDefinition.id)
        .where(
            GroupClassInscription.tenant_id == tenant_id,
            GroupClassInscription.wa_phone == wa_phone,
            GroupClassSession.estado == SessionState.PROGRAMADA.value,
            GroupClassSession.fecha >= today,
        )
        .order_by(GroupClassSession.fecha, GroupClassSession.hora)
    )
    rows = result.all()
    upcoming = []
    for insc, session, definition in rows:
        fecha_str = session.fecha if isinstance(session.fecha, str) else session.fecha.isoformat()
        upcoming.append({
            "session_id": str(session.id),
            "nombre": definition.nombre,
            "fecha": fecha_str,
            "hora": session.hora,
        })
    return upcoming
