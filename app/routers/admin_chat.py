"""Router de chat handoff: WebSocket + REST para fisio y paciente."""

import uuid
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, get_db
from app.core.features import has_feature
from app.core.security import decode_access_token
from app.models.conversation import Conversation
from app.models.enums import ConversationState
from app.models.message import Message
from app.models.tenant import Tenant
from app.routers.admin import TokenData, get_current_user, require_tenant_scope
from app.services.conversation import append_therapist_message
from app.services.derivation_service import end_derivation
from app.services.websocket_manager import manager

router = APIRouter(prefix="/admin/chat", tags=["admin-chat"])
logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TherapistMessageRequest(BaseModel):
    conversation_id: UUID
    content: str


class EndDerivationRequest(BaseModel):
    conversation_id: UUID


class DerivationInfo(BaseModel):
    conversation_id: UUID
    patient_name: str | None
    wa_phone: str
    ultimo_mensaje_at: str | None


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    """WebSocket autenticado por JWT como query param (WS no soporta headers)."""
    try:
        payload = decode_access_token(token)
        tenant_id_str = payload.get("tenant_id")
        if not tenant_id_str:
            await websocket.close(code=4001)
            return
        tenant_id = str(UUID(tenant_id_str))
    except (JWTError, ValueError):
        await websocket.close(code=4001)
        return

    await manager.connect(tenant_id, websocket)
    log = logger.bind(tenant_id=tenant_id)
    log.info("ws_session_start")

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "therapist_send":
                await _handle_therapist_send(tenant_id, data, websocket)
            elif msg_type == "end_derivation":
                await _handle_end_derivation(tenant_id, data, websocket)
            else:
                log.warning("ws_unknown_message_type", msg_type=msg_type)

    except WebSocketDisconnect:
        log.info("ws_session_end")
    except Exception:
        log.error("ws_error", exc_info=True)
    finally:
        manager.disconnect(tenant_id, websocket)


async def _handle_therapist_send(tenant_id: str, data: dict, websocket: WebSocket) -> None:
    """Procesa mensaje de fisio enviado via WS → guarda en PG y reenvía al paciente."""
    conv_id_str = data.get("conversation_id")
    content = data.get("content", "").strip()
    if not conv_id_str or not content:
        return

    conv_id = UUID(conv_id_str)
    t_uuid = UUID(tenant_id)

    async with SessionLocal() as db:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conv_id,
                Conversation.tenant_id == t_uuid,
                Conversation.estado == ConversationState.DERIVADA.value,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            await manager.send_to_connection(websocket, {"type": "error", "detail": "Conversacion no encontrada o no derivada"})
            return

        if not await has_feature(t_uuid, "handoff.web_chat", db):
            await manager.send_to_connection(websocket, {"type": "error", "detail": "Feature no disponible"})
            return

        await append_therapist_message(
            tenant_id=t_uuid,
            wa_phone=conversation.wa_phone,
            content=content,
            sender_name="fisio",
            db=db,
            conversation_id=conv_id,
        )

        # Enviar al paciente por WhatsApp
        from app.services.whatsapp_service import send_text
        await send_text(t_uuid, conversation.wa_phone, content, db)

        await db.commit()
        logger.info("therapist_message_sent", tenant_id=tenant_id, conv_id=conv_id_str)


async def _handle_end_derivation(tenant_id: str, data: dict, websocket: WebSocket) -> None:
    """Finaliza derivacion desde WS."""
    conv_id_str = data.get("conversation_id")
    if not conv_id_str:
        return

    conv_id = UUID(conv_id_str)
    t_uuid = UUID(tenant_id)

    async with SessionLocal() as db:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conv_id,
                Conversation.tenant_id == t_uuid,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            return

        tenant = await db.get(Tenant, t_uuid)
        if not tenant:
            return

        await end_derivation(conversation, tenant, "manual", db)
        await db.commit()

        await manager.broadcast_to_tenant(
            tenant_id,
            {"type": "derivation_ended", "conversation_id": conv_id_str, "reason": "manual"},
        )
        logger.info("derivation_ended_via_ws", tenant_id=tenant_id, conv_id=conv_id_str)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@router.post("/send")
async def therapist_send_rest(
    body: TherapistMessageRequest,
    tenant: Tenant = Depends(require_tenant_scope),
    user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Envia mensaje de fisio via REST (fallback si WS no disponible)."""
    if not await has_feature(tenant.id, "handoff.web_chat", db):
        raise HTTPException(status_code=403, detail="Feature handoff.web_chat no disponible")

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.tenant_id == tenant.id,
            Conversation.estado == ConversationState.DERIVADA.value,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversacion no encontrada o no derivada")

    await append_therapist_message(
        tenant_id=tenant.id,
        wa_phone=conversation.wa_phone,
        content=body.content,
        sender_name=str(user.user_id),
        db=db,
        conversation_id=body.conversation_id,
    )

    from app.services.whatsapp_service import send_text
    await send_text(tenant.id, conversation.wa_phone, body.content, db)
    await db.commit()

    return {"status": "sent"}


@router.post("/end")
async def end_derivation_rest(
    body: EndDerivationRequest,
    tenant: Tenant = Depends(require_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Finaliza una derivacion activa via REST."""
    if not await has_feature(tenant.id, "handoff.web_chat", db):
        raise HTTPException(status_code=403, detail="Feature handoff.web_chat no disponible")

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.tenant_id == tenant.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversacion no encontrada")

    await end_derivation(conversation, tenant, "manual", db)
    await db.commit()

    await manager.broadcast_to_tenant(
        str(tenant.id),
        {"type": "derivation_ended", "conversation_id": str(body.conversation_id), "reason": "manual"},
    )
    return {"status": "ended"}


@router.get("/active", response_model=list[DerivationInfo])
async def list_active_derivations(
    tenant: Tenant = Depends(require_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> list[DerivationInfo]:
    """Lista conversaciones en estado DERIVADA para este tenant."""
    if not await has_feature(tenant.id, "handoff.web_chat", db):
        raise HTTPException(status_code=403, detail="Feature handoff.web_chat no disponible")

    result = await db.execute(
        select(Conversation).where(
            Conversation.tenant_id == tenant.id,
            Conversation.estado == ConversationState.DERIVADA.value,
        )
    )
    conversations = result.scalars().all()

    return [
        DerivationInfo(
            conversation_id=c.id,
            patient_name=c.nombre_paciente,
            wa_phone=c.wa_phone,
            ultimo_mensaje_at=c.ultimo_mensaje_at.isoformat() if c.ultimo_mensaje_at else None,
        )
        for c in conversations
    ]


@router.get("/messages/{conversation_id}")
async def get_derivation_messages(
    conversation_id: UUID,
    tenant: Tenant = Depends(require_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Devuelve mensajes de una conversacion derivada (para mostrar en chat UI)."""
    if not await has_feature(tenant.id, "handoff.web_chat", db):
        raise HTTPException(status_code=403, detail="Feature handoff.web_chat no disponible")

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == tenant.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversacion no encontrada")

    msgs_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(50)
    )
    messages = msgs_result.scalars().all()

    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "sender_name": m.sender_name,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]
