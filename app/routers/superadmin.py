"""Router super admin: gestión global de tenants y usuarios."""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.features import (
    FEATURE_REGISTRY,
    get_tenant_features,
    invalidate_feature_cache,
)
from app.core.security import hash_password
from app.models.admin_user import AdminRole, AdminUser
from app.models.tenant import Tenant
from app.routers.admin import TokenData, _tenant_to_read, require_super_admin
from app.schemas.admin import (
    AdminUserCreate,
    AdminUserRead,
    FeatureInfo,
    TenantCreate,
    TenantFeaturesResponse,
    TenantListItem,
    TenantListResponse,
    TenantOnboardingStatus,
    TenantRead,
)

router = APIRouter(prefix="/superadmin", tags=["superadmin"])
logger = structlog.get_logger()


def _tenant_to_list_item(tenant: Tenant) -> TenantListItem:
    return TenantListItem(
        id=tenant.id,
        slug=tenant.slug,
        nombre_negocio=tenant.nombre_negocio,
        email_notificaciones=tenant.email_notificaciones,
        bot_activo=tenant.bot_activo,
        activo=tenant.activo,
        created_at=tenant.created_at,
        plan=tenant.plan,
        plan_expires_at=tenant.plan_expires_at,
    )


@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    _: TokenData = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantListResponse:
    """Lista todos los tenants."""
    count_r = await db.execute(select(func.count(Tenant.id)))
    total = count_r.scalar() or 0

    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    tenants = result.scalars().all()

    return TenantListResponse(
        tenants=[_tenant_to_list_item(t) for t in tenants],
        total=total,
    )


@router.post("/tenants", response_model=TenantRead)
async def create_tenant(
    body: TenantCreate,
    _: TokenData = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantRead:
    """Crea un nuevo tenant."""
    existing = await db.execute(
        select(Tenant).where(Tenant.slug == body.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Slug '{body.slug}' ya existe")

    tenant = Tenant(
        slug=body.slug,
        nombre_negocio=body.nombre_negocio,
        email_notificaciones=body.email_notificaciones,
        whatsapp_phone_number_id=body.whatsapp_phone_number_id,
        whatsapp_verify_token=body.whatsapp_verify_token or str(uuid.uuid4()),
        bot_activo=body.bot_activo,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    logger.info("tenant_created", tenant_id=str(tenant.id), slug=tenant.slug)

    return _tenant_to_read(tenant)


@router.get("/users", response_model=list[AdminUserRead])
async def list_users(
    _: TokenData = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminUserRead]:
    """Lista todos los usuarios admin."""
    result = await db.execute(select(AdminUser).order_by(AdminUser.created_at.desc()))
    users = result.scalars().all()
    return [
        AdminUserRead(
            id=u.id,
            tenant_id=u.tenant_id,
            username=u.username,
            role=u.role,
            email=u.email,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/users", response_model=AdminUserRead, status_code=201)
async def create_tenant_admin(
    body: AdminUserCreate,
    _: TokenData = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminUserRead:
    """Crea un nuevo usuario tenant_admin para el tenant indicado."""
    # Verificar que el tenant existe
    tenant_r = await db.execute(select(Tenant).where(Tenant.id == body.tenant_id))
    if not tenant_r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    # Verificar username único
    existing_r = await db.execute(
        select(AdminUser).where(AdminUser.username == body.username)
    )
    if existing_r.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Username '{body.username}' ya existe")

    user = AdminUser(
        tenant_id=body.tenant_id,
        username=body.username,
        password_hash=hash_password(body.password),
        role=AdminRole.TENANT_ADMIN,
        email=body.email,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("tenant_admin_created", user_id=str(user.id), tenant_id=str(body.tenant_id))

    return AdminUserRead(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        role=user.role,
        email=user.email,
        created_at=user.created_at,
    )


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID,
    current: TokenData = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Elimina un usuario admin. No se puede eliminar a sí mismo."""
    if user_id == current.user_id:
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")

    result = await db.execute(select(AdminUser).where(AdminUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.role == AdminRole.SUPER_ADMIN:
        raise HTTPException(status_code=400, detail="No se puede eliminar a otro super admin")

    await db.delete(user)
    await db.commit()
    logger.info("admin_user_deleted", user_id=str(user_id))


@router.get("/tenants/{tenant_id}/onboarding-status", response_model=TenantOnboardingStatus)
async def get_onboarding_status(
    tenant_id: uuid.UUID,
    _: TokenData = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantOnboardingStatus:
    """Devuelve el estado de configuración de un tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    whatsapp_ok = bool(tenant.whatsapp_phone_number_id and tenant.whatsapp_token)
    google_ok = bool(tenant.google_access_token and tenant.google_refresh_token)

    missing: list[str] = []
    if not tenant.whatsapp_token:
        missing.append("whatsapp_token — pégalo desde Meta Console → System User → Token")
    if not tenant.whatsapp_phone_number_id:
        missing.append("whatsapp_phone_number_id — cópialo desde Meta Console → WhatsApp → Phone Numbers")
    if not tenant.google_access_token or not tenant.google_refresh_token:
        missing.append("google_tokens — usa 'Autorizar Google' en el panel admin")
    if not tenant.google_calendar_id:
        missing.append("google_calendar_id — pregunta al cliente qué calendario usa (normalmente su email)")

    return TenantOnboardingStatus(
        slug=tenant.slug,
        nombre_negocio=tenant.nombre_negocio,
        whatsapp_configured=whatsapp_ok,
        google_configured=google_ok,
        missing_steps=missing,
    )


@router.get("/tenants/{tenant_id}/features", response_model=TenantFeaturesResponse)
async def get_tenant_features_endpoint(
    tenant_id: uuid.UUID,
    _: TokenData = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantFeaturesResponse:
    """Devuelve features de un tenant con estado de override."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    feature_map = await get_tenant_features(tenant_id, db)
    features = [
        FeatureInfo(
            key=k,
            name=FEATURE_REGISTRY[k].name,
            description=FEATURE_REGISTRY[k].description,
            enabled=v,
            status=FEATURE_REGISTRY[k].status.value,
            stability=FEATURE_REGISTRY[k].stability.value,
        )
        for k, v in feature_map.items()
    ]
    return TenantFeaturesResponse(
        plan=tenant.plan,
        plan_expires_at=tenant.plan_expires_at,
        features=features,
        feature_overrides=tenant.feature_overrides or {},
    )


@router.put("/tenants/{tenant_id}/plan")
async def update_tenant_plan(
    tenant_id: uuid.UUID,
    body: dict,
    _: TokenData = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Cambia el plan de un tenant. Body: {"plan": "PAID"} o {"plan": "FREE_TRIAL", "plan_expires_at": "..."}."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    valid_plans = {"SIN_PLAN", "FREE_TRIAL", "PAID"}
    new_plan = body.get("plan")
    if new_plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Plan invalido. Opciones: {valid_plans}")

    tenant.plan = new_plan
    if "plan_expires_at" in body:
        from datetime import datetime, timezone
        raw = body["plan_expires_at"]
        if raw is None:
            tenant.plan_expires_at = None
        else:
            tenant.plan_expires_at = datetime.fromisoformat(raw.replace("Z", "+00:00")) if isinstance(raw, str) else raw
    await db.commit()
    await invalidate_feature_cache(tenant_id)
    logger.info("tenant_plan_updated", tenant_id=str(tenant_id), plan=new_plan)
    return {"ok": True, "plan": new_plan}


@router.put("/tenants/{tenant_id}/features")
async def update_tenant_feature_overrides(
    tenant_id: uuid.UUID,
    body: dict,
    _: TokenData = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Actualiza feature overrides de un tenant. Body: {"calendar.schedule": true, "handoff.web_chat": false}."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    invalid_keys = [k for k in body if k not in FEATURE_REGISTRY]
    if invalid_keys:
        raise HTTPException(status_code=400, detail=f"Features desconocidas: {invalid_keys}")

    tenant.feature_overrides = body
    await db.commit()
    await invalidate_feature_cache(tenant_id)
    logger.info("tenant_features_updated", tenant_id=str(tenant_id), overrides=body)
    return {"ok": True, "feature_overrides": body}
