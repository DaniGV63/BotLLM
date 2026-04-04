"""Schemas Pydantic para el panel admin."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Auth ---


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: UUID | None


# --- Tenant ---


class TenantRead(BaseModel):
    id: UUID
    slug: str
    nombre_negocio: str
    email_notificaciones: str
    bot_activo: bool
    rate_limit_per_minute: int
    max_citas_activas: int
    google_calendar_id: str | None
    google_token_expiry: datetime | None
    has_google_credentials: bool
    created_at: datetime
    plan: str
    plan_expires_at: datetime | None
    feature_overrides: dict
    wa_personal_phone: str | None
    derivation_timeout_minutes: int


class TenantUpdate(BaseModel):
    nombre_negocio: str | None = None
    email_notificaciones: str | None = None
    bot_activo: bool | None = None
    rate_limit_per_minute: int | None = None
    max_citas_activas: int | None = None
    # Solo super admin puede editar estos campos
    whatsapp_token: str | None = None
    google_calendar_id: str | None = None
    google_access_token: str | None = None
    google_refresh_token: str | None = None
    google_token_expiry: datetime | None = None
    plan: str | None = None
    plan_expires_at: datetime | None = None
    feature_overrides: dict | None = None
    wa_personal_phone: str | None = None
    derivation_timeout_minutes: int | None = None


class TenantCreate(BaseModel):
    slug: str
    nombre_negocio: str
    email_notificaciones: str
    whatsapp_phone_number_id: str
    whatsapp_verify_token: str | None = None
    bot_activo: bool = True
    plan: str = "FREE_TRIAL"


class TenantListItem(BaseModel):
    id: UUID
    slug: str
    nombre_negocio: str
    email_notificaciones: str
    bot_activo: bool
    activo: bool
    created_at: datetime
    plan: str


class TenantListResponse(BaseModel):
    tenants: list[TenantListItem]
    total: int


# --- Admin Users ---


class AdminUserCreate(BaseModel):
    username: str
    password: str
    tenant_id: UUID  # requerido: solo se crean tenant_admin desde API
    email: str | None = None


class AdminUserRead(BaseModel):
    id: UUID
    tenant_id: UUID | None
    username: str
    role: str
    email: str | None
    created_at: datetime


# --- Conversaciones ---


class ConversationSummary(BaseModel):
    id: UUID
    wa_phone: str
    nombre_paciente: str | None
    estado: str
    ultimo_mensaje_at: datetime
    created_at: datetime


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]
    total: int
    page: int
    page_size: int


class MessageRead(BaseModel):
    id: UUID
    role: str
    content: str
    intent: str | None
    action_executed: str | None
    processing_ms: int | None
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    conversation: ConversationSummary
    messages: list[MessageRead]


# --- Onboarding ---


class TenantOnboardingStatus(BaseModel):
    slug: str
    nombre_negocio: str
    whatsapp_configured: bool
    google_configured: bool
    missing_steps: list[str]


# --- Métricas ---


class MetricsResponse(BaseModel):
    mensajes_hoy: int
    mensajes_semana: int
    citas_agendadas_mes: int
    citas_canceladas_mes: int
    derivaciones_mes: int
    avg_processing_ms: int | None
    conversaciones_activas: int


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


# --- Group Classes ---


class GroupClassCreate(BaseModel):
    nombre: str
    dias_semana: list[int]
    hora: str
    duracion_min: int = 60
    max_capacidad: int = 8


class GroupClassUpdate(BaseModel):
    nombre: str | None = None
    dias_semana: list[int] | None = None
    hora: str | None = None
    duracion_min: int | None = None
    max_capacidad: int | None = None
    activa: bool | None = None


class GroupClassRead(BaseModel):
    id: UUID
    nombre: str
    dias_semana: list[int]
    hora: str
    duracion_min: int
    max_capacidad: int
    activa: bool
    created_at: datetime


class GroupSessionRead(BaseModel):
    id: UUID
    definition_id: UUID
    fecha: str
    hora: str
    estado: str
    inscritos: int
    plazas_libres: int


class GroupInscriptionRead(BaseModel):
    id: UUID
    wa_phone: str
    nombre_paciente: str | None
    created_at: datetime
