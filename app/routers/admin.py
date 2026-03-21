"""Router del panel admin: login JWT + CRUD tenant + conversaciones."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    decrypt,
    encrypt,
    verify_password,
    decode_access_token,
)
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
    TenantRead,
    TenantUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])
logger = structlog.get_logger()


# --- Dependencia de autenticación ---


async def get_current_tenant(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Extrae tenant del JWT en el header Authorization."""
    try:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Token inválido")

        payload = decode_access_token(token)
        tenant_id = payload.get("sub")
        if not tenant_id:
            raise HTTPException(status_code=401, detail="Token inválido")

        result = await db.execute(
            select(Tenant).where(Tenant.id == UUID(tenant_id))
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=401, detail="Tenant no encontrado")

        return tenant
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    except ValueError:
        raise HTTPException(status_code=401, detail="Token inválido")


def _tenant_to_read(tenant: Tenant) -> TenantRead:
    """Convierte modelo Tenant a schema TenantRead (sin datos sensibles)."""
    return TenantRead(
        id=tenant.id,
        slug=tenant.slug,
        nombre_negocio=tenant.nombre_negocio,
        email_notificaciones=tenant.email_notificaciones,
        bot_activo=tenant.bot_activo,
        google_calendar_id=tenant.google_calendar_id,
        google_token_expiry=tenant.google_token_expiry,
        has_google_credentials=bool(
            tenant.google_access_token and tenant.google_refresh_token
        ),
        created_at=tenant.created_at,
    )


# --- Endpoints ---


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Autentica admin y devuelve JWT."""
    result = await db.execute(
        select(Tenant).where(Tenant.admin_username == body.username)
    )
    tenant = result.scalar_one_or_none()

    if not tenant or not tenant.admin_password_hash:
        logger.warning("admin_login_failed", username=body.username)
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    if not verify_password(body.password, tenant.admin_password_hash):
        logger.warning("admin_login_failed", username=body.username)
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = create_access_token({"sub": str(tenant.id)})
    logger.info("admin_login_success", tenant_id=str(tenant.id))
    return LoginResponse(access_token=token)


@router.get("/tenant", response_model=TenantRead)
async def get_tenant(
    tenant: Tenant = Depends(get_current_tenant),
) -> TenantRead:
    """Devuelve datos del tenant (sin campos sensibles)."""
    return _tenant_to_read(tenant)


@router.put("/tenant", response_model=TenantRead)
async def update_tenant(
    body: TenantUpdate,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> TenantRead:
    """Actualiza campos editables del tenant."""
    updates = body.model_dump(exclude_unset=True)
    encrypted_fields = {"google_access_token", "google_refresh_token"}

    for field, value in updates.items():
        if field in encrypted_fields:
            if not value:
                continue
            value = encrypt(value)
        setattr(tenant, field, value)

    await db.commit()
    await db.refresh(tenant)
    logger.info(
        "tenant_updated",
        tenant_id=str(tenant.id),
        fields=list(updates.keys()),
    )
    return _tenant_to_read(tenant)


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """Lista conversaciones recientes del tenant con paginación."""
    base_filter = select(Conversation).where(
        Conversation.tenant_id == tenant.id
    )

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
    tenant: Tenant = Depends(get_current_tenant),
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
