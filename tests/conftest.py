"""Fixtures compartidos para todos los tests de Atendoo v1.3.0."""

import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Mockear dependencias con extensiones nativas antes de cualquier import de app.
# Esto evita conflictos de build en entornos de test que no tienen los binarios
# de Google / cryptography compilados (el entorno conda del desarrollador sí los tiene).
for _mod in [
    "googleapiclient",
    "googleapiclient.discovery",
    "google.oauth2",
    "google.oauth2.credentials",
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "cryptography",
    "cryptography.fernet",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

import fakeredis.aioredis  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402

from app.models.enums import ConversationState  # noqa: E402


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_factory():
    """Crea mocks de Tenant con plan PAID y valores por defecto para handoff."""
    def _make(
        wa_personal_phone: str = "34600000001",
        timeout_minutes: int = 60,
        tenant_id: uuid.UUID | None = None,
    ):
        t = MagicMock()
        t.id = tenant_id or uuid.uuid4()
        t.plan = "PAID"
        t.plan_expires_at = None
        t.feature_overrides = {}
        t.wa_personal_phone = wa_personal_phone
        t.derivation_timeout_minutes = timeout_minutes
        t.email_notificaciones = "fisio@clinica.test"
        t.whatsapp_phone_number_id = "1234567890"
        t.whatsapp_token = None
        return t

    return _make


@pytest.fixture
def conversation_factory():
    """Crea mocks de Conversation con valores por defecto."""
    def _make(
        estado: str = ConversationState.ACTIVA.value,
        nombre: str = "Paciente Test",
        wa_phone: str = "34611111111",
        tenant_id: uuid.UUID | None = None,
        conv_id: uuid.UUID | None = None,
    ):
        c = MagicMock()
        c.id = conv_id or uuid.uuid4()
        c.tenant_id = tenant_id or uuid.uuid4()
        c.wa_phone = wa_phone
        c.nombre_paciente = nombre
        c.estado = estado
        c.ultimo_mensaje_at = datetime.now(timezone.utc)
        return c

    return _make


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def fake_redis():
    """Instancia FakeRedis aislada por test."""
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest_asyncio.fixture(autouse=True)
async def patch_redis(fake_redis):
    """Parchea get_redis en todos los modulos de servicio para usar FakeRedis."""
    redis_mock = AsyncMock(return_value=fake_redis)
    with (
        patch("app.core.redis.get_redis", redis_mock),
        patch("app.services.derivation_service.get_redis", redis_mock),
        patch("app.services.wa_bridge_service.get_redis", redis_mock),
        patch("app.services.conversation.get_redis", redis_mock),
    ):
        yield


# ---------------------------------------------------------------------------
# DB mock
# ---------------------------------------------------------------------------


@pytest.fixture
def db_mock():
    """AsyncMock de AsyncSession de SQLAlchemy."""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    # execute devuelve un MagicMock con scalars().all() y scalar_one_or_none()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    result.scalar.return_value = None
    db.execute = AsyncMock(return_value=result)
    db.get = AsyncMock(return_value=None)
    return db


def make_db_result(rows=None, scalar=None):
    """Helper para crear resultados de db.execute con distintos valores."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows or []
    result.scalar_one_or_none.return_value = scalar
    result.scalar.return_value = scalar
    return result
