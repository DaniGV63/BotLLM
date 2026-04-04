"""Tests de integración para el flujo completo de clases grupales."""

import json
import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.group_class import SessionState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_definition(dias_semana=None, max_capacidad=8, tenant_id=None):
    d = MagicMock()
    d.id = uuid.uuid4()
    d.tenant_id = tenant_id or uuid.uuid4()
    d.nombre = "Pilates"
    d.dias_semana = json.dumps(dias_semana or list(range(7)))
    d.hora = "10:00"
    d.duracion_min = 60
    d.max_capacidad = max_capacidad
    d.activa = True
    return d


def _make_session(definition, fecha=None):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.definition_id = definition.id
    s.tenant_id = definition.tenant_id
    s.fecha = fecha or (date.today() + timedelta(days=2))
    s.hora = definition.hora
    s.estado = SessionState.PROGRAMADA.value
    s.google_event_id = None
    return s


# ---------------------------------------------------------------------------
# Ciclo completo: definir → sesión → inscribir → verificar capacidad
# ---------------------------------------------------------------------------

class TestGroupClassFullCycle:
    @pytest.mark.asyncio
    async def test_inscribe_then_check_capacity(self):
        """Inscribir paciente reduce plazas disponibles."""
        from app.services.group_class_service import inscribe_patient

        definition = _make_definition(max_capacidad=2)
        session = _make_session(definition)
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:  # session with lock
                result.scalar_one_or_none.return_value = session
            elif call_count == 2:  # definition
                result.scalar_one.return_value = definition
            elif call_count == 3:  # count (0 inscritos)
                result.scalar.return_value = 0
            elif call_count == 4:  # existing inscription check
                result.scalar_one_or_none.return_value = None
            return result

        db = AsyncMock()
        db.execute = mock_execute

        result = await inscribe_patient(definition.tenant_id, session.id, "34600000001", "Ana", db)
        assert result["ok"] is True
        assert result["plazas_libres"] == 1

    @pytest.mark.asyncio
    async def test_full_class_rejects_inscription(self):
        """No se puede inscribir si aforo lleno."""
        from app.services.group_class_service import inscribe_patient

        definition = _make_definition(max_capacidad=2)
        session = _make_session(definition)
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.scalar_one_or_none.return_value = session
            elif call_count == 2:
                result.scalar_one.return_value = definition
            elif call_count == 3:
                result.scalar.return_value = 2  # llena
            return result

        db = AsyncMock()
        db.execute = mock_execute

        result = await inscribe_patient(definition.tenant_id, session.id, "34600000002", "Pedro", db)
        assert result["ok"] is False
        assert result["reason"] == "full"


# ---------------------------------------------------------------------------
# Inscribir + cancelar → plaza liberada
# ---------------------------------------------------------------------------

class TestInscriptionCancellation:
    @pytest.mark.asyncio
    async def test_cancel_releases_slot(self):
        """Cancelar inscripción devuelve True y llama db.delete."""
        from app.services.group_class_service import cancel_inscription

        definition = _make_definition(max_capacidad=8)
        session = _make_session(definition, fecha=date.today() + timedelta(days=5))
        inscription = MagicMock()
        inscription.nombre_paciente = "Ana"
        inscription.wa_phone = "34600000001"

        async def mock_execute(stmt):
            result = MagicMock()
            result.first.return_value = (inscription, session)
            return result

        db = AsyncMock()
        db.execute = mock_execute

        with patch("app.services.group_class_service.send_cancellation_alert_email", new_callable=AsyncMock):
            ok = await cancel_inscription(definition.tenant_id, session.id, "34600000001", db)

        assert ok is True
        db.delete.assert_called_once_with(inscription)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_inscription(self):
        from app.services.group_class_service import cancel_inscription

        async def mock_execute(stmt):
            result = MagicMock()
            result.first.return_value = None
            return result

        db = AsyncMock()
        db.execute = mock_execute

        ok = await cancel_inscription(uuid.uuid4(), uuid.uuid4(), "34600000001", db)
        assert ok is False


# ---------------------------------------------------------------------------
# Merge slots individual + grupal
# ---------------------------------------------------------------------------

class TestMergeSlots:
    @pytest.mark.asyncio
    async def test_group_slots_visible_to_agent(self):
        """get_group_slots_for_bot devuelve slots con session_id para el agente."""
        from app.services.group_class_service import get_group_slots_for_bot

        session_id = uuid.uuid4()
        avail = [{
            "session_id": session_id,
            "definition_id": uuid.uuid4(),
            "nombre": "Yoga",
            "fecha": date(2026, 4, 14),
            "hora": "11:00",
            "plazas_libres": 5,
            "max_capacidad": 8,
        }]

        with patch("app.services.group_class_service.get_available_sessions", new_callable=AsyncMock) as mock_avail:
            mock_avail.return_value = avail
            slots = await get_group_slots_for_bot(uuid.uuid4(), 7, AsyncMock())

        assert len(slots) == 1
        assert slots[0]["slots"][0]["session_id"] == str(session_id)
        assert slots[0]["slots"][0]["hora"] == "11:00"

    @pytest.mark.asyncio
    async def test_no_slots_when_all_full(self):
        from app.services.group_class_service import get_group_slots_for_bot

        with patch("app.services.group_class_service.get_available_sessions", new_callable=AsyncMock) as mock_avail:
            mock_avail.return_value = []
            slots = await get_group_slots_for_bot(uuid.uuid4(), 7, AsyncMock())

        assert slots == []


# ---------------------------------------------------------------------------
# Alerta cancelación <24h (grupal)
# ---------------------------------------------------------------------------

class TestCancellationAlert:
    @pytest.mark.asyncio
    async def test_no_alert_when_far_future(self):
        """Sin alerta si la sesión es en más de 24h."""
        from app.services.group_class_service import cancel_inscription

        session = _make_session(_make_definition(), fecha=date.today() + timedelta(days=10))
        inscription = MagicMock()
        inscription.nombre_paciente = "Marta"

        async def mock_execute(stmt):
            result = MagicMock()
            result.first.return_value = (inscription, session)
            return result

        db = AsyncMock()
        db.execute = mock_execute

        with patch("app.services.group_class_service.send_cancellation_alert_email", new_callable=AsyncMock) as mock_alert:
            await cancel_inscription(session.tenant_id, session.id, "34600000001", db)

        mock_alert.assert_not_called()
