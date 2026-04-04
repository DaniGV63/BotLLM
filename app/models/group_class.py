"""Modelos para clases grupales recurrentes."""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SessionState(str, enum.Enum):
    PROGRAMADA = "PROGRAMADA"
    CANCELADA = "CANCELADA"


class GroupClassDefinition(Base):
    """Plantilla de clase recurrente (ej: Pilates L/X/V a las 10:00)."""

    __tablename__ = "group_class_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    dias_semana: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # JSON array: "[0,2,4]" para L/X/V
    hora: Mapped[str] = mapped_column(String(5), nullable=False)  # "10:00"
    duracion_min: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    max_capacidad: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class GroupClassSession(Base):
    """Instancia concreta de una clase en una fecha específica."""

    __tablename__ = "group_class_sessions"
    __table_args__ = (UniqueConstraint("definition_id", "fecha", name="uq_session_definition_fecha"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("group_class_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    hora: Mapped[str] = mapped_column(String(5), nullable=False)
    estado: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SessionState.PROGRAMADA.value
    )
    google_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GroupClassInscription(Base):
    """Inscripción de un paciente a una sesión grupal."""

    __tablename__ = "group_class_inscriptions"
    __table_args__ = (
        UniqueConstraint("session_id", "wa_phone", name="uq_inscription_session_phone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("group_class_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    wa_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre_paciente: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
