import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    nombre_negocio: Mapped[str] = mapped_column(String(200), nullable=False)
    email_notificaciones: Mapped[str] = mapped_column(String(200), nullable=False)

    # WhatsApp
    whatsapp_phone_number_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    whatsapp_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_verify_token: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    meta_app_secret: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Google Calendar / Gmail
    google_calendar_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    google_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Estado
    bot_activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # Admin (Fase 5)
    admin_username: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )
    admin_password_hash: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
