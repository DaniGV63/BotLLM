# Prompt para Sonnet 4.6 — Implementar Sistema de Features & Planes

## Instruccion Principal

Implementa el sistema de feature flags y planes para Attendoo siguiendo EXACTAMENTE el diseno descrito en `FEATURES.md` (ya existe en el repo). Lee `FEATURES.md`, `CLAUDE.md`, `PLAN.md` antes de empezar.

**IMPORTANTE**: Lee cada archivo que vayas a modificar ANTES de editarlo. No asumas contenido.

---

## Contexto

Attendoo es un bot de WhatsApp multi-tenant para clinicas de fisioterapia. Necesitamos:
- 3 planes: `SIN_PLAN` (usuario sin tenant activo), `FREE_TRIAL` (14 dias), `PAID` (todo)
- Feature registry en codigo con dotted keys (`calendar.schedule`, `admin.metrics`, etc.)
- Per-tenant overrides via JSONB (superadmin puede dar/quitar features individuales)
- Cache Redis 60s para no golpear PG en cada mensaje
- Tests unitarios

---

## Orden de Implementacion (seguir este orden exacto)

### Paso 1: `app/models/enums.py` — Anadir TenantPlan

Anadir al archivo existente (que ya tiene `ConversationState` y `MessageRole`):

```python
class TenantPlan(str, enum.Enum):
    SIN_PLAN = "SIN_PLAN"
    FREE_TRIAL = "FREE_TRIAL"
    PAID = "PAID"
```

---

### Paso 2: `app/core/features.py` — CREAR archivo nuevo (~250 lineas)

Este es el corazon del sistema. Contiene:

**Imports y dataclass:**
```python
import enum
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TenantPlan


class FeatureStatus(str, enum.Enum):
    IMPLEMENTED = "implementada"
    IN_PROGRESS = "en-progreso"
    PENDING = "pendiente"


class FeatureDifficulty(str, enum.Enum):
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


class FeaturePriority(str, enum.Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class FeatureStability(str, enum.Enum):
    ESTABLE = "estable"
    BETA = "beta"
    EXPERIMENTAL = "experimental"


class ConversionImpact(str, enum.Enum):
    ALTO = "alto"
    MEDIO = "medio"
    BAJO = "bajo"


@dataclass(frozen=True)
class FeatureDefinition:
    key: str
    name: str
    description: str
    plans: tuple[TenantPlan, ...]  # planes que incluyen esta feature
    status: FeatureStatus
    difficulty: FeatureDifficulty
    priority: FeaturePriority
    stability: FeatureStability
    conversion_impact: ConversionImpact
    dependencies: tuple[str, ...] = ()
    version: str = ""
    always_enabled: bool = False  # core, security, oauth, backup
```

**FEATURE_REGISTRY** — diccionario plano con TODAS las features de `FEATURES.md`. Ejemplo de algunas entradas (implementar TODAS las que aparecen en FEATURES.md):

```python
FEATURE_REGISTRY: dict[str, FeatureDefinition] = {
    # --- Core (always_enabled) ---
    "core.whatsapp_bot": FeatureDefinition(
        key="core.whatsapp_bot",
        name="Bot WhatsApp",
        description="Motor principal del bot con deteccion de intenciones",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.XL,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.ALTO,
        always_enabled=True,
        version="v1.0",
    ),
    # ... (TODAS las features de FEATURES.md)

    # --- Calendar (free+paid) ---
    "calendar.schedule": FeatureDefinition(
        key="calendar.schedule",
        name="Agendar citas",
        description="Crear citas via Google Calendar",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.L,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.ALTO,
        dependencies=("oauth.google_calendar",),
        version="v1.0",
    ),

    # --- Admin (metrics es solo PAID) ---
    "admin.metrics": FeatureDefinition(
        key="admin.metrics",
        name="Analiticas de datos",
        description="Dashboard de metricas del tenant",
        plans=(TenantPlan.PAID,),  # SOLO PAID
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.ALTO,
        version="v1.1",
    ),

    # ... etc. para handoff.*, groups.*, reminders.*, etc.
}
```

**PLAN_FEATURES** — derivado automaticamente del registry:
```python
PLAN_FEATURES: dict[TenantPlan, frozenset[str]] = {
    plan: frozenset(
        f.key for f in FEATURE_REGISTRY.values()
        if plan in f.plans or f.always_enabled
    )
    for plan in TenantPlan
}

FREE_TRIAL_DURATION_DAYS = 14
```

**Funcion `_resolve_features`:**
```python
def _resolve_features(tenant) -> dict[str, bool]:
    """Construye mapa completo de features para un tenant."""
    from app.models.enums import TenantPlan as TP

    plan = TP(tenant.plan) if tenant.plan else TP.SIN_PLAN

    # FREE_TRIAL expirado → degrada a SIN_PLAN
    if plan == TP.FREE_TRIAL and tenant.plan_expires_at:
        if datetime.now(timezone.utc) > tenant.plan_expires_at:
            plan = TP.SIN_PLAN

    # Features del plan
    plan_features = PLAN_FEATURES.get(plan, frozenset())
    result = {}
    for key, feat in FEATURE_REGISTRY.items():
        if feat.always_enabled:
            result[key] = True
        elif key in plan_features:
            result[key] = True
        else:
            result[key] = False

    # Aplicar overrides del tenant (maxima prioridad)
    overrides = tenant.feature_overrides or {}
    for key, value in overrides.items():
        if key in FEATURE_REGISTRY:
            result[key] = bool(value)

    return result
```

**Funciones publicas:**
```python
async def get_tenant_features(tenant_id: uuid.UUID, db: AsyncSession) -> dict[str, bool]:
    """Devuelve mapa completo de features para un tenant. Con cache Redis 60s."""
    from app.core.redis import get_redis
    from app.models.tenant import Tenant

    redis = await get_redis()
    cache_key = f"features:{tenant_id}"
    cached = await redis.get(cache_key)

    if cached:
        return json.loads(cached)

    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        return {k: False for k in FEATURE_REGISTRY}

    resolved = _resolve_features(tenant)
    await redis.set(cache_key, json.dumps(resolved), ex=60)
    return resolved


async def has_feature(tenant_id: uuid.UUID, feature_key: str, db: AsyncSession) -> bool:
    """Comprueba si un tenant tiene acceso a una feature."""
    features = await get_tenant_features(tenant_id, db)
    return features.get(feature_key, False)


async def invalidate_feature_cache(tenant_id: uuid.UUID) -> None:
    """Invalida cache de features al cambiar plan u overrides."""
    from app.core.redis import get_redis
    redis = await get_redis()
    await redis.delete(f"features:{tenant_id}")
```

**Dependency FastAPI:**
```python
from fastapi import Depends, HTTPException


def require_feature(feature_key: str):
    """FastAPI dependency: requiere que el tenant tenga acceso a una feature."""
    async def _check(tenant=None, db=None):
        # Los imports se resuelven en el router que lo use
        # Ver implementacion en admin_features.py
        if tenant and not await has_feature(tenant.id, feature_key, db):
            raise HTTPException(
                status_code=403,
                detail=f"Feature '{feature_key}' no disponible en tu plan",
            )
        return tenant
    return _check
```

---

### Paso 3: `app/models/tenant.py` — Anadir 3 columnas

Anadir al modelo Tenant existente, en la seccion "Estado" (despues de `activo`):

```python
from sqlalchemy.dialects.postgresql import JSONB

# Plan y features
plan: Mapped[str] = mapped_column(
    String(20), nullable=False, server_default="SIN_PLAN"
)
plan_expires_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), nullable=True
)
feature_overrides: Mapped[dict | None] = mapped_column(
    JSONB, nullable=False, server_default="{}"
)
```

---

### Paso 4: Migracion Alembic

Crear migracion `alembic/versions/f7a1b2c3d4e5_add_tenant_plan_features.py`:

```python
"""add tenant plan and features

Revision ID: f7a1b2c3d4e5
Revises: e1f2a3b4c5d6
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "f7a1b2c3d4e5"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("plan", sa.String(20), nullable=False, server_default="SIN_PLAN"))
    op.add_column("tenants", sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tenants", sa.Column("feature_overrides", JSONB(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("tenants", "feature_overrides")
    op.drop_column("tenants", "plan_expires_at")
    op.drop_column("tenants", "plan")
```

**IMPORTANTE**: Verificar que `down_revision` coincide con la ultima migracion existente. Lee `alembic/versions/` para comprobarlo. La ultima es `e1f2a3b4c5d6`.

---

### Paso 5: `app/schemas/admin.py` — Anadir schemas

Anadir campos a schemas existentes y crear nuevos:

**En `TenantRead`** — anadir:
```python
plan: str
plan_expires_at: datetime | None
feature_overrides: dict
```

**En `TenantUpdate`** — anadir (al final, son super-admin only):
```python
plan: str | None = None
plan_expires_at: datetime | None = None
feature_overrides: dict | None = None
```

**En `TenantCreate`** — anadir:
```python
plan: str = "FREE_TRIAL"
```

**En `TenantListItem`** — anadir:
```python
plan: str
```

**Nuevo schema al final del archivo:**
```python
# --- Features ---


class FeatureInfo(BaseModel):
    key: str
    name: str
    description: str
    enabled: bool
    status: str
    stability: str


class TenantFeaturesResponse(BaseModel):
    plan: str
    plan_expires_at: datetime | None
    features: list[FeatureInfo]
```

---

### Paso 6: `app/routers/admin_features.py` — CREAR archivo nuevo (~80 lineas)

```python
"""Router de features: endpoints separados de admin.py para no superar 400 lineas."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.features import (
    FEATURE_REGISTRY,
    get_tenant_features,
    has_feature,
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
```

---

### Paso 7: `app/routers/admin.py` — Modificaciones minimas

1. Anadir `plan`, `plan_expires_at`, `feature_overrides` a `_SUPER_ONLY_FIELDS`:
```python
_SUPER_ONLY_FIELDS = {
    "whatsapp_token",
    "google_calendar_id",
    "google_access_token",
    "google_refresh_token",
    "google_token_expiry",
    "plan",
    "plan_expires_at",
    "feature_overrides",
}
```

2. Actualizar `_tenant_to_read` para incluir los nuevos campos:
```python
def _tenant_to_read(tenant: Tenant) -> TenantRead:
    return TenantRead(
        # ... campos existentes ...
        plan=tenant.plan,
        plan_expires_at=tenant.plan_expires_at,
        feature_overrides=tenant.feature_overrides or {},
    )
```

3. Proteger endpoint de metricas con feature check. Anadir import y modificar:
```python
from app.core.features import has_feature

# En el endpoint get_metrics, al inicio (antes de cualquier query):
@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    tenant: Tenant = Depends(require_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> MetricsResponse:
    """Metricas de actividad del tenant."""
    if not await has_feature(tenant.id, "admin.metrics", db):
        raise HTTPException(status_code=403, detail="Analiticas no disponibles en tu plan")
    # ... resto del codigo existente sin cambios ...
```

---

### Paso 8: `app/routers/superadmin.py` — Anadir endpoints de features/plan

Anadir al final del archivo (~60 lineas nuevas):

```python
from app.core.features import (
    FEATURE_REGISTRY,
    get_tenant_features,
    invalidate_feature_cache,
)
from app.schemas.admin import FeatureInfo, TenantFeaturesResponse


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
        tenant.plan_expires_at = body["plan_expires_at"]
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

    # Validar que las keys existen
    invalid_keys = [k for k in body if k not in FEATURE_REGISTRY]
    if invalid_keys:
        raise HTTPException(status_code=400, detail=f"Features desconocidas: {invalid_keys}")

    tenant.feature_overrides = body
    await db.commit()
    await invalidate_feature_cache(tenant_id)
    logger.info("tenant_features_updated", tenant_id=str(tenant_id), overrides=body)
    return {"ok": True, "feature_overrides": body}
```

---

### Paso 9: `app/services/agent.py` — Feature checks

Anadir import al inicio:
```python
from app.core.features import get_tenant_features
```

Anadir constante:
```python
FEATURE_NOT_AVAILABLE_MSG = (
    "Esta funcionalidad no esta disponible en tu plan actual. "
    "Contacta con nosotros para mas informacion."
)
```

En `handle_message`, justo despues de cargar el tenant (linea ~154, despues de `_t = await db.get(Tenant, tenant_id)`), anadir:

```python
# Feature check
features = await get_tenant_features(tenant_id, db)
```

Luego, antes de cada bloque de intent que requiere feature, anadir check:

```python
if intent == "agendar_cita":
    if not features.get("calendar.schedule", False):
        await send_text(tenant_id, wa_phone, FEATURE_NOT_AVAILABLE_MSG, db)
        return
    # ... codigo existente de agendar_cita ...
elif intent in ("cancelar_cita", "modificar_cita"):
    feature_key = "calendar.cancel" if intent == "cancelar_cita" else "calendar.modify"
    if not features.get(feature_key, False):
        await send_text(tenant_id, wa_phone, FEATURE_NOT_AVAILABLE_MSG, db)
        return
    # ... codigo existente ...
```

Y en la seccion de ejecutar action, antes de `elif action_type == "derivar":`:
```python
elif action_type == "derivar":
    if not features.get("email.derivation", False):
        reply_text = FEATURE_NOT_AVAILABLE_MSG
    else:
        await send_notification_email(...)
        action_executed = "derivar"
```

---

### Paso 10: `app/main.py` — Incluir router

Anadir despues de los imports de routers existentes:
```python
from app.routers.admin_features import router as admin_features_router
```

Y despues de `app.include_router(admin_router)`:
```python
app.include_router(admin_features_router)
```

---

### Paso 11: `app/routers/superadmin.py` — Actualizar `_tenant_to_list_item`

Anadir `plan` al `TenantListItem`:
```python
def _tenant_to_list_item(tenant: Tenant) -> TenantListItem:
    return TenantListItem(
        # ... campos existentes ...
        plan=tenant.plan,
    )
```

---

### Paso 12: `seed.py` — Actualizar demo tenant

En el dict `PRIMER_TENANT`, anadir:
```python
"plan": "FREE_TRIAL",
```

Y despues de crear el tenant, setear expiry:
```python
from datetime import datetime, timedelta, timezone

# Despues de crear el tenant:
if not tenant.plan_expires_at:
    tenant.plan = "FREE_TRIAL"
    tenant.plan_expires_at = datetime.now(timezone.utc) + timedelta(days=14)
    await session.commit()
```

---

### Paso 13: `tests/test_features.py` — CREAR archivo nuevo (~150 lineas)

```python
"""Tests unitarios para el sistema de features y planes."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.features import (
    FEATURE_REGISTRY,
    PLAN_FEATURES,
    _resolve_features,
    get_tenant_features,
    has_feature,
)
from app.models.enums import TenantPlan


def _make_tenant(plan="PAID", expires=None, overrides=None):
    """Crea un mock de Tenant para tests."""
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.plan = plan
    tenant.plan_expires_at = expires
    tenant.feature_overrides = overrides or {}
    return tenant


class TestResolveFeatures:
    def test_paid_has_all_features(self):
        tenant = _make_tenant(plan="PAID")
        result = _resolve_features(tenant)
        for key in FEATURE_REGISTRY:
            assert result[key] is True, f"PAID should have {key}"

    def test_free_trial_has_basics(self):
        tenant = _make_tenant(plan="FREE_TRIAL")
        result = _resolve_features(tenant)
        assert result["calendar.schedule"] is True
        assert result["email.derivation"] is True
        assert result["admin.dashboard"] is True
        assert result["admin.conversations"] is True

    def test_free_trial_no_paid_features(self):
        tenant = _make_tenant(plan="FREE_TRIAL")
        result = _resolve_features(tenant)
        assert result["admin.metrics"] is False
        assert result["handoff.web_chat"] is False
        assert result["groups.templates"] is False

    def test_sin_plan_only_core(self):
        tenant = _make_tenant(plan="SIN_PLAN")
        result = _resolve_features(tenant)
        # Core/security/oauth/backup = always_enabled
        assert result["core.whatsapp_bot"] is True
        assert result["security.jwt_auth"] is True
        # Everything else disabled
        assert result["calendar.schedule"] is False
        assert result["admin.dashboard"] is False
        assert result["admin.metrics"] is False

    def test_override_grants_access(self):
        tenant = _make_tenant(
            plan="FREE_TRIAL",
            overrides={"handoff.web_chat": True},
        )
        result = _resolve_features(tenant)
        assert result["handoff.web_chat"] is True

    def test_override_revokes_access(self):
        tenant = _make_tenant(
            plan="PAID",
            overrides={"calendar.schedule": False},
        )
        result = _resolve_features(tenant)
        assert result["calendar.schedule"] is False

    def test_expired_free_trial_degrades(self):
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        tenant = _make_tenant(plan="FREE_TRIAL", expires=expired)
        result = _resolve_features(tenant)
        # Degrades to SIN_PLAN: only always_enabled
        assert result["core.whatsapp_bot"] is True
        assert result["calendar.schedule"] is False
        assert result["admin.dashboard"] is False

    def test_expired_trial_with_override_still_works(self):
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        tenant = _make_tenant(
            plan="FREE_TRIAL",
            expires=expired,
            overrides={"calendar.schedule": True},
        )
        result = _resolve_features(tenant)
        assert result["calendar.schedule"] is True  # override wins


class TestRegistryConsistency:
    def test_plan_features_keys_exist(self):
        """Todas las keys en PLAN_FEATURES existen en FEATURE_REGISTRY."""
        for plan, keys in PLAN_FEATURES.items():
            for key in keys:
                assert key in FEATURE_REGISTRY, f"{key} in {plan} not in registry"

    def test_dependencies_exist(self):
        """Todas las dependencias referenciadas existen en FEATURE_REGISTRY."""
        for key, feat in FEATURE_REGISTRY.items():
            for dep in feat.dependencies:
                assert dep in FEATURE_REGISTRY, f"{key} depends on {dep} which doesn't exist"

    def test_resolve_returns_all_keys(self):
        """_resolve_features devuelve exactamente las mismas keys que FEATURE_REGISTRY."""
        tenant = _make_tenant(plan="PAID")
        result = _resolve_features(tenant)
        assert set(result.keys()) == set(FEATURE_REGISTRY.keys())
```

---

### Paso 14: `CLAUDE.md` — Anadir regla

En la seccion "REGLAS INQUEBRANTABLES", despues de la regla 9, anadir:

```
10. **Registro de features** — Toda feature nueva debe registrarse en `app/core/features.py` (FEATURE_REGISTRY) y en `FEATURES.md`. Feature key = dotted notation (`modulo.subfeature`). Asignacion de plan obligatoria.
```

Y en la seccion "ESTRUCTURA", anadir `app/core/features.py` despues de `app/core/ (config, database, redis, security)`:
```
├── app/
│   ├── core/    (config, database, redis, security, features)
```

Y anadir `admin_features.py` en routers:
```
│   └── routers/
│       ├── admin_features.py       ← endpoints features (separado de admin.py)
```

---

## Verificacion Final

Despues de implementar todo, ejecutar:

```bash
conda run -n botllm pytest tests/test_features.py -v
```

Los 10 tests deben pasar. Si algun test falla, arreglalo antes de continuar.

---

## Archivos Criticos a Leer ANTES de editar

- `FEATURES.md` — inventario completo de features (ya creado)
- `CLAUDE.md` — reglas del proyecto
- `app/models/tenant.py` — modelo actual del tenant
- `app/models/enums.py` — enums existentes
- `app/schemas/admin.py` — schemas Pydantic existentes
- `app/routers/admin.py` — router admin (369 lineas, NO superar 400)
- `app/routers/superadmin.py` — router superadmin (203 lineas)
- `app/services/agent.py` — orquestador (306 lineas, NO superar 400)
- `app/main.py` — punto de entrada, incluir nuevo router
- `app/core/redis.py` — funciones Redis existentes (get_redis, acquire_lock)
- `seed.py` — script de seed
- `alembic/versions/` — verificar ultima migracion para down_revision

## Recordatorios

- **Max 300 lineas por archivo .py** (400 absoluto). Si un archivo se acerca, refactorizar.
- **Lee CADA archivo antes de editarlo**. No asumas contenido.
- **No toques admin.html ni admin.js** en este paso — la UI se hara en una tarea separada.
- **Commit** con mensaje: `feat: implement feature flags system with plans and per-tenant overrides`
- **Push** a la rama `claude/plan-features-tracking-Se2IK`
