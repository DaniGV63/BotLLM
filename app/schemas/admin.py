"""Schemas Pydantic para el panel admin."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Login ---


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Tenant ---


class TenantRead(BaseModel):
    id: UUID
    slug: str
    nombre_negocio: str
    email_notificaciones: str
    bot_activo: bool
    google_calendar_id: str | None
    google_token_expiry: datetime | None
    has_google_credentials: bool
    created_at: datetime


class TenantUpdate(BaseModel):
    nombre_negocio: str | None = None
    email_notificaciones: str | None = None
    bot_activo: bool | None = None
    whatsapp_token: str | None = None
    google_calendar_id: str | None = None
    google_access_token: str | None = None
    google_refresh_token: str | None = None
    google_token_expiry: datetime | None = None


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
