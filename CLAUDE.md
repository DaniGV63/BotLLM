# CLAUDE.md — BotLLM

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
- Docker Desktop para PostgreSQL y Redis
- Claude Code como extensión de VS Code
- El desarrollador lanza todo manualmente: docker, alembic, seed, logs

## ESTRUCTURA

```
BotLLM/
├── CLAUDE.md, PLAN.md, LOGICA.md
├── prompts/
│   ├── negocio.md                  ← datos del fisio (servicios, horarios, FAQ)
│   ├── intent_detection.md         ← prompt para clasificar intención
│   └── response_generation.md      ← prompt para generar respuesta (JSON mode)
├── app/
│   ├── main.py
│   ├── core/    (config, database, redis, security)
│   ├── models/  (tenant, conversation, message)
│   ├── schemas/ (llm.py → LLMResponse, ActionCreate, etc.)
│   └── services/
│       ├── llm_client.py           ← wrapper: OpenAIClient + GeminiClient + singleton
│       ├── llm_service.py          ← detect_intent() + generate_response()
│       ├── agent.py                ← orquestador (≤200 líneas)
│       ├── conversation.py         ← historial Redis + sync PG
│       ├── calendar_service.py     ← get_free_slots, create/modify/cancel appointment
│       ├── whatsapp_service.py     ← parse_incoming + send_text
│       └── email_service.py        ← Gmail send
├── seed.py, docker-compose.yml, Dockerfile, requirements.txt
```

## REGLAS INQUEBRANTABLES

1. **Ningún archivo > 300 líneas** — refactorizar si crece
2. **LLM singleton** por provider en llm_client.py
3. **PG es fuente de verdad** — PG primero, Redis después
4. **Estados como Enum** — ACTIVA / DESPEDIDA, nunca strings sueltos
5. **tenant_id en toda función de servicio** — multi-tenant desde día 1
6. **El LLM solo clasifica y redacta** — no decide disponibilidad, no ejecuta
7. **Prompts en archivos .md** — no hardcodeados en código ni en BD
8. **Solo texto plano** en WhatsApp — nada de List Messages, Reply Buttons, Flows
9. **SDK directo** — openai + google-genai, sin LangChain

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
LOG_LEVEL=INFO
```

## FASE ACTUAL

→ **Fase 6: Producción v1.0** (ver DEPLOY.md para guía completa)

## REFERENCIAS

- **PLAN.md** — fases, BD, firmas de funciones, Docker, anti-patrones
- **LOGICA.md** — prompts completos, wrapper LLM, safety net, flujo del orquestador
- **prompts/negocio.md** — datos del fisio para el LLM
- **prompts/intent_detection.md** — prompt de clasificación de intención
- **prompts/response_generation.md** — prompt de generación de respuesta
