# Prompt para Sonnet — Actualizar PLAN_V1.3.0.md y BACKLOG.md al sistema de features

## Instruccion Principal

Actualiza `docs/PLAN_V1.3.0.md` y `docs/BACKLOG.md` para reflejar los cambios
introducidos por el sistema de features (ya implementado en la sesion de hoy).
**Solo documentacion**: no toques ningun archivo `.py`, `.html`, `.js`, ni `.css`.

**Lee ANTES de editar**: `docs/PLAN_V1.3.0.md`, `docs/BACKLOG.md`,
`app/core/features.py`, `FEATURES.md`, `CLAUDE.md`.

---

## Contexto: que se implemento hoy

En la sesion 2026-03-30 se implemento el sistema de feature flags completo:

1. `TenantPlan` enum (`SIN_PLAN` / `FREE_TRIAL` / `PAID`) en `app/models/enums.py`
2. `app/core/features.py` — `FEATURE_REGISTRY` con 30+ features, `PLAN_FEATURES`,
   `_resolve_features()`, `get_tenant_features()` (cache Redis 60s),
   `has_feature()`, `invalidate_feature_cache()`, `require_feature()`
3. `app/models/tenant.py` — +3 columnas: `plan`, `plan_expires_at`, `feature_overrides` (JSONB)
4. Migracion Alembic `f7a1b2c3d4e5`
5. `app/routers/admin_features.py` — `GET /admin/features`
6. `app/routers/superadmin.py` — `GET/PUT /tenants/{id}/features`, `PUT /tenants/{id}/plan`
7. `app/schemas/admin.py` — `FeatureInfo`, `TenantFeaturesResponse`, campos `plan` en schemas
8. `app/services/agent.py` — feature checks para `calendar.*` y `email.derivation`
9. `tests/test_features.py` — 11 tests unitarios (todos pasan)

Las features `handoff.*`, `groups.*` ya estan en `FEATURE_REGISTRY` con
`status=PENDING` y `plans=(TenantPlan.PAID,)`. **No hay que crearlas**,
solo marcarlas `IMPLEMENTED` cuando se codifiquen.

---

## Cambios a realizar

### 1. `docs/BACKLOG.md`

**Actualizar tabla "Features ya implementadas"** — anadir al final:

```
| Sistema de feature flags (TenantPlan, FEATURE_REGISTRY, cache Redis) | v1.2.2 |
| FEATURES.md — inventario completo de features | v1.2.2 |
| Per-tenant feature overrides (superadmin) | v1.2.2 |
| Feature check en agent.py (calendar.*, email.derivation) | v1.2.2 |
| Feature check en GET /admin/metrics (admin.metrics) | v1.2.2 |
```

**Actualizar tabla Bloque A** — marcar tarea #25 como completada:

```
| 25 | **Crear FEATURES.md + sistema de features** | ✅ Hecho (v1.2.2) | FEATURES.md creado. Sistema de planes/overrides implementado. |
```

**Actualizar "Orden de ejecucion"** — quitar #25 (ya hecho), dejar:

```
**Orden de ejecucion:** #16/#17/#26 → #18 → resto bloques B-E
```

**Actualizar version del changelog** — cambiar la referencia de estado actual:

```
**Fase actual: v1.3.0** — Derivacion handoff (siguiente tarea).
**v1.2.2** cerrada: sistema de features flags y planes.
```

---

### 2. `docs/PLAN_V1.3.0.md`

Reescribir/ampliar las siguientes secciones del plan. El resto del documento
permanece igual (arquitectura WS, WA bridge, grupales, tests, riesgos).

#### 2a. Anadir nueva seccion al inicio: "Prerequisitos ya implementados"

Insertar despues del bloque "Decisiones del grill-me" y antes de "Versionado":

```markdown
---

## Prerequisitos implementados (v1.2.2)

Antes de empezar v1.3.0, los siguientes sistemas ya estan en produccion:

| Sistema | Archivos | Relevancia para v1.3.0 |
|---------|----------|------------------------|
| `TenantPlan` enum | `app/models/enums.py` | `handoff.*` son `PAID` only |
| `FEATURE_REGISTRY` | `app/core/features.py` | `handoff.web_chat`, `handoff.wa_bridge`, `handoff.cancellation_alert` ya registradas como `PENDING` |
| `has_feature()` + cache Redis 60s | `app/core/features.py` | Usar en cada endpoint nuevo de handoff |
| `invalidate_feature_cache()` | `app/core/features.py` | Llamar si se cambia plan/overrides desde superadmin |
| `plan`, `plan_expires_at`, `feature_overrides` | `app/models/tenant.py` | Disponibles en el modelo |
| `GET/PUT /superadmin/tenants/{id}/features` | `app/routers/superadmin.py` | Superadmin puede habilitar handoff a tenants especificos via override |
| Feature checks en `agent.py` | `app/services/agent.py` | Patron ya establecido para anadir checks de handoff |

**Patron de feature check** (ya establecido en el codigo):
```python
features = await get_tenant_features(tenant_id, db)
if not features.get("handoff.web_chat", False):
    raise HTTPException(status_code=403, detail="Feature no disponible en tu plan")
```
```

#### 2b. Actualizar seccion "7. Orden de implementacion" — v1.3.0

Sustituir la tabla de pasos v1.3.0 por esta version que integra los feature checks:

```markdown
### v1.3.0 — Derivacion handoff (5-7 dias)

| Paso | Que | Archivos | Feature check |
|------|-----|----------|---------------|
| 1 | DB: +`DERIVADA` en `ConversationState`, +`THERAPIST` en `MessageRole` | `app/models/enums.py` | — |
| 2 | DB: +`wa_personal_phone` (Tenant + AdminUser), +`derivation_timeout_minutes` (Tenant), +`sender_name` (Message) | `app/models/*.py` | — |
| 3 | Migracion Alembic `add_derivation_and_wa_fields` | `alembic/versions/` | `down_revision = "f7a1b2c3d4e5"` |
| 4 | `derivation_service.py`: derivate/end/timeout. En `conversation.py`: +`derivate_conversation()`, +`end_derivation()` | nuevos | — |
| 5 | `websocket_manager.py` + `admin_chat.py` (WS endpoint + REST) | nuevos | `has_feature("handoff.web_chat")` en cada endpoint |
| 6 | `wa_bridge_service.py` + deteccion fisio en `webhook.py` | nuevo + modif. | `has_feature("handoff.wa_bridge")` antes de routear al bridge |
| 7 | Alerta cancelacion <24h en `calendar_service.py` | modif. | `has_feature("handoff.cancellation_alert")` |
| 8 | **Marcar features IMPLEMENTED** en `app/core/features.py`: `handoff.web_chat`, `handoff.wa_bridge`, `handoff.cancellation_alert` → `status=FeatureStatus.IMPLEMENTED` | `app/core/features.py` | Hacer en el mismo commit que cada feature |
| 9 | UI: `admin-chat.js` + modificar `admin.html` (tab chat, panel derivacion) | `static/` | — |
| 10 | Tests: `tests/unit/test_derivation_service.py`, `tests/unit/test_wa_bridge_service.py` | `tests/unit/` | — |
```

#### 2c. Actualizar seccion "7. Orden de implementacion" — v1.5.0

Sustituir la tabla de pasos v1.5.0 por esta version:

```markdown
### v1.5.0 — Sesiones grupales (3-4 dias)

| Paso | Que | Archivos | Feature check |
|------|-----|----------|---------------|
| 11 | DB: 3 tablas nuevas (`group_class_definitions`, `group_class_sessions`, `group_class_inscriptions`) | `app/models/group_class.py`, `alembic/` | `down_revision` = revision de v1.3.0 |
| 12 | `group_class_service.py`: CRUD clases, generacion lazy sesiones, inscripciones | nuevo | — |
| 13 | Merge slots en `agent.py` + `calendar_service.py` | modif. | `has_feature("groups.templates")` antes de merge |
| 14 | `admin_classes.py` (CRUD REST) + `admin-classes.js` + `admin.html` (tab clases) | nuevos + modif. | `has_feature("groups.templates")` en endpoints |
| 15 | Alerta cancelacion grupal <24h | `group_class_service.py` | `has_feature("handoff.cancellation_alert")` |
| 16 | **Marcar features IMPLEMENTED** en `app/core/features.py`: `groups.templates`, `groups.sessions`, `groups.inscriptions` | `app/core/features.py` | Hacer en el mismo commit que cada feature |
| 17 | Tests: `tests/unit/test_group_class_service.py`, `tests/integration/test_group_classes_flow.py` | `tests/` | — |
```

#### 2d. Anadir nueva seccion al final: "11. Regla de desarrollo para features"

```markdown
---

## 11. Regla de desarrollo para features (CLAUDE.md regla 10)

Al implementar cada paso de este plan:

1. **Antes de codificar**: la feature ya esta en `FEATURE_REGISTRY` con `status=PENDING`.
2. **Al terminar la feature**: cambiar `status` a `FeatureStatus.IMPLEMENTED` en `app/core/features.py`.
3. **En cada endpoint nuevo**: anadir `has_feature(tenant_id, "handoff.xxx", db)` al inicio.
4. **Si el superadmin necesita probar**: usar `PUT /superadmin/tenants/{id}/features` con
   `{"handoff.web_chat": true}` para habilitar via override sin cambiar el plan.
5. **Cache**: `invalidate_feature_cache(tenant_id)` se llama automaticamente al cambiar
   plan u overrides. No hace falta llamarlo manualmente.

### Features ya registradas para v1.3.0 y v1.5.0

| Key | Plan | Status actual | Cambiar a IMPLEMENTED en paso |
|-----|------|--------------|-------------------------------|
| `handoff.web_chat` | PAID | PENDING | Paso 5 (admin_chat.py) |
| `handoff.wa_bridge` | PAID | PENDING | Paso 6 (wa_bridge_service.py) |
| `handoff.cancellation_alert` | PAID | PENDING | Paso 7 (calendar_service.py) |
| `groups.templates` | PAID | PENDING | Paso 14 (admin_classes.py) |
| `groups.sessions` | PAID | PENDING | Paso 12 (group_class_service.py) |
| `groups.inscriptions` | PAID | PENDING | Paso 12 (group_class_service.py) |
```

---

## Verificacion final

Despues de editar, comprueba:

1. `docs/BACKLOG.md`: tarea #25 aparece como `✅ Hecho (v1.2.2)`.
2. `docs/PLAN_V1.3.0.md`: la seccion "Prerequisitos implementados" existe y es coherente con `app/core/features.py`.
3. `docs/PLAN_V1.3.0.md`: la seccion "7. Orden de implementacion" tiene columna "Feature check" en ambas tablas.
4. `docs/PLAN_V1.3.0.md`: la seccion "11. Regla de desarrollo para features" existe al final.
5. Ningun archivo `.py`, `.html`, `.js` o `.css` modificado.

Commit con mensaje: `docs: update PLAN_V1.3.0 and BACKLOG to integrate feature flags system`
Push a la rama `claude/implement-feature-tracking-YM4vd`.
