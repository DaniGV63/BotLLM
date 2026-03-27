# PLAN.md — Bot WhatsApp Fisioterapeuta (Attendoo)

Documento maestro. Fases con checklist, esquema BD, estructura de ficheros, convenciones.

---

## 1. VISIÓN GENERAL

Bot de WhatsApp para clínicas de fisioterapia. El paciente escribe en lenguaje natural,
el código orquesta todo (detecta intención, consulta datos, genera respuesta), el LLM
solo clasifica y redacta — nunca decide disponibilidad ni ejecuta acciones.

**Funcionalidades v1:**
1. FAQ — responde preguntas sobre la clínica (precios, horarios, servicios, ubicación)
2. Agendar cita — consulta huecos libres en Calendar, el LLM redacta la respuesta
3. Cancelar/modificar cita — busca cita por teléfono, el LLM redacta confirmación
4. Derivar a humano — notifica al fisio por email via Gmail API

**Decisiones arquitectónicas clave:**
- **SDK directo** (openai + google-genai) con wrapper propio — sin LangChain
- **Dos llamadas LLM por mensaje**: detect_intent (barata, rápida) + generate_response (con contexto)
- **El LLM nunca decide disponibilidad** — el código consulta Calendar primero y pasa los huecos
- **El LLM no ejecuta acciones** — devuelve JSON estructurado, el código ejecuta en Calendar
- GPT-4o-mini como modelo principal, Gemini 2.5 Flash como alternativa (configurable por env)
- Prompts en archivos .md versionados en Git
- Sin panel admin en MVP — el desarrollador controla todo
- GitHub con tags por fase de implementación
- Multi-tenant desde día 1 (tenant_id en toda función de servicio)

---

## 2. ANTI-PATRONES A NO REPETIR (del proyecto Bot/)

| # | Anti-patrón | Qué pasó | Solución en Attendoo |
|---|---|---|---|
| 1 | God file | agent.py creció a 1754 líneas, 18 handlers | Ningún archivo > 300 líneas. Separar en llm_client.py, llm_service.py, agent.py |
| 2 | Interactivos + LLM | List Messages + Reply Buttons + LLM = 11 estados | LLM solo redacta texto. Sin mensajes interactivos |
| 3 | LLM instanciado por llamada | Nueva instancia en cada invocación | Singleton por provider en llm_client.py |
| 4 | JSONB sin schema | estado_datos era dict libre | Sin estado parcial. Pydantic para respuestas del LLM |
| 5 | Dual write sin orden | Redis + PG sin transacción | PG fuente de verdad. PG primero, Redis después |
| 6 | Estados como strings | Typo fallaba silenciosamente | Enum (ACTIVA, DESPEDIDA) |
| 7 | Handlers mezclan lógica con I/O | Imposible testear | Separar decisión de ejecución |
| 8 | Flujo rígido al inicio | "¿Cómo te llamas?" obligatorio | Responder directamente. Nombre solo cuando hace falta |
| 9 | LLM decide disponibilidad | Alucinaciones de horarios | Código consulta Calendar, LLM solo redacta |
| 10 | Framework pesado (LangChain) | Capa de abstracción innecesaria | SDK directo + wrapper propio (~100 líneas) |

**Checklist antes de cada fase:**
- [ ] ¿Algún archivo supera 300 líneas? → Refactorizar
- [ ] ¿El LLM se instancia más de una vez? → Singleton
- [ ] ¿Redis y PG se escriben sin orden claro? → PG primero, Redis después
- [ ] ¿Hay strings literales para estados? → Enum
- [ ] ¿El LLM decide algo que debería decidir el código? → Mover al código

---

## 3. FLUJO DE CADA MENSAJE

```
1. Webhook recibe mensaje de WhatsApp
2. Validar HMAC + deduplicar + extraer texto
3. BackgroundTask:
   a. detect_intent(message) → "faq" | "agendar_cita" | "cancelar_cita" | "modificar_cita" | "otro"
   b. Según intención, consultar datos ANTES de llamar al LLM:
      - faq: cargar negocio.md (ya en memoria)
      - agendar_cita: get_free_slots() de Calendar
      - cancelar/modificar: get_appointment_by_phone() de Calendar
      - otro: nada extra
   c. generate_response(message, intent, context) → {message: str, action: dict | None}
   d. Si action != None: ejecutar acción en Calendar (create/modify/cancel)
   e. Enviar response.message por WhatsApp
   f. Persistir mensajes (PG primero, Redis después)
```

### Ejemplos de flujo

**FAQ (sin consultar Calendar):**
```
Paciente: "¿Qué horario tenéis?"
→ detect_intent → "faq"
→ context = {business_info: negocio.md, history: [...]}
→ generate_response → {message: "Nuestro horario es de L-V 9:00-20:00...", action: None}
→ enviar mensaje
```

**Agendar cita (consulta Calendar primero):**
```
Paciente: "Quiero una cita para el jueves"
→ detect_intent → "agendar_cita"
→ get_free_slots(days_ahead=7, duration_minutes=60) → [{date: "2025-03-20", slots: ["09:00","10:00",...]}]
→ context = {business_info, free_slots, history, nombre_paciente (si se conoce)}
→ generate_response → {message: "Para el jueves tengo hueco a las 9, 10, 11...", action: None}
  (aún no hay acción porque falta nombre/hora/confirmación)

Paciente: "A las 10, soy María García"
→ detect_intent → "agendar_cita"
→ get_free_slots(...) → [...]  (verificar que las 10 sigue libre)
→ generate_response → {message: "Confirmo: jueves 20/03 a las 10:00 para María García. ¿Confirmas?", action: None}

Paciente: "Sí"
→ detect_intent → "agendar_cita"
→ generate_response → {message: "✅ Cita reservada...", action: {type: "create", datetime: "2025-03-20T10:00", duration: 60, client_name: "María García", client_phone: "34612..."}}
→ create_appointment(...) → event_id
→ enviar mensaje
```

### Reglas de flujo
- **Primer mensaje**: responder directamente a lo que pide. Sin forzar nombre
- **Nombre**: solo se pide cuando necesario (agendar, cancelar). Se guarda y no se repide
- **RGPD**: línea de consentimiento en el PRIMER mensaje de conversación nueva
- **Mensajes no texto**: "Solo puedo leer mensajes de texto" — no llama al LLM
- **Expiración**: sin actividad > 24h → resetear conversación
- **Error de sistema**: fallback + derivar a humano automáticamente
- **Safety net**: el código valida confirmación antes de ejecutar action

---

## 4. STACK TÉCNICO

```
Canal:          Meta WhatsApp Cloud API (directa, sin BSP)
Backend:        FastAPI (Python 3.11+)
LLM:            SDK directo — openai (GPT-4o-mini) + google-genai (Gemini 2.5 Flash)
ORM:            SQLAlchemy 2.x (async) + Alembic
BD:             PostgreSQL 15
Caché/sesiones: Redis 7 (historial conversacional, TTL 24h)
Agenda:         Google Calendar API (google-auth + googleapiclient)
Notificaciones: Gmail API
Hosting:        Hetzner VPS CX22 (4GB RAM, 2 vCPU)
Contenedores:   Docker Compose (FastAPI + PostgreSQL + Redis + Nginx)
Proxy inverso:  Nginx + Let's Encrypt (Certbot)
CDN:            Cloudflare (capa gratuita)
Linter:         Ruff
Versionado:     Git + GitHub (tag por fase)
```

**Dependencias Python (requirements.txt):**
```
fastapi
uvicorn[standard]
pydantic-settings
python-dotenv
sqlalchemy[asyncio]
asyncpg
redis[asyncio]
alembic
openai
google-genai
google-auth-oauthlib
google-api-python-client
httpx
cryptography
bcrypt
python-jose[cryptography]
structlog
ruff
pytest
pytest-asyncio
```

**Sin LangChain.** El wrapper propio en `llm_client.py` abstrae ambos providers en ~100 líneas.

---

## 5. ESTRUCTURA DE FICHEROS

```
Attendoo/
├── CLAUDE.md                          ← guía compacta para Claude Code
├── PLAN.md                            ← este archivo
├── LOGICA.md                          ← lógica LLM: prompts, flujo, respuestas
├── .env                               ← NUNCA commitear
├── .env.example
├── .gitignore
├── docker-compose.yml                 ← dev: app + db + redis
├── docker-compose.prod.yml            ← prod: + nginx
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── seed.py                            ← crea primer tenant en BD
├── prompts/                           ← PROMPTS PARA EL LLM (versionados en Git)
│   ├── intent_detection.md            ← prompt para detectar intención
│   ├── response_generation.md         ← prompt para generar respuesta final
│   └── negocio.md                     ← info del fisio (servicios, horarios, FAQ)
├── alembic/
│   └── versions/
├── app/
│   ├── main.py                        ← FastAPI app, lifespan, health check
│   ├── core/
│   │   ├── config.py                  ← Settings pydantic-settings
│   │   ├── database.py                ← engine async, SessionLocal, get_db
│   │   ├── redis.py                   ← lazy singleton Redis
│   │   └── security.py               ← HMAC, Fernet, bcrypt, JWT
│   ├── models/
│   │   ├── __init__.py
│   │   ├── tenant.py                  ← modelo Tenant
│   │   ├── conversation.py            ← ACTIVA / DESPEDIDA (Enum)
│   │   └── message.py                 ← role: user/assistant, intent, action
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── llm.py                     ← LLMResponse, ActionCreate, ActionModify, etc.
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_client.py             ← wrapper: OpenAIClient + GeminiClient + singleton
│   │   ├── llm_service.py            ← detect_intent() + generate_response()
│   │   ├── calendar_service.py       ← get_free_slots, get/create/modify/cancel appointment
│   │   ├── agent.py                   ← orquestador (≤200 líneas)
│   │   ├── conversation.py            ← historial Redis (20 msgs) + sync PG
│   │   ├── whatsapp_service.py       ← parse_incoming + send_text
│   │   └── email_service.py          ← Gmail API send
│   └── routers/
│       ├── __init__.py
│       ├── webhook.py                 ← GET/POST webhook Meta
│       └── admin.py                   ← panel admin (Fase 5, post-MVP)
├── static/
│   └── admin.html                     ← panel admin (Fase 5, post-MVP)
└── tests/
    ├── conftest.py
    ├── test_webhook.py
    ├── test_llm_service.py
    ├── test_calendar_service.py
    └── test_agent.py
```

---

## 6. FIRMAS EXPLÍCITAS DE FUNCIONES

### llm_client.py — Wrapper de providers

```python
from dataclasses import dataclass

@dataclass
class LLMResponse:
    content: str
    usage: dict  # {input_tokens: int, output_tokens: int}

class LLMClient:
    """Interfaz común para providers LLM."""
    async def chat(self, messages: list[dict], json_mode: bool = False) -> LLMResponse: ...

class OpenAIClient(LLMClient):
    """GPT-4o-mini via SDK oficial de OpenAI."""
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"): ...
    async def chat(self, messages: list[dict], json_mode: bool = False) -> LLMResponse: ...

class GeminiClient(LLMClient):
    """Gemini 2.5 Flash via SDK oficial de Google."""
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"): ...
    async def chat(self, messages: list[dict], json_mode: bool = False) -> LLMResponse: ...

# Singleton
_client: LLMClient | None = None

def get_llm_client() -> LLMClient:
    """Devuelve singleton. Lee LLM_PROVIDER de config."""
    global _client
    if _client is None:
        if settings.LLM_PROVIDER == "openai":
            _client = OpenAIClient(api_key=settings.OPENAI_API_KEY, model=settings.LLM_MODEL)
        elif settings.LLM_PROVIDER == "gemini":
            _client = GeminiClient(api_key=settings.GEMINI_API_KEY, model=settings.LLM_MODEL)
    return _client
```

### llm_service.py — Detección + Generación

```python
async def detect_intent(message: str, history: list[dict]) -> str:
    """Clasifica la intención del mensaje.
    
    Args:
        message: texto del paciente
        history: últimos mensajes para contexto de continuación
    
    Returns:
        "faq" | "agendar_cita" | "modificar_cita" | "cancelar_cita" | "derivar_humano" | "otro"
    """

async def generate_response(
    message: str,
    intent: str,
    context: dict,
    history: list[dict],
) -> dict:
    """Genera respuesta + acción opcional.
    
    Args:
        message: texto del paciente
        intent: intención detectada
        context: {
            "business_info": str,          # contenido de negocio.md
            "free_slots": list[dict]|None, # huecos libres (solo si intent=agendar)
            "appointment": dict|None,      # cita existente (solo si intent=cancelar/modificar)
            "current_datetime": str,       # fecha/hora actual
            "nombre_paciente": str|None,   # si se conoce
        }
        history: últimos mensajes de la conversación
    
    Returns:
        {
            "message": str,                # texto para enviar al paciente
            "action": dict | None          # None si no hay acción, o:
              # {"type":"create","datetime":"2025-03-20T10:00","duration":60,
              #  "client_name":"María","client_phone":"34612..."}
              # {"type":"modify","event_id":"abc123","new_datetime":"2025-03-21T11:00"}
              # {"type":"cancel","event_id":"abc123"}
              # {"type":"derivar","motivo":"paciente quiere hablar con persona"}
            "nombre_detectado": str | None # nombre que el paciente dijo (para guardar)
        }
    """
```

### calendar_service.py — Google Calendar

```python
async def get_free_slots(
    tenant_id: UUID,
    days_ahead: int = 7,
    duration_minutes: int = 60,
) -> list[dict]:
    """Devuelve huecos libres respetando horario laboral, citas existentes, y festivos.
    
    Returns:
        [{"date": "2025-03-20", "day_name": "jueves",
          "slots": ["09:00","10:00","11:00",...]}]
    """

async def get_appointment_by_phone(
    tenant_id: UUID,
    phone: str,
) -> dict | None:
    """Busca la próxima cita de ese teléfono.
    
    Returns:
        {"event_id":"abc","datetime":"2025-03-20T10:00","service":"fisioterapia",
         "client_name":"María"} o None
    """

async def create_appointment(
    tenant_id: UUID,
    phone: str,
    client_name: str,
    datetime_iso: str,
    duration_minutes: int,
    service: str,
) -> str:
    """Crea evento en Calendar. Devuelve event_id."""

async def modify_appointment(
    tenant_id: UUID,
    event_id: str,
    new_datetime_iso: str,
) -> bool:
    """Modifica fecha/hora de un evento. True si OK."""

async def cancel_appointment(
    tenant_id: UUID,
    event_id: str,
) -> bool:
    """Elimina evento de Calendar. True si OK."""
```

### whatsapp_service.py — Meta API

```python
def parse_incoming_webhook(body: dict) -> dict | None:
    """Extrae datos del webhook o None si no es un mensaje procesable.
    
    Returns:
        {"phone_number_id": str, "wa_phone": str, "wa_message_id": str,
         "message_type": str, "text": str | None, "contact_name": str | None}
    """

async def send_text(
    tenant_id: UUID,
    wa_phone: str,
    message: str,
) -> dict | None:
    """Envía mensaje de texto plano. Devuelve response de Meta o None si error."""
```

### agent.py — Orquestador

```python
async def handle_message(
    tenant_id: UUID,
    wa_phone: str,
    message_text: str,
    wa_message_id: str,
    db: AsyncSession,
) -> None:
    """Punto de entrada. Llamado desde BackgroundTask del webhook.
    
    Flujo:
    1. get_or_create_conversation
    2. detect_intent
    3. preparar contexto según intención (consultar Calendar si necesario)
    4. generate_response
    5. ejecutar action si existe (Calendar/Email)
    6. guardar nombre si se detectó
    7. persistir mensajes (PG → Redis)
    8. enviar respuesta por WhatsApp
    """
```

### conversation.py — Historial

```python
async def get_history(
    tenant_id: UUID,
    wa_phone: str,
    max_messages: int = 20,
) -> list[dict]:
    """Lee historial de Redis. Si no existe, reconstruye desde PG."""

async def append_message(
    tenant_id: UUID,
    wa_phone: str,
    role: str,
    content: str,
    intent: str | None = None,
    action: str | None = None,
) -> None:
    """Guarda mensaje en PG (fuente de verdad) y actualiza Redis (caché)."""
```

### email_service.py — Gmail

```python
async def send_notification_email(
    tenant_id: UUID,
    patient_name: str | None,
    patient_phone: str,
    motivo: str,
) -> bool:
    """Envía email al fisio avisando que un paciente quiere contacto. True si OK."""
```

---

## 7. ESQUEMA DE BASE DE DATOS

### Tabla `tenants`

```sql
CREATE TABLE tenants (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                     VARCHAR(50) UNIQUE NOT NULL,
    nombre_negocio           VARCHAR(200) NOT NULL,
    email_notificaciones     VARCHAR(200) NOT NULL,
    whatsapp_phone_number_id VARCHAR(50) UNIQUE NOT NULL,
    whatsapp_token           TEXT,            -- encriptado Fernet
    whatsapp_verify_token    VARCHAR(100),
    meta_app_secret          TEXT,            -- encriptado Fernet
    google_calendar_id       VARCHAR(200),
    google_access_token      TEXT,            -- encriptado Fernet
    google_refresh_token     TEXT,            -- encriptado Fernet
    google_token_expiry      TIMESTAMPTZ,
    bot_activo               BOOLEAN NOT NULL DEFAULT TRUE,
    admin_username           VARCHAR(100) UNIQUE,
    admin_password_hash      VARCHAR(200),
    activo                   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Servicios, horarios, prompts NO están en BD. Viven en `prompts/*.md`.

### Tabla `conversations`

```sql
CREATE TABLE conversations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    wa_phone          VARCHAR(20) NOT NULL,
    nombre_paciente   VARCHAR(200),
    estado            VARCHAR(20) NOT NULL DEFAULT 'ACTIVA'
                      CHECK (estado IN ('ACTIVA', 'DESPEDIDA')),
    ultimo_mensaje_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_conversations_tenant_phone UNIQUE (tenant_id, wa_phone)
);
```

### Tabla `messages`

```sql
CREATE TABLE messages (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id   UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role              VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant')),
    content           TEXT NOT NULL,
    wa_message_id     VARCHAR(100) UNIQUE,
    wa_timestamp      TIMESTAMPTZ,
    status            VARCHAR(20) DEFAULT NULL,
    intent            VARCHAR(30),
    action_executed   VARCHAR(50),
    processing_ms     INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 8. CONTRATO API DE META

### Webhook entrante
```python
phone_number_id = data["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"]
wa_phone        = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
wa_message_id   = data["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
tipo_mensaje    = data["entry"][0]["changes"][0]["value"]["messages"][0]["type"]
mensaje_texto   = data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
```

### Casos edge
1. Webhook de status (delivered/read) → actualizar BD, devolver 200
2. Array messages vacío → devolver 200
3. wa_message_id duplicado → devolver 200 (deduplicación)
4. tipo_mensaje != "text" → responder "Solo puedo leer mensajes de texto", devolver 200

### Patrón: 200 inmediato + BackgroundTask
```python
@router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    # Validar HMAC + extraer datos → síncrono, rápido
    background_tasks.add_task(process_message, ...)
    return {"status": "ok"}
```

### Envío (solo texto plano)
```
POST https://graph.facebook.com/v19.0/{phone_number_id}/messages
Authorization: Bearer {whatsapp_token}
{"messaging_product":"whatsapp","to":"{wa_phone}","type":"text","text":{"body":"{msg}"}}
```

---

## 9. SEGURIDAD

### .env.example
```bash
# Base de datos
DATABASE_URL=postgresql+asyncpg://fisiobot:fisiobot_dev@localhost:5432/fisiobot
REDIS_URL=redis://localhost:6379/0

# Encriptación
ENCRYPTION_KEY=           # Fernet.generate_key()
SECRET_KEY=               # 32+ chars aleatorios

# LLM
LLM_PROVIDER=openai       # "openai" o "gemini"
LLM_MODEL=gpt-4o-mini     # o "gemini-2.5-flash"
OPENAI_API_KEY=
GEMINI_API_KEY=            # solo si LLM_PROVIDER=gemini

# Meta
META_APP_SECRET=

# Logging
LOG_LEVEL=INFO             # DEBUG para ver contenido de mensajes
```

### Campos encriptados (Fernet)
`whatsapp_token`, `meta_app_secret`, `google_access_token`, `google_refresh_token`

---

## 10. DOCKER

### docker-compose.yml (dev)
```yaml
services:
  app:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    volumes:
      - ./app:/app/app
      - ./prompts:/app/prompts
    depends_on: [db, redis]
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: fisiobot
      POSTGRES_USER: fisiobot
      POSTGRES_PASSWORD: fisiobot_dev
    volumes: [postgres_data:/var/lib/postgresql/data]
    ports: ["5432:5432"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
volumes:
  postgres_data:
```

### Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

---

## 11. CONVENCIONES

- Python 3.11+, type hints, async/await para I/O
- Ruff (linter + formatter)
- Conventional commits (`feat:`, `fix:`, `refactor:`, `docs:`)
- **Ningún archivo > 300 líneas**
- **LLM singleton** por provider
- **PG fuente de verdad** → PG primero, Redis después
- **Estados como Enum**
- **tenant_id en toda función de servicio**
- **El LLM solo clasifica y redacta** — nunca decide disponibilidad ni ejecuta

---

## 12. FASES DE IMPLEMENTACIÓN

Cada fase = tag en GitHub. No saltar fases.

### FASE 1 — Infraestructura base → `v0.1`
```
□ git init + .gitignore + GitHub repo privado
□ docker-compose.yml + Dockerfile + requirements.txt
□ app/core/config.py (Settings con LLM_PROVIDER, LLM_MODEL)
□ app/core/database.py (engine async + get_db)
□ app/core/redis.py (lazy singleton)
□ app/core/security.py (Fernet + HMAC)
□ app/models/ (tenant, conversation, message con Enum)
□ app/schemas/llm.py (LLMResponse, ActionCreate, etc.)
□ alembic init + migración inicial
□ seed.py (primer tenant)
□ prompts/negocio.md (placeholder)
□ prompts/intent_detection.md
□ prompts/response_generation.md
□ app/main.py (lifespan + health check)
□ Verificar: docker compose up → alembic upgrade head → seed.py → OK
□ git tag v0.1
```

### FASE 2 — Webhook de Meta → `v0.2`
```
□ app/services/whatsapp_service.py (parse_incoming + send_text)
□ app/routers/webhook.py (GET verificación + POST recepción)
□ Deduplicación, status webhooks, mensajes no-texto
□ BackgroundTask
□ Verificar: ngrok + WhatsApp → log + echo
□ git tag v0.2
```

### FASE 3 — Motor LLM → `v0.3`
```
□ app/services/llm_client.py (OpenAIClient + GeminiClient + singleton)
□ app/services/llm_service.py (detect_intent + generate_response)
□ app/services/conversation.py (historial Redis 20 msgs + PG)
□ app/services/agent.py (orquestador ≤200 líneas)
□ Safety net confirmación
□ Stubs de Calendar (log pero no ejecutan)
□ Verificar: FAQ funciona + agendar genera action correcta (sin Calendar real)
□ git tag v0.3
```

### FASE 4 — Integraciones → `v0.4`
```
□ app/services/calendar_service.py (get_free_slots, get/create/modify/cancel)
□ app/services/email_service.py (Gmail send)
□ Conectar agent.py → calendar_service + email_service
□ Guardar nombre_paciente en conversation
□ Verificar: agendar + cancelar + modificar + derivar end-to-end
□ git tag v0.4
```

### FASE 5 — Panel admin (post-MVP) → `v0.5`
```
□ app/routers/admin.py
□ static/admin.html
□ git tag v0.5
```

### FASE 6 — Producción → `v1.0`
```
□ docker-compose.prod.yml + Nginx + Certbot
□ Hetzner VPS + Cloudflare
□ Todos los flujos desde móvil real
□ git tag v1.0
```

---

## 13. DATOS DEL PRIMER TENANT

```python
PRIMER_TENANT = {
    "slug": "fisio-cliente",
    "nombre_negocio": "[COMPLETAR]",
    "email_notificaciones": "[COMPLETAR]",
    "whatsapp_phone_number_id": "1023364914199630",
    "whatsapp_verify_token": "[GENERAR]",
    "bot_activo": True,
}
```

**Preguntar al fisio (para `prompts/negocio.md`):**
- Servicios, duración y precio
- Horarios por día
- Mutuas aceptadas
- Política de cancelación
- 5-10 preguntas frecuentes
- Email para notificaciones
- Dirección y teléfono

---

## 14. CHECKLIST DE ENTREGA

```
□ Bot funcionando en WhatsApp del fisio
□ RGPD: consentimiento en primera interacción
□ prompts/negocio.md con datos reales
□ Google Calendar conectado y probado
□ 4 flujos probados desde móvil (FAQ, agendar, cancelar, derivar)
□ Documento 1 página para el fisio
□ 2 semanas soporte post-entrega
```
