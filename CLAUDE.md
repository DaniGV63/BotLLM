# CLAUDE.md — Atendoo

Guía compacta para Claude Code. Leer ENTERO antes de tocar cualquier archivo.
Para detalles: ver PLAN.md (fases, BD, Docker) y LOGICA.md (LLM, prompts, flujo).
Antes de cualquier exploración, indica tu mejor respuesta estimada en 1 o 2 frases. Luego, pregúntame si quiero que la verifiques en el código o que procedas con la acción.

---

## QUÉ ES

Bot de WhatsApp para clínicas de fisioterapia. Dos llamadas LLM por mensaje:
1. `detect_intent` → clasifica intención (barata, rápida)
2. `generate_response` → redacta respuesta con contexto ya preparado (JSON mode)

El código orquesta todo. El LLM solo clasifica y redacta.
El LLM NUNCA decide disponibilidad, NUNCA ejecuta acciones.

## STACK

FastAPI + PostgreSQL + Redis + OpenAI SDK (GPT-4o-mini) + Google GenAI SDK (Gemini 2.5 Flash)
+ Meta WhatsApp Cloud API + Google Calendar API + Gmail API.
**Sin LangChain.** Wrapper propio en `llm_client.py` (~100 líneas).

## ENTORNO DEL DESARROLLADOR

- Windows, VS Code fork (Antigravity), Python 3.12 via Miniconda
- **Entorno conda:** `botllm` — SIEMPRE usar `conda run -n botllm` o `conda activate botllm`. NUNCA usar `base`.
- Docker Desktop para PostgreSQL y Redis
- Claude Code como extensión de VS Code
- El desarrollador lanza todo manualmente: docker, alembic, seed, logs

## ESTRUCTURA

```
Atendoo/
├── CLAUDE.md, PLAN.md, LOGICA.md
├── prompts/
│   ├── negocio.md                  ← datos del fisio (servicios, horarios, FAQ)
│   ├── intent_detection.md         ← prompt para clasificar intención
│   └── response_generation.md      ← prompt para generar respuesta (JSON mode)
├── app/
│   ├── main.py
│   ├── core/    (config, database, redis, security, features)
│   ├── models/  (tenant, conversation, message, group_class)
│   ├── schemas/ (llm.py → LLMResponse, ActionCreate, etc.)
│   └── services/
│       ├── llm_client.py           ← wrapper: OpenAIClient + GeminiClient + singleton
│       ├── llm_service.py          ← detect_intent() + generate_response()
│       ├── agent.py                ← orquestador (excepción líneas)
│       ├── conversation.py         ← historial Redis + sync PG + ciclo vida
│       ├── calendar_service.py     ← get_free_slots, create/modify/cancel appointment
│       ├── whatsapp_service.py     ← parse_incoming + send_text
│       ├── email_service.py        ← Gmail send
│       ├── derivation_service.py   ← derivación handoff: estado + email + WS + Redis
│       ├── wa_bridge_service.py    ← fisio responde desde WA personal (prefijos N.)
│       ├── websocket_manager.py    ← ConnectionManager singleton por tenant
│       ├── group_class_service.py  ← CRUD clases, sesiones lazy, inscripciones
│       └── backup_service.py       ← backup/restore multi-tenant (V2 JSON)
│   └── routers/
│       ├── webhook.py              ← GET/POST webhook Meta
│       ├── admin.py                ← panel admin (login, config, métricas)
│       ├── admin_chat.py           ← WS chat handoff + REST derivaciones
│       ├── admin_classes.py        ← CRUD clases grupales, sesiones, inscritos (API)
│       ├── admin_calendar.py       ← eventos unificados + bloqueo + sesiones grupales
│       ├── admin_features.py       ← endpoints features
│       ├── superadmin.py           ← CRUD tenants, usuarios, onboarding status
│       └── oauth.py                ← flujo OAuth2 Google Calendar/Gmail
├── static/
│   ├── admin.html                  ← panel admin (template HTML)
│   ├── admin.js                    ← lógica JS del panel admin
│   ├── admin-chat.js               ← WebSocket client, chat UI derivaciones
│   ├── admin-calendar.js           ← FullCalendar v6: citas, clases, work_blocks
│   ├── admin-calendar-classes.js   ← modal chooser + detalle sesión grupal
│   ├── admin-superadmin.js         ← lógica UI superadmin
│   └── atendoo.css                ← estilos compartidos
├── landing/
│   └── index.html                  ← landing page comercial
├── backup_tenant.py, restore_tenant.py  ← scripts CLI backup/restore
├── seed.py, docker-compose.yml, Dockerfile, requirements.txt
```

## REGLAS INQUEBRANTABLES

0. **PROHIBIDO DESTRUIR DATOS — REGLA ABSOLUTA**
   - **NUNCA** ejecutar `docker compose down` seguido de `docker compose up` — esto borra el volumen PostgreSQL y destruye todos los datos de clientes, conversaciones y configuración del tenant.
   - Para reiniciar contenedores: usar **`docker compose restart`** (preserva volúmenes).
   - Para reiniciar solo la app: matar el proceso uvicorn y relanzarlo.
   - Si hay conflicto de puertos: parar el contenedor/proceso que ocupa el puerto, **no recrear volúmenes**.
   - Los datos de tenant (tokens WhatsApp, Google Calendar, etc.) viven en la BD con backup automático al startup. Restaurar con `python restore_tenant.py backups/<archivo>.json`.

1. **MUY RECOMENDABLE no superar 300 líneas por archivo de programación** (`.py`, `.js`, `.ts`, etc.) — refactorizar si crece. Superar puntualmente está permitido si la alternativa rompe la cohesión del módulo, pero nunca superar 400 líneas bajo ningún concepto. Esta regla NO aplica a archivos de markup/template (`.html`, `.css`, `.md`).
2. **LLM singleton** por provider en llm_client.py
3. **PG es fuente de verdad** — PG primero, Redis después
4. **Estados como Enum** — ACTIVA / INACTIVA, nunca strings sueltos
5. **tenant_id en toda función de servicio** — multi-tenant desde día 1
6. **El LLM solo clasifica y redacta** — no decide disponibilidad, no ejecuta
7. **Prompts en archivos .md** — no hardcodeados en código ni en BD
8. **Solo texto plano** en WhatsApp — nada de List Messages, Reply Buttons, Flows
9. **SDK directo** — openai + google-genai, sin LangChain
10. **Registro de features** — Toda feature nueva debe registrarse en `app/core/features.py` (FEATURE_REGISTRY) y en `FEATURES.md`. Feature key = dotted notation (`modulo.subfeature`). Asignacion de plan obligatoria.
11. **Actualizar estado tras implementar** — Después de completar un plan que modifique el bot, ejecutar `/update-status` para sincronizar FEATURES.md, BACKLOG.md, CLAUDE.md y PLAN.md.

## FLUJO DE CADA MENSAJE

```
Webhook POST → validar HMAC → deduplicar → BackgroundTask:
  1. detect_intent(message, history[-4:]) → intent string
  2. Preparar contexto según intención:
     - faq → negocio.md (ya en memoria)
     - agendar_cita → get_free_slots() de Calendar
     - cancelar/modificar → get_appointment_by_phone()
  3. generate_response(message, intent, context, history) → JSON {message, action, nombre}
  4. Si action.type in (create, modify, cancel): safety net → ejecutar en Calendar
  5. Si action.type == "derivar": send_notification_email
  6. Si action.type == "despedida": deactivate_conversation (INACTIVA)
  6. Persistir: PG primero, Redis después
  7. Enviar response.message por WhatsApp
```

## COMPORTAMIENTO DEL BOT

- Responde directamente a lo que el paciente pide. Sin "¿Cómo te llamas?" al inicio
- Nombre SOLO cuando necesario (agendar, cancelar). Se guarda y no se repide
- RGPD: línea de consentimiento en el PRIMER mensaje de conversación nueva
- Mensajes no-texto: "Solo puedo leer mensajes de texto" — no llama al LLM
- Error de sistema: fallback + derivar a humano automáticamente
- Safety net: código valida confirmación antes de ejecutar action de Calendar

## CONVENCIONES

- Python 3.12+, type hints, async/await para I/O
- Ruff (linter + formatter)
- Conventional commits: feat:, fix:, refactor:, docs:
- Manejo de errores: try/except → log → fallback → derivar → return
- Logging: structlog JSON, siempre tenant_id + wa_phone. Contenido solo en DEBUG
- Separar decisión de ejecución (no mezclar lógica con I/O)
- Firmas de funciones explícitas (ver PLAN.md §6 para todas las firmas)

## CONFIG (.env)

```
LLM_PROVIDER=gemini        # "openai" o "gemini"
LLM_MODEL=gemini-2.5-flash      # gpt-4o-mini o "gemini-2.5-flash"
OPENAI_API_KEY=
GEMINI_API_KEY=             # solo si gemini
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
ENCRYPTION_KEY=             # Fernet
META_APP_SECRET=
GOOGLE_CLIENT_ID=           # OAuth2
GOOGLE_CLIENT_SECRET=       # OAuth2
BASE_URL=http://localhost:8000
LOG_LEVEL=INFO
```

## Contexto de despliegue
- Producción utiliza docker-compose.prod.yml (NO el docker-compose.yml por defecto)
- La terminal es PowerShell en Windows - NO uses continuaciones de línea con barra invertida ni secuencias de escape al estilo bash
- Comprueba siempre los nombres reales de los servicios en el archivo compose antes de ejecutar comandos de Docker

## Git y Versionado
- Al etiquetar una versión (release), usa etiquetas anotadas (git tag -a) que cubran TODOS los commits relevantes, no solo el último
- Después de cualquier despliegue o incremento de versión, verifica que la cadena de versión esté actualizada en el código (no solo en la documentación/commits)
- Incluye en los commits únicamente los archivos que el usuario haya mencionado explícitamente

## Estilo de Planificación y Ejecución
- Cuando el usuario haga una pregunta directa, responde directamente antes de explorar el código
- Mantén las iteraciones del plan concisas; pregunta antes de realizar una exploración exhaustiva

## Convenciones
- Nunca marques las comprobaciones/tareas como 'completadas' en las tablas de estado hasta que se haya verificado que realmente están terminadas
- Las credenciales/tokens deben almacenarse cifrados en .env por defecto

## FASE ACTUAL

→ **v1.7.1** — Gaps, estabilidad y UI/Admin

### Changelog v1.7.1
- `agent.py`: nombre del paciente actualizable en cualquier momento (eliminado guard `not conversation.nombre_paciente`)
- `admin.html`: fix layout chat derivaciones (`hidden flex flex-col` en lugar de `hidden flex-col`)
- `admin-chat.js`: formato teléfono con `formatPhone()` en lista y header de chat
- `prompts/response_generation.md`: regla anti mensajes de espera + actualización de nombre + sección historial de citas
- `prompts/intent_detection.md`: nuevo intent `consultar_historial`
- `admin_calendar.py`: `colorId: "11"` en eventos de bloqueo
- `agent.py` + `modificar_cita`: inyección de `free_slots` en el contexto del LLM
- `conversation.py` modelo + migración Alembic `d4e5f6a1b2c3`: columna `rgpd_accepted` (RGPD persistido en PG)
- `agent.py`: Crash recovery — persiste mensajes de error y deriva automáticamente en ambos bloques except
- `main.py`: `_derivation_timeout_loop()` — background task cada 5 min para cerrar derivaciones por timeout
- `calendar_service.py`: `get_past_appointments()` — historial citas pasadas desde Google Calendar
- `agent.py`: intent `consultar_historial` → inyecta `past_appointments` en contexto
- WS real-time: `conversation_updated` y `calendar_event_changed` broadcasts desde `agent.py` y `admin_calendar.py`
- `admin-chat.js`: WS conecta en login (no solo al abrir tab chat), polling fallback reducido a 30s
- `calendar_service.py`: `create_group_calendar_event()` + `delete_group_calendar_event()` (colorId 10 verde)
- `group_class_service.py`: sync idempotente sesiones → Google Calendar al generarlas
- `admin_classes.py` + `admin_calendar.py`: limpieza eventos GCal al cancelar/eliminar sesiones
- `admin_calendar.py`: `DELETE /block/{event_id}` + `PATCH /block/{event_id}` — editar/borrar bloqueos
- `admin-calendar.js`: click en bloqueos → modal editar/borrar; `slotDuration: '00:15:00'`
- `admin.html`: modal editar bloqueo; `admin.js`: auto-cerrar sidebar en móvil
- `atendoo.css`: media queries responsive para panel admin en móvil

### Changelog v1.6.1
- Gestión de clases grupales migrada al tab Calendario (eliminado tab independiente)
- 3 nuevos endpoints en `admin_calendar`: `POST /create-class`, `GET /session/{id}`, `DELETE /session/{id}`
- Modal chooser al pulsar hueco: bloquear horario o crear sesión grupal
- Detalle de sesión con lista de inscritos, edición, cancelación e eliminación de serie
- Validaciones inline en modal de creación de clase
- Eliminado `static/admin-classes.js` (UI absorbida por `admin-calendar-classes.js`)
- Permite seleccionar el día de hoy en el calendario

### Changelog v1.6.0
- Migración BD: `work_blocks` (JSONB) y `slot_duration_minutes` por tenant
- `calendar_service`: slots dinámicos según `work_blocks` + `format_work_blocks_for_prompt`
- `agent.py` + `llm_service`: inyección de horarios reales en contexto del LLM
- `group_class_service`: validación clases grupales contra `work_blocks`
- Nuevo router `admin_calendar.py`: `GET /events` (citas + clases + work_blocks) + `POST /block`
- `superadmin`: `plan_expires_at` en lista tenants, parseo datetime, botón clear fecha
- Features nuevas: `admin.work_blocks` y `admin.calendar_view` (FREE_TRIAL + PAID, beta)
- `admin-superadmin.js` (nuevo): lógica superadmin extraída de `admin.js`
- `admin-calendar.js` (nuevo): FullCalendar v6 — semana desde lunes, 24h, vista unificada
- `admin.js`: editor horario semanal, duración cita, integración calendario
- Superadmin UI: columna Plan + Baja, toggle expiración, features PENDING grises

### Changelog v1.5.0
- Modelos BD: `GroupClassDefinition`, `GroupClassSession`, `GroupClassInscription` + migración
- `group_class_service`: CRUD definiciones, generación lazy de sesiones, inscripciones con SELECT FOR UPDATE, alerta cancelación <24h
- Slots grupales mezclados con slots individuales en intent `agendar_cita` (feature `groups.sessions`)
- `ActionCreate` con campos opcionales `is_group_class` + `session_id` → `inscribe_patient()` en lugar de Calendar
- Router `admin/classes`: CRUD definiciones, sesiones con conteo inscritos, generación lazy, lista inscritos (feature gate `groups.templates`)
- UI: tab "Clases grupales" en panel admin con formulario, tabla, sesiones e inscritos
- Features grupales marcadas IMPLEMENTED en features.py y FEATURES.md
- Tests: 20 tests nuevos (unitarios + integración), total 68/68 pasados

### Changelog v1.4.0
- Superadmin puede editar `wa_personal_phone` y `derivation_timeout_minutes` del tenant
- Cambiar `wa_personal_phone` invalida automáticamente la cache Redis del fisio
- Filtro `?estado=` en `GET /admin/conversations` (ACTIVA, INACTIVA, DERIVADA)

### Changelog v1.3.0
- Estado de conversación `DERIVADA`: bypass LLM, mensajes del paciente se notifican al fisio
- `derivation_service`: orquesta derivación (estado + email + push WS + Redis mapping)
- `websocket_manager`: ConnectionManager singleton por tenant para el chat en tiempo real
- `admin_chat` router: WS `/admin/chat/ws` + REST `/send`, `/end`, `/active`, `/messages`
- `wa_bridge_service`: fisio responde desde WA personal con prefijos `N.` o `1.`, comando `/bot`
- Webhook detecta si el sender es el fisio → rutea a WA bridge (sin llamar al LLM)
- Alerta cancelación `<24h` por email al fisio (feature `handoff.cancellation_alert`)
- UI: tab "Chat derivaciones" en panel admin con lista activa, chat, badge, sonido
- Campos nuevos: `wa_personal_phone` (Tenant + AdminUser), `derivation_timeout_minutes` (Tenant), `sender_name` (Message)

### Changelog v1.2.2
- Sistema de feature flags con planes (SIN_PLAN / FREE_TRIAL / PAID)
- `features.py`: FEATURE_REGISTRY con 37 features, resolución con cache Redis 60s
- `has_feature()`, `get_tenant_features()`, `require_feature()` dependency FastAPI
- `FEATURES.md`: inventario completo de features para futuro sistema de pricing
- Campos nuevos en Tenant: `plan`, `plan_expires_at`, `feature_overrides` (JSONB)
- Migración Alembic: f7a1b2c3d4e5

### Changelog v1.2.1
- Landing: nuevo headline hero "Recupera tiempo para lo que más te importa"
- Landing: añadido enlace "Contacta" en navbar
- Landing: hover con escala en tarjetas de beneficios (`hover:scale-[1.02]`)
- Landing: icono WhatsApp nativo (SVG) en lugar de lucide en tarjeta "Sin apps nuevas"
- Landing: scroll suave habilitado (`scroll-smooth` + `scroll-padding-top`)
- Landing: copy más inclusivo ("clientes" en lugar de "pacientes" en sección beneficios)

### Changelog v1.2.0
- Estado DESPEDIDA → INACTIVA + deactivate/reactivate conversation
- Acción "despedida" en prompt y agent
- OAuth router para Google Calendar/Gmail por tenant
- Backup/restore multi-tenant (automático al startup, CLI manual)
- Admin panel refactorizado (HTML/JS/CSS separados)
- Endpoint onboarding-status para checklist de configuración
- Rename BotLLM → Atendoo en toda la codebase

## REFERENCIAS

- **PLAN.md** — fases, BD, firmas de funciones, Docker, anti-patrones
- **LOGICA.md** — prompts completos, wrapper LLM, safety net, flujo del orquestador
- **DEPLOY.md** — guía de despliegue Hetzner
- **prompts/negocio.md** — datos del fisio para el LLM
- **prompts/intent_detection.md** — prompt de clasificación de intención
- **prompts/response_generation.md** — prompt de generación de respuesta
- **docs/BACKLOG.md** — backlog completo (26 tareas, bloques A-E), estado actual
- **docs/PLAN_V1.3.0.md** — plan detallado derivación handoff + sesiones grupales (v1.3.0/v1.5.0)
- **docs/SESSION_2026_03_29.md** — última sesión: decisiones arquitectura v1.3.0/v1.5.0
