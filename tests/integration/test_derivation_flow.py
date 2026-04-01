"""Tests de integración para el flujo completo de derivación handoff (v1.3.0).

Prueba el ciclo de vida: ACTIVA → DERIVADA → mensajes paciente/fisio → ACTIVA.
Usa FakeRedis real (via fixture autouse) y mocks de PG y APIs externas.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import ConversationState
from app.services.derivation_service import (
    derivate_conversation,
    end_derivation,
)
from app.services.wa_bridge_service import handle_therapist_message, is_therapist_phone
from tests.conftest import make_db_result

_PATCH_CREDS = "app.services.derivation_service.get_google_creds"
_PATCH_WS = "app.services.websocket_manager.manager"
_PATCH_SEND = "app.services.whatsapp_service.send_text"
_PATCH_APPEND = "app.services.conversation.append_therapist_message"


# ---------------------------------------------------------------------------
# Flujo completo: derivación → respuesta fisio → cierre
# ---------------------------------------------------------------------------


class TestDerivationLifecycle:
    """Ciclo completo: se deriva, fisio responde, se cierra."""

    async def test_flujo_completo_via_wa_bridge(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        """
        1. Conversación ACTIVA → se deriva (estado DERIVADA, Redis mapping)
        2. Fisio responde con prefijo → mensaje llega al paciente
        3. Se cierra derivación → estado ACTIVA, mapping limpiado
        """
        tenant = tenant_factory(wa_personal_phone="34600000001")
        conv = conversation_factory(
            estado=ConversationState.ACTIVA.value,
            wa_phone="34611111111",
        )
        conv.tenant_id = tenant.id

        # PASO 1: derivar
        with patch(_PATCH_CREDS, side_effect=ValueError), \
             patch(_PATCH_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            numero = await derivate_conversation(
                conv, tenant, "paciente pide hablar con fisio", [], db_mock
            )

        assert conv.estado == ConversationState.DERIVADA.value
        assert numero == 1

        # Verificar mapping en Redis
        key = f"bridge:{tenant.id}:mappings"
        raw = await fake_redis.hget(key, "1.")
        assert raw is not None
        mapping = json.loads(raw)
        assert mapping["phone"] == conv.wa_phone

        # PASO 2: fisio responde
        db_mock.execute = AsyncMock(
            return_value=make_db_result(scalar=conv)
        )
        sent = []

        async def capture_send(tid, phone, content, db):
            sent.append({"phone": phone, "content": content})

        with patch(_PATCH_APPEND, AsyncMock()), patch(_PATCH_SEND, capture_send):
            result = await handle_therapist_message(
                "34600000001", "1. Buenas tardes, ¿en qué puedo ayudarte?", tenant, db_mock
            )

        assert result is None  # Sin respuesta de vuelta al fisio
        assert len(sent) == 1
        assert sent[0]["phone"] == conv.wa_phone
        assert sent[0]["content"] == "Buenas tardes, ¿en qué puedo ayudarte?"

        # PASO 3: cerrar derivación
        with patch(_PATCH_CREDS, side_effect=ValueError):
            await end_derivation(conv, tenant, "manual", db_mock)

        assert conv.estado == ConversationState.ACTIVA.value
        remaining = await fake_redis.hgetall(key)
        assert "1." not in remaining

    async def test_flujo_completo_sin_prefijo(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        """Sin prefijo con una sola derivación activa: el mensaje se entrega igual."""
        tenant = tenant_factory(wa_personal_phone="34600000001")
        conv = conversation_factory(estado=ConversationState.DERIVADA.value)
        conv.tenant_id = tenant.id

        with patch(_PATCH_CREDS, side_effect=ValueError), \
             patch(_PATCH_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            await derivate_conversation(conv, tenant, "motivo", [], db_mock)

        db_mock.execute = AsyncMock(return_value=make_db_result(scalar=conv))
        sent = []

        async def capture(tid, phone, content, db):
            sent.append(content)

        with patch(_PATCH_APPEND, AsyncMock()), patch(_PATCH_SEND, capture):
            await handle_therapist_message(
                "34600000001", "Mañana a las 10 tienes cita", tenant, db_mock
            )

        assert sent == ["Mañana a las 10 tienes cita"]

    async def test_flujo_timeout(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        """Timeout: derivación se cierra y se envía email."""
        tenant = tenant_factory(wa_personal_phone="34600000001", timeout_minutes=60)
        conv = conversation_factory(estado=ConversationState.ACTIVA.value)
        conv.tenant_id = tenant.id

        with patch(_PATCH_CREDS, side_effect=ValueError), \
             patch(_PATCH_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            await derivate_conversation(conv, tenant, "motivo", [], db_mock)

        # Cerrar por timeout
        with patch("app.services.derivation_service._send_timeout_email", AsyncMock()) as mock_email:
            await end_derivation(conv, tenant, "timeout", db_mock)

        assert conv.estado == ConversationState.ACTIVA.value
        mock_email.assert_called_once_with(tenant, conv)


# ---------------------------------------------------------------------------
# Detección fisio integrada con derivación
# ---------------------------------------------------------------------------


class TestFisioDetection:
    async def test_fisio_detectado_por_tenant_phone(self, tenant_factory, db_mock, fake_redis):
        tenant = tenant_factory(wa_personal_phone="34600000001")
        db_mock.execute = AsyncMock(return_value=make_db_result(rows=[]))

        assert await is_therapist_phone("34600000001", tenant, db_mock) is True
        assert await is_therapist_phone("34611111111", tenant, db_mock) is False

    async def test_fisio_no_detectado_sin_wa_personal(self, tenant_factory, db_mock, fake_redis):
        tenant = tenant_factory(wa_personal_phone=None)
        db_mock.execute = AsyncMock(return_value=make_db_result(rows=[]))

        assert await is_therapist_phone("34600000001", tenant, db_mock) is False

    async def test_cache_independiente_por_tenant(
        self, tenant_factory, db_mock, fake_redis
    ):
        """Dos tenants distintos tienen caches de fisio independientes."""
        tenant_a = tenant_factory(wa_personal_phone="34600000001")
        tenant_b = tenant_factory(wa_personal_phone="34600000002")
        db_mock.execute = AsyncMock(return_value=make_db_result(rows=[]))

        assert await is_therapist_phone("34600000001", tenant_a, db_mock) is True
        assert await is_therapist_phone("34600000001", tenant_b, db_mock) is False


# ---------------------------------------------------------------------------
# Redis state consistency
# ---------------------------------------------------------------------------


class TestRedisStateConsistency:
    async def test_multiples_derivaciones_counters_independientes_por_tenant(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        """Cada tenant tiene su propio contador de derivaciones."""
        tenant_a = tenant_factory()
        tenant_b = tenant_factory()
        conv_a = conversation_factory()
        conv_b = conversation_factory()
        conv_a.tenant_id = tenant_a.id
        conv_b.tenant_id = tenant_b.id

        with patch(_PATCH_CREDS, side_effect=ValueError), \
             patch(_PATCH_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            n_a = await derivate_conversation(conv_a, tenant_a, "motivo", [], db_mock)
            n_b = await derivate_conversation(conv_b, tenant_b, "motivo", [], db_mock)

        assert n_a == 1
        assert n_b == 1  # Cada tenant empieza en 1

    async def test_segunda_derivacion_mismo_tenant_incrementa(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv1 = conversation_factory(wa_phone="34611111111")
        conv2 = conversation_factory(wa_phone="34622222222")
        conv1.tenant_id = tenant.id
        conv2.tenant_id = tenant.id

        with patch(_PATCH_CREDS, side_effect=ValueError), \
             patch(_PATCH_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            n1 = await derivate_conversation(conv1, tenant, "m1", [], db_mock)
            n2 = await derivate_conversation(conv2, tenant, "m2", [], db_mock)

        assert n1 == 1
        assert n2 == 2

        key = f"bridge:{tenant.id}:mappings"
        assert await fake_redis.hget(key, "1.") is not None
        assert await fake_redis.hget(key, "2.") is not None

    async def test_end_derivation_solo_borra_su_mapping(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        """Al cerrar una derivación no se borra el mapping de las otras."""
        tenant = tenant_factory()
        conv1 = conversation_factory(wa_phone="34611111111")
        conv2 = conversation_factory(wa_phone="34622222222")
        conv1.tenant_id = tenant.id
        conv2.tenant_id = tenant.id

        with patch(_PATCH_CREDS, side_effect=ValueError), \
             patch(_PATCH_WS) as mock_ws:
            mock_ws.broadcast_to_tenant = AsyncMock()
            await derivate_conversation(conv1, tenant, "m1", [], db_mock)
            await derivate_conversation(conv2, tenant, "m2", [], db_mock)

        with patch(_PATCH_CREDS, side_effect=ValueError):
            await end_derivation(conv1, tenant, "manual", db_mock)

        key = f"bridge:{tenant.id}:mappings"
        remaining = await fake_redis.hgetall(key)
        assert "1." not in remaining
        assert "2." in remaining
