"""Router de clases grupales: CRUD definiciones, sesiones e inscripciones."""

import json
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.features import has_feature
from app.models.group_class import GroupClassDefinition, GroupClassInscription, GroupClassSession
from app.models.tenant import Tenant
from app.routers.admin import TokenData, get_current_user, require_tenant_scope
from app.schemas.admin import (
    GroupClassCreate,
    GroupClassRead,
    GroupClassUpdate,
    GroupInscriptionRead,
    GroupSessionRead,
)
from app.services.group_class_service import (
    create_definition,
    delete_definition,
    generate_upcoming_sessions,
    list_definitions,
    update_definition,
)

router = APIRouter(prefix="/admin/classes", tags=["admin-classes"])
logger = structlog.get_logger()

_FEATURE = "groups.templates"


def _def_to_read(d: GroupClassDefinition) -> GroupClassRead:
    try:
        dias = json.loads(d.dias_semana)
    except (json.JSONDecodeError, TypeError):
        dias = []
    return GroupClassRead(
        id=d.id,
        nombre=d.nombre,
        dias_semana=dias,
        hora=d.hora,
        duracion_min=d.duracion_min,
        max_capacidad=d.max_capacidad,
        activa=d.activa,
        created_at=d.created_at,
    )


# ---------------------------------------------------------------------------
# Definiciones
# ---------------------------------------------------------------------------


@router.get("", response_model=list[GroupClassRead])
async def list_classes(
    tenant: Tenant = Depends(require_tenant_scope),
    user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GroupClassRead]:
    """Lista definiciones de clases grupales del tenant."""
    if not await has_feature(tenant.id, _FEATURE, db):
        raise HTTPException(status_code=403, detail="Feature no disponible en tu plan")
    definitions = await list_definitions(tenant.id, db, only_active=False)
    return [_def_to_read(d) for d in definitions]


@router.post("", response_model=GroupClassRead, status_code=201)
async def create_class(
    body: GroupClassCreate,
    tenant: Tenant = Depends(require_tenant_scope),
    user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupClassRead:
    if not await has_feature(tenant.id, _FEATURE, db):
        raise HTTPException(status_code=403, detail="Feature no disponible en tu plan")
    definition = await create_definition(
        tenant_id=tenant.id,
        nombre=body.nombre,
        dias_semana=body.dias_semana,
        hora=body.hora,
        duracion_min=body.duracion_min,
        max_capacidad=body.max_capacidad,
        db=db,
    )
    await db.commit()
    await db.refresh(definition)
    return _def_to_read(definition)


@router.put("/{class_id}", response_model=GroupClassRead)
async def update_class(
    class_id: uuid.UUID,
    body: GroupClassUpdate,
    tenant: Tenant = Depends(require_tenant_scope),
    user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupClassRead:
    if not await has_feature(tenant.id, _FEATURE, db):
        raise HTTPException(status_code=403, detail="Feature no disponible en tu plan")
    updates = body.model_dump(exclude_unset=True)
    definition = await update_definition(tenant.id, class_id, updates, db)
    if not definition:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    await db.commit()
    await db.refresh(definition)
    return _def_to_read(definition)


@router.delete("/{class_id}", status_code=204)
async def delete_class(
    class_id: uuid.UUID,
    tenant: Tenant = Depends(require_tenant_scope),
    user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not await has_feature(tenant.id, _FEATURE, db):
        raise HTTPException(status_code=403, detail="Feature no disponible en tu plan")
    deleted = await delete_definition(tenant.id, class_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    await db.commit()


# ---------------------------------------------------------------------------
# Sesiones
# ---------------------------------------------------------------------------


@router.get("/{class_id}/sessions", response_model=list[GroupSessionRead])
async def list_sessions(
    class_id: uuid.UUID,
    tenant: Tenant = Depends(require_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> list[GroupSessionRead]:
    if not await has_feature(tenant.id, _FEATURE, db):
        raise HTTPException(status_code=403, detail="Feature no disponible en tu plan")
    result = await db.execute(
        select(GroupClassSession)
        .where(
            GroupClassSession.definition_id == class_id,
            GroupClassSession.tenant_id == tenant.id,
        )
        .order_by(GroupClassSession.fecha)
    )
    sessions = result.scalars().all()

    out = []
    for s in sessions:
        count_result = await db.execute(
            select(func.count()).where(GroupClassInscription.session_id == s.id)
        )
        inscritos = count_result.scalar() or 0

        defn_result = await db.execute(
            select(GroupClassDefinition).where(GroupClassDefinition.id == s.definition_id)
        )
        defn = defn_result.scalar_one()

        out.append(GroupSessionRead(
            id=s.id,
            definition_id=s.definition_id,
            fecha=s.fecha.isoformat(),
            hora=s.hora,
            estado=s.estado,
            inscritos=inscritos,
            plazas_libres=max(0, defn.max_capacidad - inscritos),
        ))
    return out


@router.post("/{class_id}/sessions/generate", status_code=200)
async def generate_sessions(
    class_id: uuid.UUID,
    days_ahead: int = 14,
    tenant: Tenant = Depends(require_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not await has_feature(tenant.id, _FEATURE, db):
        raise HTTPException(status_code=403, detail="Feature no disponible en tu plan")
    await generate_upcoming_sessions(tenant.id, class_id, days_ahead, db)
    await db.commit()
    return {"ok": True, "days_ahead": days_ahead}


# ---------------------------------------------------------------------------
# Inscripciones
# ---------------------------------------------------------------------------


@router.get("/sessions/{session_id}/inscriptions", response_model=list[GroupInscriptionRead])
async def list_inscriptions(
    session_id: uuid.UUID,
    tenant: Tenant = Depends(require_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> list[GroupInscriptionRead]:
    if not await has_feature(tenant.id, _FEATURE, db):
        raise HTTPException(status_code=403, detail="Feature no disponible en tu plan")
    result = await db.execute(
        select(GroupClassInscription).where(
            GroupClassInscription.session_id == session_id,
            GroupClassInscription.tenant_id == tenant.id,
        )
    )
    inscriptions = result.scalars().all()
    return [
        GroupInscriptionRead(
            id=i.id,
            wa_phone=i.wa_phone,
            nombre_paciente=i.nombre_paciente,
            created_at=i.created_at,
        )
        for i in inscriptions
    ]
