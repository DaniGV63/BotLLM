"""Tests unitarios para group_class_service."""

import json
import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

MADRID_TZ = ZoneInfo("Europe/Madrid")


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_definition(dias_semana=None, max_capacidad=8, hora="10:00", activa=True):
    d = MagicMock()
    d.id = uuid.uuid4()
    d.tenant_id = uuid.uuid4()
    d.nombre = "Pilates"
    d.dias_semana = json.dumps(dias_semana or [0, 2, 4])
    d.hora = hora
    d.duracion_min = 60
    d.max_capacidad = max_capacidad
    d.activa = activa
    return d


def _make_session(fecha=None, hora="10:00", estado="PROGRAMADA", definition=None):
    s = MagicMock()
    s.id = uuid.uuid4()
    s.definition_id = definition.id if definition else uuid.uuid4()
    s.tenant_id = uuid.uuid4()
    s.fecha = fecha or (date.today() + timedelta(days=2))
    s.hora = hora
    s.estado = estado
    return s


def _make_db(scalar_return=None, scalars_return=None, first_return=None):
    db = AsyncMock()
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none.return_value = scalar_return
    scalar_result.scalar_one.return_value = scalar_return
    scalar_result.scalar.return_value = 0
    scalar_result.scalars.return_value.all.return_value = scalars_return or []
    scalar_result.first.return_value = first_return
    db.execute.return_value = scalar_result
    return db


# ---------------------------------------------------------------------------
# create_definition
# ---------------------------------------------------------------------------

class TestCreateDefinition:
    @pytest.mark.asyncio
    async def test_creates_and_flushes(self):
        from app.services.group_class_service import create_definition

        db = AsyncMock()
        tenant_id = uuid.uuid4()
        result = await create_definition(tenant_id, "Yoga", [1, 3], "09:00", 45, 6, db)

        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert result.nombre == "Yoga"
        assert result.hora == "09:00"
        assert result.max_capacidad == 6

    @pytest.mark.asyncio
    async def test_dias_semana_serialized_as_json(self):
        from app.services.group_class_service import create_definition

        db = AsyncMock()
        result = await create_definition(uuid.uuid4(), "X", [0, 4], "10:00", 60, 8, db)
        assert json.loads(result.dias_semana) == [0, 4]


# ---------------------------------------------------------------------------
# generate_upcoming_sessions
# ---------------------------------------------------------------------------

class TestGenerateUpcomingSessions:
    @pytest.mark.asyncio
    async def test_generates_for_matching_days(self):
        from app.services.group_class_service import generate_upcoming_sessions

        definition = _make_definition(dias_semana=list(range(7)))  # todos los días
        db = _make_db(scalar_return=definition)
        db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=definition)
        ))

        with patch("app.services.group_class_service.pg_insert") as mock_insert:
            stmt_mock = MagicMock()
            stmt_mock.values.return_value.on_conflict_do_nothing.return_value = stmt_mock
            mock_insert.return_value = stmt_mock
            db.execute = AsyncMock()

            # Parcheamos la consulta inicial para devolver la definición
            async def mock_execute(stmt):
                result = MagicMock()
                result.scalar_one_or_none.return_value = definition
                return result

            db.execute = mock_execute

            # Con 7 días y todos los días activos, debería generar 7 sesiones
            # Solo verificamos que no lanza excepciones
            await generate_upcoming_sessions(definition.tenant_id, definition.id, 7, db)

    @pytest.mark.asyncio
    async def test_does_nothing_if_definition_not_found(self):
        from app.services.group_class_service import generate_upcoming_sessions

        db = AsyncMock()

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        db.execute = mock_execute
        # No debe lanzar excepción
        await generate_upcoming_sessions(uuid.uuid4(), uuid.uuid4(), 7, db)


# ---------------------------------------------------------------------------
# inscribe_patient
# ---------------------------------------------------------------------------

class TestInscribePatient:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        from app.services.group_class_service import inscribe_patient

        definition = _make_definition(max_capacidad=8)
        session = _make_session(definition=definition)

        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:  # session query
                result.scalar_one_or_none.return_value = session
            elif call_count == 2:  # definition query
                result.scalar_one.return_value = definition
            elif call_count == 3:  # count inscritos
                result.scalar.return_value = 3
            elif call_count == 4:  # existing inscription
                result.scalar_one_or_none.return_value = None
            return result

        db = AsyncMock()
        db.execute = mock_execute

        result = await inscribe_patient(session.tenant_id, session.id, "34600000001", "Ana", db)

        assert result["ok"] is True
        assert result["plazas_libres"] == 4
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_capacity_returns_error(self):
        from app.services.group_class_service import inscribe_patient

        definition = _make_definition(max_capacidad=8)
        session = _make_session(definition=definition)
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
                result.scalar.return_value = 8  # llena
            return result

        db = AsyncMock()
        db.execute = mock_execute

        result = await inscribe_patient(session.tenant_id, session.id, "34600000001", "Ana", db)
        assert result["ok"] is False
        assert result["reason"] == "full"

    @pytest.mark.asyncio
    async def test_duplicate_inscription_returns_error(self):
        from app.services.group_class_service import inscribe_patient

        definition = _make_definition(max_capacidad=8)
        session = _make_session(definition=definition)
        existing_inscription = MagicMock()
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
                result.scalar.return_value = 2
            elif call_count == 4:
                result.scalar_one_or_none.return_value = existing_inscription
            return result

        db = AsyncMock()
        db.execute = mock_execute

        result = await inscribe_patient(session.tenant_id, session.id, "34600000001", "Ana", db)
        assert result["ok"] is False
        assert result["reason"] == "already_inscribed"

    @pytest.mark.asyncio
    async def test_session_not_found(self):
        from app.services.group_class_service import inscribe_patient

        async def mock_execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        db = AsyncMock()
        db.execute = mock_execute

        result = await inscribe_patient(uuid.uuid4(), uuid.uuid4(), "34600000001", None, db)
        assert result["ok"] is False
        assert result["reason"] == "session_not_found"


# ---------------------------------------------------------------------------
# cancel_inscription
# ---------------------------------------------------------------------------

class TestCancelInscription:
    @pytest.mark.asyncio
    async def test_cancels_and_liberates_plaza(self):
        from app.services.group_class_service import cancel_inscription

        session = _make_session(fecha=date.today() + timedelta(days=3))
        inscription = MagicMock()
        inscription.nombre_paciente = "Ana"

        async def mock_execute(stmt):
            result = MagicMock()
            result.first.return_value = (inscription, session)
            return result

        db = AsyncMock()
        db.execute = mock_execute

        with patch("app.services.group_class_service.send_cancellation_alert_email", new_callable=AsyncMock) as mock_alert:
            result = await cancel_inscription(session.tenant_id, session.id, "34600000001", db)

        assert result is True
        db.delete.assert_called_once_with(inscription)
        mock_alert.assert_not_called()  # >24h: no alerta

    @pytest.mark.asyncio
    async def test_cancellation_within_24h_triggers_alert(self):
        from app.services.group_class_service import cancel_inscription

        session = _make_session(fecha=date.today(), hora="23:59")  # hoy casi a medianoche
        inscription = MagicMock()
        inscription.nombre_paciente = "Pedro"

        async def mock_execute(stmt):
            result = MagicMock()
            result.first.return_value = (inscription, session)
            return result

        db = AsyncMock()
        db.execute = mock_execute

        with patch("app.services.group_class_service.send_cancellation_alert_email", new_callable=AsyncMock) as mock_alert:
            with patch("app.services.group_class_service.datetime") as mock_dt:
                from datetime import datetime
                mock_dt.now.return_value = datetime(
                    date.today().year, date.today().month, date.today().day,
                    10, 0, 0, tzinfo=MADRID_TZ
                )
                mock_dt.combine = datetime.combine
                await cancel_inscription(session.tenant_id, session.id, "34600000001", db)

        mock_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_inscription_not_found_returns_false(self):
        from app.services.group_class_service import cancel_inscription

        async def mock_execute(stmt):
            result = MagicMock()
            result.first.return_value = None
            return result

        db = AsyncMock()
        db.execute = mock_execute

        result = await cancel_inscription(uuid.uuid4(), uuid.uuid4(), "34600000001", db)
        assert result is False


# ---------------------------------------------------------------------------
# get_group_slots_for_bot
# ---------------------------------------------------------------------------

class TestGetGroupSlotsForBot:
    @pytest.mark.asyncio
    async def test_filters_full_sessions(self):
        from app.services.group_class_service import get_group_slots_for_bot

        with patch("app.services.group_class_service.get_available_sessions", new_callable=AsyncMock) as mock_avail:
            mock_avail.return_value = []  # sin sesiones disponibles
            result = await get_group_slots_for_bot(uuid.uuid4(), 7, AsyncMock())
        assert result == []

    @pytest.mark.asyncio
    async def test_formats_correctly(self):
        from app.services.group_class_service import get_group_slots_for_bot

        session_id = uuid.uuid4()
        avail = [{
            "session_id": session_id,
            "definition_id": uuid.uuid4(),
            "nombre": "Yoga",
            "fecha": date(2026, 4, 10),
            "hora": "10:00",
            "plazas_libres": 3,
            "max_capacidad": 8,
        }]

        with patch("app.services.group_class_service.get_available_sessions", new_callable=AsyncMock) as mock_avail:
            mock_avail.return_value = avail
            result = await get_group_slots_for_bot(uuid.uuid4(), 7, AsyncMock())

        assert len(result) == 1
        assert result[0]["date"] == "2026-04-10"
        assert len(result[0]["slots"]) == 1
        slot = result[0]["slots"][0]
        assert slot["session_id"] == str(session_id)
        assert "Yoga grupal" in slot["label"]
        assert "3 plazas" in slot["label"]
