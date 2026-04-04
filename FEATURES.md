# FEATURES.md — Attendoo Feature Registry

Inventario completo de features del proyecto. Fuente de verdad para:
- Tracking del estado de desarrollo
- Sistema de planes (SIN_PLAN / FREE_TRIAL / PAID)
- Feature flags por tenant (overrides)
- Planificacion y priorizacion

---

## Planes

| Plan | Descripcion | Expiracion |
|------|-------------|------------|
| **SIN_PLAN** | Usuario registrado sin tenant activo. Ve la interfaz admin vacia. Para curiosos que se registran en la web. | — |
| **FREE_TRIAL** | 14 dias. Features esenciales: bot, calendario, email, admin (sin analiticas). | `plan_expires_at` → degrada a SIN_PLAN |
| **PAID** | Todas las features. Mensualidad recurrente. | Sin expiracion |

**Overrides por tenant**: El superadmin puede dar/quitar features individuales a cualquier tenant, independiente de su plan. Util para demos, clientes VIP, o primer cliente.

---

## Trackers

Cada feature tiene estos campos:

| Campo | Valores | Proposito |
|-------|---------|-----------|
| **key** | `modulo.subfeature` | Identificador unico (dotted notation) |
| **status** | `implementada` / `en-progreso` / `pendiente` | Estado de desarrollo |
| **dificultad** | `S` / `M` / `L` / `XL` | Complejidad logica |
| **prioridad** | `alta` / `media` / `baja` | Urgencia de implementacion |
| **dependencias** | lista de keys | Features que deben existir antes |
| **estabilidad** | `estable` / `beta` / `experimental` | Riesgo de rotura |
| **impacto conversion** | `alto` / `medio` / `bajo` | Cuanto empuja de free a paid |
| **plan** | `always` / `free+paid` / `paid` | Plan minimo requerido |
| **version** | `v1.0`, `v1.3`, etc. | Version de introduccion |

---

## Core — always_enabled

Features fundamentales del bot. Siempre activas en todos los planes.

| Key | Nombre | Status | Dif. | Estab. | Version |
|-----|--------|--------|------|--------|---------|
| `core.whatsapp_bot` | Motor principal del bot | implementada | XL | estable | v1.0 |
| `core.intent_detection` | Deteccion de intenciones (LLM call 1) | implementada | L | estable | v1.0 |
| `core.response_generation` | Generacion de respuestas (LLM call 2) | implementada | L | estable | v1.0 |
| `core.conversation_lifecycle` | Ciclo vida ACTIVA/INACTIVA | implementada | M | estable | v1.2 |
| `core.rgpd_consent` | Consentimiento RGPD primer mensaje | implementada | S | estable | v1.0 |

---

## Calendar — free+paid

Gestion de citas via Google Calendar.

| Key | Nombre | Status | Dif. | Prio. | Conv. | Estab. | Deps | Version |
|-----|--------|--------|------|-------|-------|--------|------|---------|
| `calendar.free_slots` | Consultar disponibilidad | implementada | M | alta | alto | estable | `oauth.google_calendar` | v1.0 |
| `calendar.schedule` | Agendar citas | implementada | L | alta | alto | estable | `oauth.google_calendar` | v1.0 |
| `calendar.cancel` | Cancelar citas | implementada | M | alta | medio | estable | `calendar.schedule` | v1.0 |
| `calendar.modify` | Modificar citas | implementada | M | alta | medio | estable | `calendar.schedule` | v1.0 |

---

## Email — free+paid

Comunicacion por email con el fisioterapeuta.

| Key | Nombre | Status | Dif. | Prio. | Conv. | Estab. | Deps | Version |
|-----|--------|--------|------|-------|-------|--------|------|---------|
| `email.derivation` | Derivacion a fisio por email | implementada | M | alta | medio | estable | `oauth.google_gmail` | v1.0 |

---

## Admin — diferenciado por plan

Panel de administracion. Algunas features solo en PAID.

| Key | Nombre | Plan | Status | Dif. | Estab. | Version |
|-----|--------|------|--------|------|--------|---------|
| `admin.dashboard` | Panel principal | free+paid | implementada | L | estable | v1.1 |
| `admin.conversations` | Visor de mensajes | free+paid | implementada | M | estable | v1.1 |
| `admin.tenant_config` | Configuracion tenant | free+paid | implementada | M | estable | v1.1 |
| `admin.metrics` | Analiticas de datos | **paid** | implementada | M | estable | v1.1 |

---

## Security — always_enabled

| Key | Nombre | Status | Version |
|-----|--------|--------|---------|
| `security.hmac_validation` | Validacion HMAC webhook | implementada | v1.0 |
| `security.rate_limiting` | Rate limiting por tenant | implementada | v1.0 |
| `security.jwt_auth` | Autenticacion JWT admin | implementada | v1.1 |
| `security.encryption` | Encriptacion tokens (Fernet) | implementada | v1.0 |

---

## OAuth — always_enabled

| Key | Nombre | Status | Version |
|-----|--------|--------|---------|
| `oauth.google_calendar` | OAuth2 Google Calendar | implementada | v1.2 |
| `oauth.google_gmail` | OAuth2 Gmail | implementada | v1.2 |

---

## Backup — always_enabled

| Key | Nombre | Status | Version |
|-----|--------|--------|---------|
| `backup.auto_backup` | Backup automatico al startup | implementada | v1.2 |
| `backup.restore` | Restore desde JSON | implementada | v1.2 |

---

## Handoff v1.3.0 — paid

Derivacion en tiempo real al fisioterapeuta.

| Key | Nombre | Status | Dif. | Prio. | Conv. | Estab. | Deps | Version |
|-----|--------|--------|------|-------|-------|--------|------|---------|
| `handoff.web_chat` | Chat web fisio (WebSocket) | pendiente | L | alta | alto | beta | `email.derivation` | v1.3 |
| `handoff.wa_bridge` | Puente WhatsApp fisio | pendiente | L | alta | alto | beta | `email.derivation` | v1.3 |
| `handoff.cancellation_alert` | Alerta cancelacion <24h | pendiente | M | alta | medio | beta | `calendar.cancel` | v1.3 |

---

## Clases Grupales v1.5.0 — paid

Clases recurrentes con capacidad.

| Key | Nombre | Status | Dif. | Prio. | Conv. | Estab. | Deps | Version |
|-----|--------|--------|------|-------|-------|--------|------|---------|
| `groups.templates` | Plantillas clases recurrentes | implementada | L | media | alto | beta | `calendar.schedule` | v1.5 |
| `groups.sessions` | Sesiones con capacidad | implementada | M | media | alto | beta | `groups.templates` | v1.5 |
| `groups.inscriptions` | Inscripciones pacientes | implementada | M | media | medio | beta | `groups.sessions` | v1.5 |

---

## Futuro — paid

Features planificadas sin version asignada.

| Key | Nombre | Status | Dif. | Prio. | Conv. | Estab. | Deps |
|-----|--------|--------|------|-------|-------|--------|------|
| `reminders.appointment_24h` | Recordatorio 24h antes | pendiente | M | alta | alto | — | `calendar.schedule` |
| `i18n.multi_language` | Soporte multi-idioma | pendiente | L | baja | medio | — | — |
| `payments.gateway` | Pasarela de pago (Stripe/Redsys) | pendiente | XL | media | alto | — | — |
| `waitlist.management` | Lista de espera | pendiente | M | baja | medio | — | `calendar.schedule` |
| `history.appointments` | Historial citas en BD | pendiente | M | media | bajo | — | `calendar.schedule` |
| `analytics.llm_costs` | Analiticas coste LLM | pendiente | S | baja | bajo | — | `admin.metrics` |

---

## Resumen por Plan

| Modulo | SIN_PLAN | FREE_TRIAL | PAID |
|--------|----------|------------|------|
| Core | ✅ | ✅ | ✅ |
| Security | ✅ | ✅ | ✅ |
| OAuth | ✅ | ✅ | ✅ |
| Backup | ✅ | ✅ | ✅ |
| Calendar | ❌ | ✅ | ✅ |
| Email | ❌ | ✅ | ✅ |
| Admin (dashboard, mensajes, config) | ❌ | ✅ | ✅ |
| Admin (analiticas) | ❌ | ❌ | ✅ |
| Handoff (v1.3) | ❌ | ❌ | ✅ |
| Clases Grupales (v1.5) | ❌ | ❌ | ✅ |
| Recordatorios | ❌ | ❌ | ✅ |
| Multi-idioma | ❌ | ❌ | ✅ |
| Pagos | ❌ | ❌ | ✅ |

---

## Implementacion Tecnica

### Modelo de datos (Tenant)

3 columnas nuevas en la tabla `tenants`:
```
plan            VARCHAR(20)  NOT NULL  DEFAULT 'SIN_PLAN'
plan_expires_at TIMESTAMPTZ  NULL
feature_overrides JSONB      NOT NULL  DEFAULT '{}'
```

### Enum TenantPlan
```
SIN_PLAN    → solo always_enabled
FREE_TRIAL  → always_enabled + free+paid features
PAID        → todas las features
```

### Resolucion has_feature(tenant_id, feature_key)
```
1. feature_overrides del tenant (maxima prioridad)
2. Features del plan del tenant
3. always_enabled (core, security, oauth, backup)
4. FREE_TRIAL expirado → degrada a SIN_PLAN
5. Cache Redis 60s
```

### Archivos clave
```
app/core/features.py          ← Registry + has_feature() + require_feature()
app/models/tenant.py           ← +3 columnas
app/routers/admin_features.py  ← Endpoints features (separado de admin.py)
app/routers/superadmin.py      ← CRUD plan/features por tenant
tests/test_features.py         ← 10 tests unitarios
```

### Regla para desarrollo futuro
> Toda feature nueva debe registrarse en `app/core/features.py` (FEATURE_REGISTRY) y en este archivo (FEATURES.md). Feature key = dotted notation (`modulo.subfeature`). Asignacion de plan obligatoria.
