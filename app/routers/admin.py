"""Router del panel admin: login JWT + tenant endpoints + impersonación."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import check_rate_limit
from app.core.security import (
    create_access_token,
    decode_access_token,
    encrypt,
    verify_password,
)
from app.models.admin_user import AdminRole, AdminUser
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.tenant import Tenant
from app.schemas.admin import (
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationSummary,
    LoginRequest,
    LoginResponse,
    MessageRead,
    MetricsResponse,
    TenantRead,
    TenantUpdate,
)
from app.core.features import has_feature
from app.services.email_service import send_bot_status_email
from app.services.wa_bridge_service import invalidate_fisio_cache

router = APIRouter(prefix="/admin", tags=["admin"])
logger = structlog.get_logger()

# Campos editables solo por super admin
_SUPER_ONLY_FIELDS = {
    "whatsapp_token",
    "google_calendar_id",
    "google_access_token",
    "google_refresh_token",
    "google_token_expiry",
    "plan",
    "plan_expires_at",
    "feature_overrides",
    "wa_personal_phone",
    "derivation_timeout_minutes",
}


# --- Token data ---


@dataclass
class TokenData:
    user_id: UUID
    role: str
    tenant_id: UUID | None


# --- Dependencias de autenticación ---


async def get_current_user(
    authorization: str = Header(...),
) -> TokenData:
    """Decodifica el JWT y retorna los datos del usuario."""
    try:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Token inválido")

        payload = decode_access_token(token)
        user_id = payload.get("sub")
        role = payload.get("role")
        tenant_id_str = payload.get("tenant_id")

        if not user_id or not role:
            raise HTTPException(status_code=401, detail="Token inválido")

        return TokenData(
            user_id=UUID(user_id),
            role=role,
            tenant_id=UUID(tenant_id_str) if tenant_id_str else None,
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    except ValueError:
        raise HTTPException(status_code=401, detail="Token inválido")


async def require_super_admin(
    user: TokenData = Depends(get_current_user),
) -> TokenData:
    """Solo permite acceso a super admins."""
    if user.role != AdminRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Acceso denegado: se requiere super admin")
    return user


async def require_tenant_scope(
    user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Resuelve el tenant activo desde el token. Válido para tenant_admin y super_admin impersonando."""
    if not user.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Sin tenant activo. Selecciona un tenant desde el panel de Super Admin.",
        )
    result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")
    return tenant


# --- Helpers ---


def _tenant_to_read(tenant: Tenant) -> TenantRead:
    return TenantRead(
        id=tenant.id,
        slug=tenant.slug,
        nombre_negocio=tenant.nombre_negocio,
        email_notificaciones=tenant.email_notificaciones,
        bot_activo=tenant.bot_activo,
        rate_limit_per_minute=tenant.rate_limit_per_minute,
        max_citas_activas=tenant.max_citas_activas,
        google_calendar_id=tenant.google_calendar_id,
        google_token_expiry=tenant.google_token_expiry,
        has_google_credentials=bool(tenant.google_access_token and tenant.google_refresh_token),
        created_at=tenant.created_at,
        plan=tenant.plan,
        plan_expires_at=tenant.plan_expires_at,
        feature_overrides=tenant.feature_overrides or {},
        wa_personal_phone=tenant.wa_personal_phone,
        derivation_timeout_minutes=tenant.derivation_timeout_minutes or 60,
        derivation_timeout_no_reply_minutes=tenant.derivation_timeout_no_reply_minutes or 480,
        derivation_timeout_after_reply_minutes=tenant.derivation_timeout_after_reply_minutes or 120,
        work_blocks=tenant.work_blocks or {},
        slot_duration_minutes=tenant.slot_duration_minutes or 60,
    )


# --- Endpoints ---


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Autentica admin o super admin y devuelve JWT con role + tenant_id."""
    rate_key = f"login:{body.username}"
    if await check_rate_limit(rate_key, limit=10, window=300):
        raise HTTPException(status_code=429, detail="Demasiados intentos. Inténtalo en 5 minutos.")
    result = await db.execute(
        select(AdminUser).where(AdminUser.username == body.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        logger.warning("admin_login_failed", username=body.username)
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "tenant_id": str(user.tenant_id) if user.tenant_id else None,
    })
    logger.info("admin_login_success", user_id=str(user.id), role=user.role)
    return LoginResponse(
        access_token=token,
        role=user.role,
        tenant_id=user.tenant_id,
    )


@router.post("/impersonate/{tenant_id}", response_model=LoginResponse)
async def impersonate_tenant(
    tenant_id: UUID,
    user: TokenData = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Super admin obtiene token scoped a un tenant para gestionarlo directamente."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant no encontrado")

    token = create_access_token({
        "sub": str(user.user_id),
        "role": AdminRole.SUPER_ADMIN,
        "tenant_id": str(tenant_id),
    })
    logger.info("super_admin_impersonating", user_id=str(user.user_id), tenant_id=str(tenant_id))
    return LoginResponse(
        access_token=token,
        role=AdminRole.SUPER_ADMIN,
        tenant_id=tenant_id,
    )


@router.get("/tenant", response_model=TenantRead)
async def get_tenant(
    tenant: Tenant = Depends(require_tenant_scope),
) -> TenantRead:
    """Devuelve datos del tenant activo."""
    return _tenant_to_read(tenant)


@router.put("/tenant", response_model=TenantRead)
async def update_tenant(
    body: TenantUpdate,
    tenant: Tenant = Depends(require_tenant_scope),
    user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantRead:
    """Actualiza campos del tenant. Tenant admin solo puede editar campos básicos."""
    updates = body.model_dump(exclude_unset=True)

    if user.role != AdminRole.SUPER_ADMIN:
        updates = {k: v for k, v in updates.items() if k not in _SUPER_ONLY_FIELDS}

    encrypted_fields = {"whatsapp_token", "google_access_token", "google_refresh_token"}
    old_bot_activo = tenant.bot_activo

    for field, value in updates.items():
        if field in encrypted_fields:
            if not value:
                continue
            value = encrypt(value)
        setattr(tenant, field, value)

    await db.commit()
    await db.refresh(tenant)
    logger.info("tenant_updated", tenant_id=str(tenant.id), fields=list(updates.keys()))

    if "bot_activo" in updates and tenant.bot_activo != old_bot_activo:
        try:
            await send_bot_status_email(tenant.id, tenant.bot_activo)
        except Exception:
            logger.warning("bot_status_email_failed", tenant_id=str(tenant.id))

    if "wa_personal_phone" in updates:
        try:
            await invalidate_fisio_cache(tenant.id)
        except Exception:
            logger.warning("fisio_cache_invalidation_failed", tenant_id=str(tenant.id))

    return _tenant_to_read(tenant)


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    estado: str | None = Query(None),
    tenant: Tenant = Depends(require_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """Lista conversaciones recientes del tenant con paginación y filtro por estado."""
    base_filter = select(Conversation).where(Conversation.tenant_id == tenant.id)
    if estado:
        base_filter = base_filter.where(Conversation.estado == estado)

    count_result = await db.execute(
        select(func.count()).select_from(base_filter.subquery())
    )
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        base_filter.order_by(Conversation.ultimo_mensaje_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    conversations = result.scalars().all()

    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                id=c.id,
                wa_phone=c.wa_phone,
                nombre_paciente=c.nombre_paciente,
                estado=c.estado,
                ultimo_mensaje_at=c.ultimo_mensaje_at,
                created_at=c.created_at,
            )
            for c in conversations
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationDetailResponse,
)
async def get_conversation_messages(
    conversation_id: UUID,
    tenant: Tenant = Depends(require_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """Devuelve mensajes de una conversación del tenant."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = messages_result.scalars().all()

    return ConversationDetailResponse(
        conversation=ConversationSummary(
            id=conversation.id,
            wa_phone=conversation.wa_phone,
            nombre_paciente=conversation.nombre_paciente,
            estado=conversation.estado,
            ultimo_mensaje_at=conversation.ultimo_mensaje_at,
            created_at=conversation.created_at,
        ),
        messages=[
            MessageRead(
                id=m.id,
                role=m.role,
                content=m.content,
                intent=m.intent,
                action_executed=m.action_executed,
                processing_ms=m.processing_ms,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    tenant: Tenant = Depends(require_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> MetricsResponse:
    """Métricas de actividad del tenant."""
    if not await has_feature(tenant.id, "admin.metrics", db):
        raise HTTPException(status_code=403, detail="Analiticas no disponibles en tu plan")
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago, month_start = today - timedelta(days=7), today.replace(day=1)
    tid = tenant.id

    async def _cnt(*where):
        r = await db.execute(select(func.count(Message.id)).where(*where))
        return r.scalar() or 0

    msgs_hoy = await _cnt(Message.tenant_id == tid, Message.role == "user", Message.created_at >= today)
    msgs_sem = await _cnt(Message.tenant_id == tid, Message.role == "user", Message.created_at >= week_ago)
    citas = await _cnt(Message.tenant_id == tid, Message.action_executed == "create", Message.created_at >= month_start)
    canceladas = await _cnt(Message.tenant_id == tid, Message.action_executed == "cancel", Message.created_at >= month_start)
    derivadas = await _cnt(Message.tenant_id == tid, Message.action_executed == "derivar", Message.created_at >= month_start)

    avg_r = await db.execute(
        select(func.avg(Message.processing_ms)).where(
            Message.tenant_id == tid,
            Message.processing_ms.isnot(None),
            Message.created_at >= week_ago,
        )
    )
    act_r = await db.execute(
        select(func.count()).select_from(Conversation).where(
            Conversation.tenant_id == tid, Conversation.estado == "ACTIVA"
        )
    )
    avg_val = avg_r.scalar()
    return MetricsResponse(
        mensajes_hoy=msgs_hoy,
        mensajes_semana=msgs_sem,
        citas_agendadas_mes=citas,
        citas_canceladas_mes=canceladas,
        derivaciones_mes=derivadas,
        avg_processing_ms=int(avg_val) if avg_val is not None else None,
        conversaciones_activas=act_r.scalar() or 0,
    )
