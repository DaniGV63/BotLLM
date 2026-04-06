# Plan: Tasks #16, #17, #18 + Alerta cancelación <24h

## Contexto

El bot Atendoo actualmente deriva conversaciones al fisio via email, sin posibilidad de respuesta dentro del sistema. Las sesiones grupales no están soportadas. Este plan aborda:

- **#16** Chat web en admin para que el fisio responda al paciente en tiempo real (WebSocket)
- **#17** WA bridge: el fisio puede responder también desde su WhatsApp personal con prefijos N.
- **#18** Sesiones grupales recurrentes configurables desde admin
- **Extra** Alerta al fisio si una cita/clase se cancela a <24h

---

## Decisiones del grill-me

| Tema | Decisión |
|------|----------|
| Canal fisio | Chat web admin (WebSocket) + WA bridge con N. |
| WA bridge multi-derivación | Prefijo `1. Juan`, `2. Maria`. Sin prefijo + 1 activa → se envía. Sin prefijo + >1 activas → bot pide al fisio que use N. |
| Identidad en chat | Sin prefijo automático. Bot anuncia "Te paso con el fisio", fisio escribe libre |
| Rol en BD | Enum `THERAPIST` + `sender_name` = username del AdminUser que envía |
| Fin handoff | Timeout configurable/tenant (default 1h) + `/bot` por WA o chat. Al expirar timeout → email al fisio |
| Notificación derivación | Email mejorado + sonido/push admin + WA personal via template de Meta con resumen |
| Num. personal fisio | Campo en Tenant (default) + override en AdminUser. Solo superadmin edita |
| Num. bot | Bot en número de la clínica. Derivaciones y alertas van al WA personal del fisio |
| Intent grupales | Mismo `agendar_cita`. Huecos libres mezclan individual + grupal con info extra |
| Tipo grupal | Slots dedicados "clase" recurrentes + excepciones |
| Aforo | Configurable por sesión desde admin |
| Bot y grupales | Las horas grupales son una cita más. Aparecen junto a las individuales con info extra. Sin preguntas extra, sin desbloqueo |
| Tracking plazas | BD (verdad) + Google Calendar (asistente). Slots llenos NO aparecen |
| Cancelación grupal | Misma mecánica que individual. Plaza se libera |
| Alerta <24h | Email + WA personal al fisio |
| Feature flags | Plan separado. Registrar TODAS las features (existentes + nuevas) en FEATURES.md para futuro sistema de pricing |
| Tests | Unitarios + integración + e2e (Playwright) |

---

## Versionado

### v1.3.0 — Derivación handoff (#16 + #17)
Chat web WebSocket + WA bridge + alerta cancelación individual <24h.
Estimación: 5-7 días.

### v1.5.0 — Sesiones grupales (#18)
Clases grupales recurrentes + alerta cancelación grupal <24h.
Estimación: 3-4 días.

(v1.4.0 reservada para bugfixes/polish post-v1.3.0)

---

## 1. Cambios en base de datos

### Tablas modificadas

**`tenants`** — 2 columnas nuevas:
- `wa_personal_phone` String(20), nullable — WA personal del fisio
- `derivation_timeout_minutes` Integer, default 60

**`admin_users`** — 1 columna nueva:
- `wa_personal_phone` String(20), nullable — override por usuario

**`conversations`** — sin cambio de esquema. `ConversationState` enum en Python: +`DERIVADA`

**`messages`** — 1 columna nueva:
- `sender_name` String(100), nullable — username del admin que envía (solo para role=THERAPIST)
- `MessageRole` enum en Python: +`THERAPIST`

### Tablas nuevas (v1.5.0)

**`group_class_definitions`** — plantillas de clases recurrentes:
- id UUID PK
- tenant_id FK tenants
- nombre String(100) — "Pilates", "Yoga"
- dias_semana String(20) — JSON array [0,2,4] para L/X/V
- hora String(5) — "10:00"
- duracion_min Integer, default 60
- max_capacidad Integer, default 8
- activa Boolean, default true
- created_at, updated_at

**`group_class_sessions`** — instancias concretas:
- id UUID PK
- definition_id FK group_class_definitions
- tenant_id FK tenants
- fecha Date
- hora String(5) — hereda de definition, puede override
- estado String(20) — PROGRAMADA / CANCELADA
- google_event_id String(200), nullable
- created_at
- Unique: (definition_id, fecha)

**`group_class_inscriptions`** — inscripciones de pacientes:
- id UUID PK
- session_id FK group_class_sessions
- tenant_id FK tenants
- wa_phone String(20)
- nombre_paciente String(200), nullable
- created_at
- Unique: (session_id, wa_phone)

### Migraciones Alembic
1. `add_derivation_and_wa_fields` — campos en tenants, admin_users, messages
2. `add_group_classes_tables` — 3 tablas nuevas (para v1.5.0)

---

## 2. Archivos a crear

| Archivo | Líneas est. | Descripción |
|---------|-------------|-------------|
| `app/services/derivation_service.py` | ~150 | Orquestar derivación: cambiar estado, notificar (email + WA template + push), timeout |
| `app/services/wa_bridge_service.py` | ~120 | Parsear msgs fisio (N.), routing, mappings Redis |
| `app/services/websocket_manager.py` | ~80 | ConnectionManager para WS por tenant |
| `app/services/group_class_service.py` | ~200 | CRUD clases, generación sesiones, inscripciones, merge slots |
| `app/models/group_class.py` | ~80 | 3 modelos + enum SessionState |
| `app/routers/admin_chat.py` | ~200 | WS endpoint + REST chat + end-derivation |
| `app/routers/admin_classes.py` | ~150 | CRUD clases grupales + sesiones + inscripciones |
| `static/admin-chat.js` | ~180 | WebSocket client, chat UI, notificaciones, sonido |
| `static/admin-classes.js` | ~120 | UI gestión clases grupales |
| `tests/conftest.py` | ~100 | Fixtures: async DB, Redis mock, tenant/user factories |
| `tests/unit/test_derivation_service.py` | ~150 | Tests unitarios derivación |
| `tests/unit/test_wa_bridge_service.py` | ~120 | Tests unitarios WA bridge routing |
| `tests/unit/test_group_class_service.py` | ~150 | Tests unitarios clases grupales |
| `tests/integration/test_derivation_flow.py` | ~200 | Tests integración flujo derivación completo |
| `tests/integration/test_group_classes_flow.py` | ~150 | Tests integración flujo grupal completo |
| `tests/e2e/test_admin_chat.py` | ~120 | Tests e2e Playwright para chat admin |
| `tests/e2e/test_admin_classes.py` | ~100 | Tests e2e Playwright para gestión clases |

## 3. Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `app/models/enums.py` | +DERIVADA en ConversationState, +THERAPIST en MessageRole |
| `app/models/tenant.py` | +wa_personal_phone, +derivation_timeout_minutes |
| `app/models/admin_user.py` | +wa_personal_phone |
| `app/models/message.py` | +sender_name String(100) nullable |
| `app/models/__init__.py` | Import nuevos modelos |
| `app/schemas/admin.py` | Nuevos campos en TenantRead/Update, schemas grupales |
| `app/services/agent.py` | Bypass LLM si DERIVADA, bifurcar grupo/individual en create |
| `app/services/conversation.py` | +derivate_conversation(), +end_derivation() |
| `app/services/email_service.py` | Email derivación mejorado con historial + email timeout |
| `app/services/whatsapp_service.py` | Reutilizar send_text() para enviar a personal del fisio |
| `app/services/calendar_service.py` | Integrar slots grupales en respuesta de huecos |
| `app/routers/webhook.py` | Detectar si sender es fisio (WA bridge) antes de llamar agent |
| `app/routers/admin.py` | +wa_personal_phone en campos protegidos superadmin, filtro estado |
| `app/main.py` | Registrar nuevos routers |
| `static/admin.html` | Tab chat + tab clases + derivation panel |
| `static/admin.js` | Integrar tabs chat y clases (se permite >400 líneas) |
| `CLAUDE.md` | Regla: registrar features únicas para futuro sistema de pricing |

---

## 4. Arquitectura WebSocket

### Conexión
```
Browser → wss://domain/ws/chat?token=JWT → FastAPI WebSocket
```
JWT como query param (WS no soporta headers custom). Servidor valida, extrae tenant_id, añade a ConnectionManager.

### Protocolo mensajes (JSON)
```
Server → Client:
  derivation_new     {conversation_id, patient_name, phone, motivo, summary}
  patient_message    {conversation_id, content, timestamp}
  derivation_ended   {conversation_id, reason: timeout|manual|bot_command}

Client → Server:
  therapist_send     {conversation_id, content}
  end_derivation     {conversation_id}
```

### ConnectionManager
Dict `{tenant_id: list[WebSocket]}`. Singleton global.
Auto-reconnect en cliente con exponential backoff.

---

## 5. WA Bridge — Lógica de routing

### Detección fisio vs paciente (webhook.py)
1. Mensaje llega → extraer wa_phone del sender
2. Buscar wa_phone en admin_users.wa_personal_phone y tenants.wa_personal_phone
3. Si match → es fisio → route a wa_bridge_service
4. Si no match → es paciente → route a agent como siempre
5. Cache en Redis (5 min) para no consultar BD cada mensaje

### Mappings en Redis
```
bridge:{tenant_id}:mappings   → Hash { "1.": {phone, conv_id, name}, "2.": ... }
bridge:{tenant_id}:counter    → Int (siguiente número)
TTL = derivation_timeout_minutes del tenant
```

### Parseo mensaje fisio
```python
re.match(r"^(\d+)\.\s+(.+)", text)  → (numero, contenido)
```

### Casos edge — Sin prefijo N.
- Solo 1 derivación activa → se envía automáticamente a ese paciente
- Múltiples derivaciones activas → bot responde al fisio: "Tienes N derivaciones activas. Usa 1., 2. ... para indicar a quién respondes"
- N. inválido → bot responde: "No hay derivación activa con ese número"
- Fisio escribe sin derivaciones activas → ignorar, log warning

### Template message para Meta
Crear template aprobado por Meta para la notificación de derivación. El `motivo` es dinámico: lo genera el LLM describiendo por qué el paciente quiere hablar con el fisio. Contenido:
```
[Atendoo] Paciente necesita atención
Nombre: {{patient_name}}
Motivo: {{motivo}}
Resumen: {{last_messages_summary}}
Responde con {{number}}. para hablar con este paciente.
```

---

## 6. Sesiones grupales — Generación de slots

### Merge de huecos libres
```python
# En agent.py, al preparar contexto para agendar_cita:
individual_slots = await get_free_slots(tenant_id)
group_slots = await get_available_group_slots(tenant_id)  # solo con plazas
context["free_slots"] = merge_slots(individual_slots, group_slots)
```

### Formato merged
```json
[{
  "date": "2026-04-01",
  "day_name": "miércoles",
  "slots": [
    "09:00",
    "10:00 - Pilates grupal (3 plazas)",
    "11:00",
    "16:00"
  ]
}]
```

Slots grupales sin plazas NO aparecen. El LLM presenta los huecos tal cual. El paciente elige uno. El código detecta si es grupal comparando datetime con group_class_sessions.

### Generación lazy de sesiones
Cuando se piden huecos, generar sesiones faltantes para los próximos 7 días. INSERT IF NOT EXISTS por (definition_id, fecha). Sin scheduler de fondo.

### Inscripción
1. Paciente elige slot grupal → código detecta match con session
2. Check plazas: SELECT COUNT inscriptions WHERE session_id, con SELECT FOR UPDATE en session
3. Si plazas llenas → informar al paciente, ofrecer otros horarios
4. INSERT inscription + add attendee en Google Calendar event
5. Si es primera inscripción de la sesión → crear evento Calendar con google_event_id

### Cancelación
1. DELETE inscription + remove attendee de Calendar
2. Si cancelación a <24h → check_cancellation_alert() → email + WA al fisio

---

## 7. Orden de implementación

### v1.3.0 — Derivación (5-7 días)

| Paso | Qué | Días |
|------|-----|------|
| 1 | DB: enums + campos tenant/admin_user/message + migración | 0.5 |
| 2 | derivation_service.py + conversation.py (derivate/end) | 1 |
| 3 | websocket_manager.py + admin_chat.py (WS endpoint) | 1 |
| 4 | wa_bridge_service.py + webhook.py (detección fisio) | 1 |
| 5 | admin-chat.js + admin.html (UI chat) | 1.5 |
| 6 | Timeout (Redis TTL + check en cada msg DERIVADA + email) | 0.5 |
| 7 | Notificaciones: email mejorado + push + WA template | 1 |
| 8 | Alerta cancelación <24h (individual) | 0.5 |
| 9 | Tests unitarios + integración + e2e chat | 1 |
| 10 | Integrar lógica chat/clases en admin.js (se permite >400 líneas) | Paralelo |

### v1.5.0 — Grupales (3-4 días)

| Paso | Qué | Días |
|------|-----|------|
| 11 | DB: modelos + migración 3 tablas | 0.5 |
| 12 | group_class_service.py (CRUD, sesiones, inscripciones) | 1.5 |
| 13 | Merge slots en agent.py + calendar_service.py | 0.5 |
| 14 | admin_classes.py + admin-classes.js + admin.html | 1 |
| 15 | Alerta cancelación <24h (grupal) | 0.5 |
| 16 | Tests unitarios + integración + e2e clases | 1 |

---

## 8. Riesgos y edge cases

| Riesgo | Mitigación |
|--------|------------|
| WS se desconecta (red, sleep) | Auto-reconnect con backoff. Msgs guardados en PG, se muestran al reconectar |
| Race condition bot/fisio | Estado DERIVADA en PG antes de notificar. Msgs durante DERIVADA no van al LLM |
| Fisio no responde (timeout) | Auto-end + msg al paciente "te contactaremos" + **email al fisio** avisando del timeout |
| Template WA para iniciar conv | Aprobar template en Meta Business. Alternativa: pedir al fisio que envíe un msg al bot |
| Cancelación sesión con inscritos | Notificar a todos los inscritos por WA (batch con delays para rate limit) |
| Timezone | Siempre Europe/Madrid para check <24h y generación de sesiones |
| admin.js excepción | Se permite superar 400 líneas para admin.js (excepción a la regla general) |

---

## 9. Tests

### Dependencias de testing (requirements-test.txt)
```
pytest==8.3.4
pytest-asyncio==0.24.0
httpx==0.27.0
aiosqlite==0.20.0
fakeredis[aioredis]==2.25.0
pytest-cov==6.0.0
playwright==1.49.0
pytest-playwright==0.6.2
testcontainers[postgres,redis]==4.8.0
```

### Estructura de tests
```
tests/
├── conftest.py                          # Fixtures compartidos (DB, Redis, mocks, factories)
├── unit/
│   ├── test_derivation_service.py       # derivate, end, timeout, notificaciones
│   ├── test_wa_bridge_service.py        # parseo prefijos, routing, edge cases
│   └── test_group_class_service.py      # slots, inscripción, cancelación, lazy gen
├── integration/
│   ├── test_derivation_flow.py          # flujo completo derivación (PG + Redis reales)
│   └── test_group_classes_flow.py       # flujo completo grupales
└── e2e/
    ├── test_admin_chat.py               # Playwright: chat UI, WS, notificaciones
    └── test_admin_classes.py            # Playwright: CRUD clases, sesiones, inscripciones
```

---

## 10. Regla global: registro de features

Añadir a CLAUDE.md:

> **Registro de features:** Mantener un archivo `FEATURES.md` con TODAS las features del sistema (existentes + nuevas). Cada feature: nombre, descripción, versión de introducción, si es activable por tenant. Al desarrollar una feature nueva, registrarla inmediatamente. Esto prepara el terreno para un futuro sistema de pricing por tiers.
