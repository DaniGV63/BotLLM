# CLAUDE.md — Attendoo

Guía compacta para Claude Code. Leer ENTERO antes de tocar cualquier archivo.
Para detalles: ver PLAN.md (fases, BD, Docker) y LOGICA.md (LLM, prompts, flujo).

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
Attendoo/
├── CLAUDE.md, PLAN.md, LOGICA.md
├── prompts/
│   ├── negocio.md                  ← datos del fisio (servicios, horarios, FAQ)
│   ├── intent_detection.md         ← prompt para clasificar intención
│   └── response_generation.md      ← prompt para generar respuesta (JSON mode)
├── app/
│   ├── main.py
│   ├── core/    (config, database, redis, security, features)
│   ├── models/  (tenant, conversation, message)
│   ├── schemas/ (llm.py → LLMResponse, ActionCreate, etc.)
│   └── services/
│       ├── llm_client.py           ← wrapper: OpenAIClient + GeminiClient + singleton
│       ├── llm_service.py          ← detect_intent() + generate_response()
│       ├── agent.py                ← orquestador (≤200 líneas)
│       ├── conversation.py         ← historial Redis + sync PG + ciclo vida (deactivate/reactivate)
│       ├── calendar_service.py     ← get_free_slots, create/modify/cancel appointment
│       ├── whatsapp_service.py     ← parse_incoming + send_text
│       ├── email_service.py        ← Gmail send
│       └── backup_service.py       ← backup/restore multi-tenant (V2 JSON)
│   └── routers/
│       ├── webhook.py              ← GET/POST webhook Meta
│       ├── admin.py                ← panel admin (login, config, métricas)
│       ├── superadmin.py           ← CRUD tenants, usuarios, onboarding status
│       ├── admin_features.py       ← endpoints features (separado de admin.py)
│       └── oauth.py                ← flujo OAuth2 Google Calendar/Gmail
├── static/
│   ├── admin.html                  ← panel admin (template HTML)
│   ├── admin.js                    ← lógica JS del panel admin
│   └── attendoo.css                ← estilos compartidos
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
LLM_PROVIDER=openai        # "openai" o "gemini"
LLM_MODEL=gpt-4o-mini      # o "gemini-2.5-flash"
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

## FASE ACTUAL

→ **v1.4.0** — Polish post-handoff

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
- Rename BotLLM → Attendoo en toda la codebase

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
