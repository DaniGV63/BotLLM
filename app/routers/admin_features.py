"""Router de features: endpoints separados de admin.py para no superar 400 lineas."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.features import (
    FEATURE_REGISTRY,
    get_tenant_features,
)
from app.models.tenant import Tenant
from app.routers.admin import require_tenant_scope
from app.schemas.admin import FeatureInfo, TenantFeaturesResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/features", response_model=TenantFeaturesResponse)
async def get_features(
    tenant: Tenant = Depends(require_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> TenantFeaturesResponse:
    """Devuelve las features habilitadas para el tenant actual."""
    feature_map = await get_tenant_features(tenant.id, db)

    features = []
    for key, enabled in feature_map.items():
        defn = FEATURE_REGISTRY[key]
        features.append(FeatureInfo(
            key=key,
            name=defn.name,
            description=defn.description,
            enabled=enabled,
            status=defn.status.value,
            stability=defn.stability.value,
        ))

    return TenantFeaturesResponse(
        plan=tenant.plan,
        plan_expires_at=tenant.plan_expires_at,
        features=features,
    )
