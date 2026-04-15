"""Tests unitarios para derivation_service.py (v1.3.0)."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import ConversationState
from app.services.derivation_service import (
    check_derivation_timeout,
    derivate_conversation,
    end_derivation,
)
from tests.conftest import make_db_result

_PATCHED_CREDS = "app.services.derivation_service.get_google_creds"
_PATCHED_WS = "app.services.websocket_manager.manager"


# ---------------------------------------------------------------------------
# derivate_conversation
# ---------------------------------------------------------------------------


class TestDerivateConversation:
    async def test_cambia_estado_a_derivada(self, tenant_factory, conversation_factory, db_mock):
        tenant = tenant_factory()
        conv = conversation_factory()

        with patch(_PATCHED_CREDS, side_effect=ValueError("sin creds")), \
             patch(_PATCHED_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            await derivate_conversation(conv, tenant, "dolor espalda", [], db_mock)

        assert conv.estado == ConversationState.DERIVADA.value
        db_mock.flush.assert_called()

    async def test_asigna_numero_redis_incremental(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv1 = conversation_factory(wa_phone="34611111111")
        conv2 = conversation_factory(wa_phone="34622222222")
        conv1.tenant_id = tenant.id
        conv2.tenant_id = tenant.id

        with patch(_PATCHED_CREDS, side_effect=ValueError), \
             patch(_PATCHED_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            n1 = await derivate_conversation(conv1, tenant, "motivo", [], db_mock)
            n2 = await derivate_conversation(conv2, tenant, "motivo2", [], db_mock)

        assert n1 == 1
        assert n2 == 2

    async def test_guarda_mapping_en_redis(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv = conversation_factory()
        conv.tenant_id = tenant.id

        with patch(_PATCHED_CREDS, side_effect=ValueError), \
             patch(_PATCHED_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            await derivate_conversation(conv, tenant, "motivo", [], db_mock)

        mappings_key = f"bridge:{tenant.id}:mappings"
        raw = await fake_redis.hget(mappings_key, "1.")
        assert raw is not None
        entry = json.loads(raw)
        assert entry["phone"] == conv.wa_phone
        assert entry["conv_id"] == str(conv.id)

    async def test_llama_broadcast_ws(self, tenant_factory, conversation_factory, db_mock):
        tenant = tenant_factory()
        conv = conversation_factory()

        with patch(_PATCHED_CREDS, side_effect=ValueError), \
             patch(_PATCHED_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            await derivate_conversation(conv, tenant, "motivo", [], db_mock)

        mock_ws.broadcast_to_tenant.assert_called_once()
        call_args = mock_ws.broadcast_to_tenant.call_args
        payload = call_args[0][1]
        assert payload["type"] == "derivation_new"
        assert payload["phone"] == conv.wa_phone

    async def test_error_email_no_propaga(self, tenant_factory, conversation_factory, db_mock):
        """Un fallo de credenciales Google no debe romper la derivación."""
        tenant = tenant_factory()
        conv = conversation_factory()

        with patch(_PATCHED_CREDS, side_effect=ValueError("sin OAuth")), \
             patch(_PATCHED_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            # No debe lanzar excepción
            numero = await derivate_conversation(conv, tenant, "motivo", [], db_mock)

        assert numero == 1

    async def test_incluye_historial_en_summary(
        self, tenant_factory, conversation_factory, db_mock
    ):
        """El WS broadcast incluye resumen de últimos mensajes."""
        tenant = tenant_factory()
        conv = conversation_factory()
        history = [
            {"role": "user", "content": "Tengo dolor de rodilla"},
            {"role": "assistant", "content": "Te paso con el fisio"},
        ]

        with patch(_PATCHED_CREDS, side_effect=ValueError), \
             patch(_PATCHED_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            await derivate_conversation(conv, tenant, "dolor rodilla", history, db_mock)

        payload = mock_ws.broadcast_to_tenant.call_args[0][1]
        assert "dolor de rodilla" in payload["summary"]


# ---------------------------------------------------------------------------
# end_derivation
# ---------------------------------------------------------------------------


class TestEndDerivation:
    async def _setup_mapping(self, fake_redis, tenant_id, conv_id, wa_phone):
        key = f"bridge:{tenant_id}:mappings"
        await fake_redis.hset(key, "1.", json.dumps({
            "phone": wa_phone,
            "conv_id": str(conv_id),
            "name": "Test",
        }))
        return key

    async def test_restaura_estado_activa(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv = conversation_factory(estado=ConversationState.DERIVADA.value)
        await self._setup_mapping(fake_redis, tenant.id, conv.id, conv.wa_phone)

        with patch(_PATCHED_CREDS, side_effect=ValueError):
            await end_derivation(conv, tenant, "manual", db_mock)

        assert conv.estado == ConversationState.ACTIVA.value

    async def test_limpia_mapping_redis(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv = conversation_factory()
        key = await self._setup_mapping(fake_redis, tenant.id, conv.id, conv.wa_phone)

        with patch(_PATCHED_CREDS, side_effect=ValueError):
            await end_derivation(conv, tenant, "manual", db_mock)

        remaining = await fake_redis.hgetall(key)
        assert "1." not in remaining

    async def test_timeout_envia_email(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv = conversation_factory()
        await self._setup_mapping(fake_redis, tenant.id, conv.id, conv.wa_phone)

        with patch("app.services.derivation_service._send_timeout_email", AsyncMock()) as mock_email:
            await end_derivation(conv, tenant, "timeout", db_mock)

        mock_email.assert_called_once_with(tenant, conv)

    async def test_manual_no_envia_email(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv = conversation_factory()
        await self._setup_mapping(fake_redis, tenant.id, conv.id, conv.wa_phone)

        with patch("app.services.derivation_service._send_timeout_email", AsyncMock()) as mock_email:
            await end_derivation(conv, tenant, "manual", db_mock)

        mock_email.assert_not_called()

    async def test_sin_mapping_no_falla(
        self, tenant_factory, conversation_factory, db_mock
    ):
        """Si no hay mapping en Redis, no debe lanzar excepción."""
        tenant = tenant_factory()
        conv = conversation_factory()

        with patch(_PATCHED_CREDS, side_effect=ValueError):
            await end_derivation(conv, tenant, "manual", db_mock)

        assert conv.estado == ConversationState.ACTIVA.value


# ---------------------------------------------------------------------------
# check_derivation_timeout
# ---------------------------------------------------------------------------


class TestCheckDerivationTimeout:
    async def test_sin_derivadas_no_hace_nada(self, db_mock):
        # db.execute devuelve lista vacía para DERIVADAS
        db_mock.execute = AsyncMock(return_value=make_db_result(rows=[]))

        with patch("app.services.derivation_service.end_derivation", AsyncMock()) as mock_end:
            await check_derivation_timeout(uuid.uuid4(), db_mock)

        mock_end.assert_not_called()

    async def test_derivacion_expirada_se_cierra(
        self, tenant_factory, conversation_factory, db_mock
    ):
        tenant = tenant_factory(timeout_minutes=60)
        # no_reply_timeout a 60 min para que 90 min expire
        tenant.derivation_timeout_no_reply_minutes = 60
        # Conversación derivada hace 90 minutos sin respuesta del fisio
        conv = conversation_factory(estado=ConversationState.DERIVADA.value)
        conv.tenant_id = tenant.id
        conv.derivation_started_at = datetime.now(timezone.utc) - timedelta(minutes=90)
        conv.ultimo_mensaje_at = datetime.now(timezone.utc) - timedelta(minutes=90)

        conv_result = make_db_result(rows=[conv])
        tenant_result = make_db_result(scalar=tenant)
        msg_result = make_db_result(scalar=None)  # sin respuesta del fisio
        db_mock.execute = AsyncMock(side_effect=[conv_result, tenant_result, msg_result])
        db_mock.get = AsyncMock(return_value=tenant)

        with patch("app.services.derivation_service.end_derivation", AsyncMock()) as mock_end:
            await check_derivation_timeout(tenant.id, db_mock)

        mock_end.assert_called_once()
        call_conv = mock_end.call_args[0][0]
        assert call_conv.id == conv.id

    async def test_derivacion_reciente_no_se_cierra(
        self, tenant_factory, conversation_factory, db_mock
    ):
        tenant = tenant_factory(timeout_minutes=60)
        tenant.derivation_timeout_no_reply_minutes = 60
        conv = conversation_factory(estado=ConversationState.DERIVADA.value)
        conv.tenant_id = tenant.id
        conv.derivation_started_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        conv.ultimo_mensaje_at = datetime.now(timezone.utc) - timedelta(minutes=10)

        conv_result = make_db_result(rows=[conv])
        tenant_result = make_db_result(scalar=tenant)
        msg_result = make_db_result(scalar=None)  # sin respuesta del fisio
        db_mock.execute = AsyncMock(side_effect=[conv_result, tenant_result, msg_result])

        with patch("app.services.derivation_service.end_derivation", AsyncMock()) as mock_end:
            await check_derivation_timeout(tenant.id, db_mock)

        mock_end.assert_not_called()
