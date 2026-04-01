"""Tests unitarios para wa_bridge_service.py (v1.3.0)."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import ConversationState
from app.services.wa_bridge_service import handle_therapist_message, is_therapist_phone
from tests.conftest import make_db_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _populate_mapping(fake_redis, tenant_id, prefix, conv_id, wa_phone, name="Paciente"):
    key = f"bridge:{tenant_id}:mappings"
    await fake_redis.hset(key, prefix, json.dumps({
        "phone": wa_phone,
        "conv_id": str(conv_id),
        "name": name,
    }))


def _make_conv_result(conversation):
    """Resultado de db.execute que devuelve una conversación."""
    r = MagicMock()
    r.scalars.return_value.all.return_value = []
    r.scalar_one_or_none.return_value = conversation
    return r


# ---------------------------------------------------------------------------
# is_therapist_phone
# ---------------------------------------------------------------------------


class TestIsTherapistPhone:
    async def test_phone_del_tenant_es_fisio(self, tenant_factory, db_mock, fake_redis):
        tenant = tenant_factory(wa_personal_phone="34600000001")
        db_mock.execute = AsyncMock(return_value=make_db_result(rows=[]))

        assert await is_therapist_phone("34600000001", tenant, db_mock) is True

    async def test_phone_desconocido_no_es_fisio(self, tenant_factory, db_mock, fake_redis):
        tenant = tenant_factory(wa_personal_phone="34600000001")
        db_mock.execute = AsyncMock(return_value=make_db_result(rows=[]))

        assert await is_therapist_phone("34699999999", tenant, db_mock) is False

    async def test_phone_admin_user_es_fisio(self, tenant_factory, db_mock, fake_redis):
        tenant = tenant_factory(wa_personal_phone=None)
        # Simula AdminUser con wa_personal_phone
        result = MagicMock()
        result.scalars.return_value.all.return_value = ["34677777777"]
        db_mock.execute = AsyncMock(return_value=result)

        assert await is_therapist_phone("34677777777", tenant, db_mock) is True

    async def test_cache_hit_no_consulta_db(self, tenant_factory, db_mock, fake_redis):
        tenant = tenant_factory(wa_personal_phone="34600000001")
        # Pre-popularizar cache
        cache_key = f"bridge:{tenant.id}:fisio_phones"
        await fake_redis.set(cache_key, json.dumps(["34600000001"]))

        result = await is_therapist_phone("34600000001", tenant, db_mock)

        assert result is True
        db_mock.execute.assert_not_called()

    async def test_cache_miss_consulta_y_cachea(self, tenant_factory, db_mock, fake_redis):
        tenant = tenant_factory(wa_personal_phone="34600000001")
        db_mock.execute = AsyncMock(return_value=make_db_result(rows=[]))

        # Primera llamada: cache miss → consulta BD
        await is_therapist_phone("34600000001", tenant, db_mock)
        assert db_mock.execute.call_count == 1

        # Segunda llamada: cache hit → no consulta BD
        db_mock.execute.reset_mock()
        await is_therapist_phone("34600000001", tenant, db_mock)
        db_mock.execute.assert_not_called()


# ---------------------------------------------------------------------------
# handle_therapist_message — routing
# ---------------------------------------------------------------------------


class TestHandleTherapistMessageRouting:
    async def test_sin_derivaciones_retorna_none(self, tenant_factory, db_mock):
        tenant = tenant_factory()
        # Redis vacío → no hay mappings → silencio
        result = await handle_therapist_message("34600000001", "Hola", tenant, db_mock)
        assert result is None

    async def test_prefijo_valido_envia_al_paciente(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv = conversation_factory(estado=ConversationState.DERIVADA.value)
        conv.tenant_id = tenant.id
        await _populate_mapping(fake_redis, tenant.id, "1.", conv.id, conv.wa_phone)

        # db.execute: primero para validar DERIVADA, luego para cargar conv en _forward
        db_mock.execute = AsyncMock(return_value=_make_conv_result(conv))

        with patch("app.services.conversation.append_therapist_message", AsyncMock()), \
             patch("app.services.whatsapp_service.send_text", AsyncMock()) as mock_send:
            result = await handle_therapist_message(
                "34600000001", "1. Hola paciente", tenant, db_mock
            )

        assert result is None  # Sin respuesta al fisio si todo OK
        mock_send.assert_called_once()

    async def test_sin_prefijo_una_derivacion_envia(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv = conversation_factory(estado=ConversationState.DERIVADA.value)
        conv.tenant_id = tenant.id
        await _populate_mapping(fake_redis, tenant.id, "1.", conv.id, conv.wa_phone)

        db_mock.execute = AsyncMock(return_value=_make_conv_result(conv))

        with patch("app.services.conversation.append_therapist_message", AsyncMock()), \
             patch("app.services.whatsapp_service.send_text", AsyncMock()) as mock_send:
            result = await handle_therapist_message(
                "34600000001", "Hola sin prefijo", tenant, db_mock
            )

        assert result is None
        mock_send.assert_called_once()

    async def test_sin_prefijo_multiples_derivaciones_pide_numero(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv1 = conversation_factory(estado=ConversationState.DERIVADA.value, wa_phone="34611111111")
        conv2 = conversation_factory(estado=ConversationState.DERIVADA.value, wa_phone="34622222222")
        conv1.tenant_id = tenant.id
        conv2.tenant_id = tenant.id

        await _populate_mapping(fake_redis, tenant.id, "1.", conv1.id, conv1.wa_phone, "Ana")
        await _populate_mapping(fake_redis, tenant.id, "2.", conv2.id, conv2.wa_phone, "Juan")

        # Ambas son DERIVADAS
        db_mock.execute = AsyncMock(return_value=_make_conv_result(
            MagicMock(estado=ConversationState.DERIVADA.value)
        ))

        result = await handle_therapist_message(
            "34600000001", "Hola sin prefijo", tenant, db_mock
        )

        assert result is not None
        assert "2" in result  # Menciona número de derivaciones
        assert "1." in result or "2." in result

    async def test_prefijo_invalido_retorna_error(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv = conversation_factory(estado=ConversationState.DERIVADA.value)
        conv.tenant_id = tenant.id
        await _populate_mapping(fake_redis, tenant.id, "1.", conv.id, conv.wa_phone)

        db_mock.execute = AsyncMock(return_value=_make_conv_result(conv))

        result = await handle_therapist_message(
            "34600000001", "9. Hola", tenant, db_mock
        )

        assert result is not None
        assert "9." in result

    async def test_comando_bot_cierra_derivaciones(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv = conversation_factory(estado=ConversationState.DERIVADA.value)
        conv.tenant_id = tenant.id
        await _populate_mapping(fake_redis, tenant.id, "1.", conv.id, conv.wa_phone)

        db_mock.execute = AsyncMock(return_value=_make_conv_result(conv))

        with patch("app.services.derivation_service.end_derivation", AsyncMock()) as mock_end:
            result = await handle_therapist_message("34600000001", "/bot", tenant, db_mock)

        assert result is not None
        assert "cerrad" in result.lower() or "1" in result
        mock_end.assert_called_once()

    async def test_comando_bot_sin_derivaciones(self, tenant_factory, db_mock):
        tenant = tenant_factory()
        # Redis vacío

        result = await handle_therapist_message("34600000001", "/bot", tenant, db_mock)

        assert result is not None
        assert "no hab" in result.lower() or "activa" in result.lower()


# ---------------------------------------------------------------------------
# handle_therapist_message — contenido del mensaje
# ---------------------------------------------------------------------------


class TestHandleTherapistMessageContent:
    async def test_contenido_mensaje_llega_al_paciente(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv = conversation_factory(estado=ConversationState.DERIVADA.value)
        conv.tenant_id = tenant.id
        await _populate_mapping(fake_redis, tenant.id, "1.", conv.id, conv.wa_phone)
        db_mock.execute = AsyncMock(return_value=_make_conv_result(conv))

        sent_messages = []

        async def capture_send(tenant_id, wa_phone, content, db):
            sent_messages.append(content)

        with patch("app.services.conversation.append_therapist_message", AsyncMock()), \
             patch("app.services.whatsapp_service.send_text", capture_send):
            await handle_therapist_message(
                "34600000001", "1. Recuerda traer informe", tenant, db_mock
            )

        assert sent_messages == ["Recuerda traer informe"]

    async def test_contenido_sin_prefijo_llega_completo(
        self, tenant_factory, conversation_factory, db_mock, fake_redis
    ):
        tenant = tenant_factory()
        conv = conversation_factory(estado=ConversationState.DERIVADA.value)
        conv.tenant_id = tenant.id
        await _populate_mapping(fake_redis, tenant.id, "1.", conv.id, conv.wa_phone)
        db_mock.execute = AsyncMock(return_value=_make_conv_result(conv))

        sent_messages = []

        async def capture_send(tenant_id, wa_phone, content, db):
            sent_messages.append(content)

        with patch("app.services.conversation.append_therapist_message", AsyncMock()), \
             patch("app.services.whatsapp_service.send_text", capture_send):
            await handle_therapist_message(
                "34600000001", "Mañana a las 10", tenant, db_mock
            )

        assert sent_messages == ["Mañana a las 10"]
