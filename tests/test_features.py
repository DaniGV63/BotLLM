"""Tests unitarios para el sistema de features y planes."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.features import (
    FEATURE_REGISTRY,
    PLAN_FEATURES,
    _resolve_features,
    get_tenant_features,
    has_feature,
)
from app.models.enums import TenantPlan


def _make_tenant(plan="PAID", expires=None, overrides=None):
    """Crea un mock de Tenant para tests."""
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.plan = plan
    tenant.plan_expires_at = expires
    tenant.feature_overrides = overrides or {}
    return tenant


class TestResolveFeatures:
    def test_paid_has_all_features(self):
        tenant = _make_tenant(plan="PAID")
        result = _resolve_features(tenant)
        for key in FEATURE_REGISTRY:
            assert result[key] is True, f"PAID should have {key}"

    def test_free_trial_has_basics(self):
        tenant = _make_tenant(plan="FREE_TRIAL")
        result = _resolve_features(tenant)
        assert result["calendar.schedule"] is True
        assert result["email.derivation"] is True
        assert result["admin.dashboard"] is True
        assert result["admin.conversations"] is True

    def test_free_trial_no_paid_features(self):
        tenant = _make_tenant(plan="FREE_TRIAL")
        result = _resolve_features(tenant)
        assert result["admin.metrics"] is False
        assert result["handoff.web_chat"] is False
        assert result["groups.templates"] is False

    def test_sin_plan_only_core(self):
        tenant = _make_tenant(plan="SIN_PLAN")
        result = _resolve_features(tenant)
        # Core/security/oauth/backup = always_enabled
        assert result["core.whatsapp_bot"] is True
        assert result["security.jwt_auth"] is True
        # Everything else disabled
        assert result["calendar.schedule"] is False
        assert result["admin.dashboard"] is False
        assert result["admin.metrics"] is False

    def test_override_grants_access(self):
        tenant = _make_tenant(
            plan="FREE_TRIAL",
            overrides={"handoff.web_chat": True},
        )
        result = _resolve_features(tenant)
        assert result["handoff.web_chat"] is True

    def test_override_revokes_access(self):
        tenant = _make_tenant(
            plan="PAID",
            overrides={"calendar.schedule": False},
        )
        result = _resolve_features(tenant)
        assert result["calendar.schedule"] is False

    def test_expired_free_trial_degrades(self):
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        tenant = _make_tenant(plan="FREE_TRIAL", expires=expired)
        result = _resolve_features(tenant)
        # Degrades to SIN_PLAN: only always_enabled
        assert result["core.whatsapp_bot"] is True
        assert result["calendar.schedule"] is False
        assert result["admin.dashboard"] is False

    def test_expired_trial_with_override_still_works(self):
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        tenant = _make_tenant(
            plan="FREE_TRIAL",
            expires=expired,
            overrides={"calendar.schedule": True},
        )
        result = _resolve_features(tenant)
        assert result["calendar.schedule"] is True  # override wins


class TestRegistryConsistency:
    def test_plan_features_keys_exist(self):
        """Todas las keys en PLAN_FEATURES existen en FEATURE_REGISTRY."""
        for plan, keys in PLAN_FEATURES.items():
            for key in keys:
                assert key in FEATURE_REGISTRY, f"{key} in {plan} not in registry"

    def test_dependencies_exist(self):
        """Todas las dependencias referenciadas existen en FEATURE_REGISTRY."""
        for key, feat in FEATURE_REGISTRY.items():
            for dep in feat.dependencies:
                assert dep in FEATURE_REGISTRY, f"{key} depends on {dep} which doesn't exist"

    def test_resolve_returns_all_keys(self):
        """_resolve_features devuelve exactamente las mismas keys que FEATURE_REGISTRY."""
        tenant = _make_tenant(plan="PAID")
        result = _resolve_features(tenant)
        assert set(result.keys()) == set(FEATURE_REGISTRY.keys())
