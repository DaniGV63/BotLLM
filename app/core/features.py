"""Sistema de feature flags y planes para Attendoo."""

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
    plans: tuple[TenantPlan, ...]
    status: FeatureStatus
    difficulty: FeatureDifficulty
    priority: FeaturePriority
    stability: FeatureStability
    conversion_impact: ConversionImpact
    dependencies: tuple[str, ...] = ()
    version: str = ""
    always_enabled: bool = False


FEATURE_REGISTRY: dict[str, FeatureDefinition] = {
    # --- Core (always_enabled) ---
    "core.whatsapp_bot": FeatureDefinition(
        key="core.whatsapp_bot",
        name="Motor principal del bot",
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
    "core.intent_detection": FeatureDefinition(
        key="core.intent_detection",
        name="Deteccion de intenciones",
        description="Deteccion de intenciones (LLM call 1)",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.L,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.ALTO,
        always_enabled=True,
        version="v1.0",
    ),
    "core.response_generation": FeatureDefinition(
        key="core.response_generation",
        name="Generacion de respuestas",
        description="Generacion de respuestas (LLM call 2)",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.L,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.ALTO,
        always_enabled=True,
        version="v1.0",
    ),
    "core.conversation_lifecycle": FeatureDefinition(
        key="core.conversation_lifecycle",
        name="Ciclo vida conversacion",
        description="Ciclo vida ACTIVA/INACTIVA",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.MEDIO,
        always_enabled=True,
        version="v1.2",
    ),
    "core.rgpd_consent": FeatureDefinition(
        key="core.rgpd_consent",
        name="Consentimiento RGPD",
        description="Consentimiento RGPD primer mensaje",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.S,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.BAJO,
        always_enabled=True,
        version="v1.0",
    ),

    # --- Calendar (free+paid) ---
    "calendar.free_slots": FeatureDefinition(
        key="calendar.free_slots",
        name="Consultar disponibilidad",
        description="Consultar slots libres en Google Calendar",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.ALTO,
        dependencies=("oauth.google_calendar",),
        version="v1.0",
    ),
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
    "calendar.cancel": FeatureDefinition(
        key="calendar.cancel",
        name="Cancelar citas",
        description="Cancelar citas en Google Calendar",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.MEDIO,
        dependencies=("calendar.schedule",),
        version="v1.0",
    ),
    "calendar.modify": FeatureDefinition(
        key="calendar.modify",
        name="Modificar citas",
        description="Modificar citas en Google Calendar",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.MEDIO,
        dependencies=("calendar.schedule",),
        version="v1.0",
    ),

    # --- Email (free+paid) ---
    "email.derivation": FeatureDefinition(
        key="email.derivation",
        name="Derivacion a fisio por email",
        description="Derivacion a fisioterapeuta por email via Gmail",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.MEDIO,
        dependencies=("oauth.google_gmail",),
        version="v1.0",
    ),

    # --- Admin (diferenciado por plan) ---
    "admin.dashboard": FeatureDefinition(
        key="admin.dashboard",
        name="Panel principal",
        description="Panel de administracion principal",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.L,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.MEDIO,
        version="v1.1",
    ),
    "admin.conversations": FeatureDefinition(
        key="admin.conversations",
        name="Visor de mensajes",
        description="Visor de conversaciones y mensajes del tenant",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.MEDIO,
        version="v1.1",
    ),
    "admin.tenant_config": FeatureDefinition(
        key="admin.tenant_config",
        name="Configuracion tenant",
        description="Configuracion del tenant en el panel admin",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.MEDIO,
        version="v1.1",
    ),
    "admin.metrics": FeatureDefinition(
        key="admin.metrics",
        name="Analiticas de datos",
        description="Dashboard de metricas del tenant",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.ALTO,
        version="v1.1",
    ),

    "admin.work_blocks": FeatureDefinition(
        key="admin.work_blocks",
        name="Configuracion horario",
        description="Configuracion de horarios de atencion del negocio desde panel admin",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.BETA,
        conversion_impact=ConversionImpact.MEDIO,
        version="v1.6",
    ),
    "admin.calendar_view": FeatureDefinition(
        key="admin.calendar_view",
        name="Vista calendario admin",
        description="Vista de calendario integrada en panel admin con FullCalendar",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.L,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.BETA,
        conversion_impact=ConversionImpact.ALTO,
        version="v1.6",
    ),

    # --- Security (always_enabled) ---
    "security.hmac_validation": FeatureDefinition(
        key="security.hmac_validation",
        name="Validacion HMAC webhook",
        description="Validacion HMAC de webhook de Meta",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.S,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.BAJO,
        always_enabled=True,
        version="v1.0",
    ),
    "security.rate_limiting": FeatureDefinition(
        key="security.rate_limiting",
        name="Rate limiting por tenant",
        description="Control de tasa de mensajes por tenant",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.S,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.BAJO,
        always_enabled=True,
        version="v1.0",
    ),
    "security.jwt_auth": FeatureDefinition(
        key="security.jwt_auth",
        name="Autenticacion JWT admin",
        description="Autenticacion JWT para el panel de administracion",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.BAJO,
        always_enabled=True,
        version="v1.1",
    ),
    "security.encryption": FeatureDefinition(
        key="security.encryption",
        name="Encriptacion tokens",
        description="Encriptacion de tokens con Fernet",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.S,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.BAJO,
        always_enabled=True,
        version="v1.0",
    ),

    # --- OAuth (always_enabled) ---
    "oauth.google_calendar": FeatureDefinition(
        key="oauth.google_calendar",
        name="OAuth2 Google Calendar",
        description="Flujo OAuth2 para Google Calendar por tenant",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.ALTO,
        always_enabled=True,
        version="v1.2",
    ),
    "oauth.google_gmail": FeatureDefinition(
        key="oauth.google_gmail",
        name="OAuth2 Gmail",
        description="Flujo OAuth2 para Gmail por tenant",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.MEDIO,
        always_enabled=True,
        version="v1.2",
    ),

    # --- Backup (always_enabled) ---
    "backup.auto_backup": FeatureDefinition(
        key="backup.auto_backup",
        name="Backup automatico al startup",
        description="Backup automatico de datos al arrancar la aplicacion",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.BAJO,
        always_enabled=True,
        version="v1.2",
    ),
    "backup.restore": FeatureDefinition(
        key="backup.restore",
        name="Restore desde JSON",
        description="Restauracion de datos desde archivo JSON",
        plans=(TenantPlan.FREE_TRIAL, TenantPlan.PAID),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.ESTABLE,
        conversion_impact=ConversionImpact.BAJO,
        always_enabled=True,
        version="v1.2",
    ),

    # --- Handoff v1.3.0 (paid) ---
    "handoff.web_chat": FeatureDefinition(
        key="handoff.web_chat",
        name="Chat web fisio",
        description="Chat web para fisioterapeuta via WebSocket",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.L,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.BETA,
        conversion_impact=ConversionImpact.ALTO,
        dependencies=("email.derivation",),
        version="v1.3",
    ),
    "handoff.wa_bridge": FeatureDefinition(
        key="handoff.wa_bridge",
        name="Puente WhatsApp fisio",
        description="Puente WhatsApp para notificaciones al fisioterapeuta",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.L,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.BETA,
        conversion_impact=ConversionImpact.ALTO,
        dependencies=("email.derivation",),
        version="v1.3",
    ),
    "handoff.cancellation_alert": FeatureDefinition(
        key="handoff.cancellation_alert",
        name="Alerta cancelacion <24h",
        description="Alerta cuando se cancela una cita con menos de 24h de antelacion",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.BETA,
        conversion_impact=ConversionImpact.MEDIO,
        dependencies=("calendar.cancel",),
        version="v1.3",
    ),

    # --- Clases Grupales v1.5.0 (paid) ---
    "groups.templates": FeatureDefinition(
        key="groups.templates",
        name="Plantillas clases recurrentes",
        description="Plantillas para clases grupales recurrentes",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.L,
        priority=FeaturePriority.MEDIA,
        stability=FeatureStability.BETA,
        conversion_impact=ConversionImpact.ALTO,
        dependencies=("calendar.schedule",),
        version="v1.5",
    ),
    "groups.sessions": FeatureDefinition(
        key="groups.sessions",
        name="Sesiones con capacidad",
        description="Sesiones grupales con control de capacidad",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.MEDIA,
        stability=FeatureStability.BETA,
        conversion_impact=ConversionImpact.ALTO,
        dependencies=("groups.templates",),
        version="v1.5",
    ),
    "groups.inscriptions": FeatureDefinition(
        key="groups.inscriptions",
        name="Inscripciones pacientes",
        description="Gestion de inscripciones de pacientes a clases grupales",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.IMPLEMENTED,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.MEDIA,
        stability=FeatureStability.BETA,
        conversion_impact=ConversionImpact.MEDIO,
        dependencies=("groups.sessions",),
        version="v1.5",
    ),

    # --- Futuro (paid) ---
    "reminders.appointment_24h": FeatureDefinition(
        key="reminders.appointment_24h",
        name="Recordatorio 24h antes",
        description="Recordatorio automatico 24h antes de la cita",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.PENDING,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.ALTA,
        stability=FeatureStability.EXPERIMENTAL,
        conversion_impact=ConversionImpact.ALTO,
        dependencies=("calendar.schedule",),
    ),
    "i18n.multi_language": FeatureDefinition(
        key="i18n.multi_language",
        name="Soporte multi-idioma",
        description="Soporte para multiples idiomas en el bot",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.PENDING,
        difficulty=FeatureDifficulty.L,
        priority=FeaturePriority.BAJA,
        stability=FeatureStability.EXPERIMENTAL,
        conversion_impact=ConversionImpact.MEDIO,
    ),
    "payments.gateway": FeatureDefinition(
        key="payments.gateway",
        name="Pasarela de pago",
        description="Pasarela de pago (Stripe/Redsys)",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.PENDING,
        difficulty=FeatureDifficulty.XL,
        priority=FeaturePriority.MEDIA,
        stability=FeatureStability.EXPERIMENTAL,
        conversion_impact=ConversionImpact.ALTO,
    ),
    "waitlist.management": FeatureDefinition(
        key="waitlist.management",
        name="Lista de espera",
        description="Gestion de lista de espera para citas",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.PENDING,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.BAJA,
        stability=FeatureStability.EXPERIMENTAL,
        conversion_impact=ConversionImpact.MEDIO,
        dependencies=("calendar.schedule",),
    ),
    "history.appointments": FeatureDefinition(
        key="history.appointments",
        name="Historial citas en BD",
        description="Historial de citas persistido en base de datos",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.PENDING,
        difficulty=FeatureDifficulty.M,
        priority=FeaturePriority.MEDIA,
        stability=FeatureStability.EXPERIMENTAL,
        conversion_impact=ConversionImpact.BAJO,
        dependencies=("calendar.schedule",),
    ),
    "analytics.llm_costs": FeatureDefinition(
        key="analytics.llm_costs",
        name="Analiticas coste LLM",
        description="Analiticas de coste de llamadas al LLM",
        plans=(TenantPlan.PAID,),
        status=FeatureStatus.PENDING,
        difficulty=FeatureDifficulty.S,
        priority=FeaturePriority.BAJA,
        stability=FeatureStability.EXPERIMENTAL,
        conversion_impact=ConversionImpact.BAJO,
        dependencies=("admin.metrics",),
    ),
}

# Derivado automaticamente del registry
PLAN_FEATURES: dict[TenantPlan, frozenset[str]] = {
    plan: frozenset(
        f.key for f in FEATURE_REGISTRY.values()
        if plan in f.plans or f.always_enabled
    )
    for plan in TenantPlan
}

FREE_TRIAL_DURATION_DAYS = 14


def _resolve_features(tenant) -> dict[str, bool]:
    """Construye mapa completo de features para un tenant."""
    plan = TenantPlan(tenant.plan) if tenant.plan else TenantPlan.SIN_PLAN

    # FREE_TRIAL expirado → degrada a SIN_PLAN
    if plan == TenantPlan.FREE_TRIAL and tenant.plan_expires_at:
        if datetime.now(timezone.utc) > tenant.plan_expires_at:
            plan = TenantPlan.SIN_PLAN

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


from fastapi import HTTPException  # noqa: E402


def require_feature(feature_key: str):
    """FastAPI dependency: requiere que el tenant tenga acceso a una feature."""
    async def _check(tenant=None, db=None):
        if tenant and not await has_feature(tenant.id, feature_key, db):
            raise HTTPException(
                status_code=403,
                detail=f"Feature '{feature_key}' no disponible en tu plan",
            )
        return tenant
    return _check
