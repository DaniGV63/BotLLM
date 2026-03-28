# LOGICA.md — Lógica del LLM (Attendoo)

Define las dos llamadas LLM, el formato de respuesta, prompts, safety net y manejo de errores.
Referencia técnica para Claude Code al implementar `llm_client.py`, `llm_service.py` y `agent.py`.

---

## 1. ARQUITECTURA: DOS LLAMADAS LLM POR MENSAJE

```
Mensaje del paciente
        ↓
[1] detect_intent(message, history)
    → LLM con prompt minimalista → devuelve string: "faq" | "agendar_cita" | ...
        ↓
[2] Código prepara contexto según intención:
    - faq: carga negocio.md
    - agendar_cita: get_free_slots() de Calendar
    - cancelar/modificar: get_appointment_by_phone()
    - derivar_humano: nada extra
    - otro: nada extra
        ↓
[3] generate_response(message, intent, context, history)
    → LLM con todo el contexto → devuelve JSON: {message, action, nombre_detectado}
        ↓
[4] Código ejecuta action si existe (Calendar/Email)
        ↓
[5] Enviar response.message por WhatsApp
```

### Por qué dos llamadas y no una

La primera llamada (detect_intent) es barata y rápida — solo clasifica. Esto permite que el código
sepa QUÉ datos consultar ANTES de la segunda llamada. Sin esto, tendrías que pasar siempre todos
los datos posibles (huecos de Calendar, citas existentes, etc.) aunque no hagan falta, desperdiciando
tokens y aumentando latencia.

La segunda llamada (generate_response) recibe contexto ya preparado — el LLM solo redacta.
Nunca decide si hay disponibilidad, nunca consulta nada, nunca ejecuta. Devuelve un JSON
estructurado que el código interpreta y ejecuta.

---

## 2. LLAMADA 1: DETECT_INTENT

### Prompt (`prompts/intent_detection.md`)

```markdown
Clasifica la intención del último mensaje del paciente en una clínica de fisioterapia.

Devuelve SOLO una de estas categorías, sin explicación:
- faq (preguntas sobre el negocio: precios, horarios, servicios, ubicación, mutuas)
- agendar_cita (quiere reservar una cita nueva, o está en proceso de hacerlo)
- modificar_cita (quiere cambiar fecha/hora de una cita que ya tiene)
- cancelar_cita (quiere cancelar una cita existente)
- derivar_humano (quiere hablar con una persona, o pide algo que el bot no puede hacer)
- otro (saludo suelto, mensaje irrelevante, o no se puede clasificar)

IMPORTANTE sobre continuación de conversación:
- Si el historial muestra que el paciente está en medio de agendar una cita
  (el bot le preguntó hora, servicio, o confirmación), clasifica como "agendar_cita"
  aunque el mensaje actual sea solo "sí", "a las 10", o un nombre.
- Lo mismo aplica para cancelar y modificar: si el contexto previo es de esa acción,
  mantén la intención aunque el mensaje actual sea ambiguo.
```

### Implementación

```python
async def detect_intent(message: str, history: list[dict]) -> str:
    prompt = load_prompt("intent_detection.md")
    
    messages = [{"role": "system", "content": prompt}]
    
    # Incluir últimos 4 mensajes de historial para contexto de continuación
    for msg in history[-4:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": message})
    
    client = get_llm_client()
    response = await client.chat(messages)
    
    intent = response.content.strip().lower()
    valid = {"faq", "agendar_cita", "modificar_cita", "cancelar_cita", "derivar_humano", "otro"}
    return intent if intent in valid else "otro"
```

---

## 3. LLAMADA 2: GENERATE_RESPONSE

### Prompt (`prompts/response_generation.md`)

```markdown
Eres el asistente virtual de una clínica de fisioterapia. Respondes por WhatsApp.

## Reglas de comportamiento
- Amable, profesional, conciso. Siempre en español. Tutea al paciente.
- Máximo 3-4 frases por mensaje. Usa ✅ para confirmaciones, ❌ para cancelaciones.
- Responde directamente a lo que el paciente pide. No fuerces un flujo rígido.
- Si el paciente saluda y pide algo, responde a lo que pide.
- Si solo saluda, saluda brevemente y pregunta en qué puedes ayudar.

## Nombre del paciente
- Solo pide el nombre cuando sea NECESARIO: para agendar o cancelar/modificar.
- Si ya tienes el nombre (aparece en el contexto), NO lo vuelvas a pedir.
- Si el paciente da su nombre en el mensaje, extráelo en "nombre_detectado".

## Agendar cita
- Los huecos disponibles están en el contexto (campo "free_slots").
- NO inventes horarios. Solo ofrece los que aparecen en free_slots.
- Necesitas: nombre, servicio, fecha y hora.
- SIEMPRE pide confirmación explícita antes de devolver un action de tipo "create".
- Repite todos los datos al confirmar: servicio, fecha, hora, nombre.
- Solo incluye action cuando el paciente confirme ("sí", "vale", "ok", "confirmo").

## Cancelar/modificar
- La cita existente está en el contexto (campo "appointment").
- Si no se encontró cita (appointment es null), díselo al paciente.
- Pide confirmación antes de devolver action de tipo "cancel" o "modify".

## Derivar a humano
- Devuelve action tipo "derivar" directamente.
- Confirma al paciente que se ha notificado a la clínica.

## Límites
- NUNCA des diagnósticos ni recomendaciones de tratamiento.
- NUNCA inventes servicios, precios, horarios o disponibilidad.
- Si no sabes algo, di que lo consulte con la clínica.

## RGPD
- Si es_primera_interaccion es true, incluye al final del mensaje:
  "Al continuar, aceptas que procesemos tus datos para gestionar tu cita."
- Solo en el primer mensaje. No repetir.

## Formato de respuesta
Responde SIEMPRE en JSON válido con esta estructura exacta:
{
  "message": "texto para enviar al paciente por WhatsApp",
  "action": null | {
    "type": "create" | "modify" | "cancel" | "derivar",
    "datetime": "YYYY-MM-DDTHH:MM",
    "duration": 60,
    "client_name": "nombre",
    "client_phone": "teléfono",
    "service": "nombre del servicio",
    "event_id": "id del evento (solo para modify/cancel)",
    "new_datetime": "YYYY-MM-DDTHH:MM (solo para modify)",
    "motivo": "razón (solo para derivar)"
  },
  "nombre_detectado": null | "nombre que dijo el paciente"
}

Incluye SOLO los campos relevantes en action según el tipo.
Si no hay acción que ejecutar, action debe ser null.
```

### Implementación

```python
async def generate_response(
    message: str,
    intent: str,
    context: dict,
    history: list[dict],
) -> dict:
    prompt_template = load_prompt("response_generation.md")
    
    # Construir system prompt con contexto
    system_content = f"""{prompt_template}

---

## Información del negocio
{context["business_info"]}

---

## Contexto actual
- Intención detectada: {intent}
- Fecha y hora actual: {context["current_datetime"]}
- Nombre del paciente: {context.get("nombre_paciente") or "Desconocido"}
- Es primera interacción: {context.get("es_primera_interaccion", False)}
"""
    
    if context.get("free_slots"):
        system_content += f"\n## Huecos disponibles\n{json.dumps(context['free_slots'], indent=2)}\n"
    
    if context.get("appointment"):
        system_content += f"\n## Cita existente del paciente\n{json.dumps(context['appointment'], indent=2)}\n"
    
    messages = [{"role": "system", "content": system_content}]
    
    # Historial completo (20 mensajes)
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": message})
    
    client = get_llm_client()
    response = await client.chat(messages, json_mode=True)
    
    return json.loads(response.content)
```

---

## 4. WRAPPER LLM (llm_client.py)

### OpenAI (GPT-4o-mini)

```python
class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
    
    async def chat(self, messages: list[dict], json_mode: bool = False) -> LLMResponse:
        kwargs = {"model": self._model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        
        response = await self._client.chat.completions.create(**kwargs)
        
        return LLMResponse(
            content=response.choices[0].message.content,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
        )
```

### Gemini (2.5 Flash)

```python
class GeminiClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model
    
    async def chat(self, messages: list[dict], json_mode: bool = False) -> LLMResponse:
        # Convertir formato OpenAI → formato Gemini
        system_instruction = None
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        
        config = {}
        if json_mode:
            config["response_mime_type"] = "application/json"
        if system_instruction:
            config["system_instruction"] = system_instruction
        
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )
        
        return LLMResponse(
            content=response.text,
            usage={
                "input_tokens": response.usage_metadata.prompt_token_count,
                "output_tokens": response.usage_metadata.candidates_token_count,
            }
        )
```

### JSON mode

Ambos providers soportan JSON mode:
- OpenAI: `response_format={"type": "json_object"}`
- Gemini: `response_mime_type="application/json"`

El wrapper abstrae esto con el parámetro `json_mode: bool`.
Se usa en `generate_response()` (que necesita JSON) pero NO en `detect_intent()` (que devuelve texto plano).

---

## 5. SAFETY NET — CONFIRMACIÓN EN CÓDIGO

El prompt instruye al LLM a solo incluir `action` cuando el paciente confirme.
El código lo valida como red de seguridad adicional.

```python
CONFIRMATION_WORDS = {
    "sí", "si", "confirmo", "vale", "ok", "adelante",
    "perfecto", "correcto", "confirmar", "claro", "venga", "dale"
}

NEGATION_WORDS = {
    "no", "cancelar", "espera", "para", "cambiar", "anular", "mejor no"
}

def user_confirmed(last_user_message: str) -> bool:
    words = set(last_user_message.lower().split())
    has_confirm = bool(words & CONFIRMATION_WORDS)
    has_negation = bool(words & NEGATION_WORDS)
    return has_confirm and not has_negation
```

### En agent.py

```python
action = response.get("action")
if action and action["type"] in ("create", "modify", "cancel"):
    if not user_confirmed(message_text):
        # El LLM no debería haber incluido action, pero por seguridad:
        logger.warning("safety_net_triggered", action=action["type"])
        await send_text(tenant_id, wa_phone, response["message"])
        return  # enviar el mensaje pero NO ejecutar la acción
    
    # Ejecutar acción
    await execute_action(action, tenant_id, wa_phone)
```

---

## 6. FLUJO COMPLETO DEL ORQUESTADOR (agent.py)

```python
async def handle_message(tenant_id, wa_phone, message_text, wa_message_id, db):
    # 1. Obtener o crear conversación
    conversation = await get_or_create_conversation(tenant_id, wa_phone, db)
    
    # 2. Si INACTIVA (despedida) o expirada (>24h) → reactivar
    if conversation.estado == ConversationState.INACTIVA.value or expired(conversation):
        await reactivate_conversation(conversation, db)
    
    # 3. Cargar historial
    history = await get_history(tenant_id, wa_phone)
    
    # 4. Detectar intención (llamada 1 al LLM)
    intent = await detect_intent(message_text, history)
    
    # 5. Preparar contexto según intención
    context = {
        "business_info": load_prompt("negocio.md"),
        "current_datetime": now_madrid().strftime("%A %d de %B de %Y, %H:%M"),
        "nombre_paciente": conversation.nombre_paciente,
        "es_primera_interaccion": len(history) == 0,
    }
    
    if intent == "agendar_cita":
        context["free_slots"] = await get_free_slots(tenant_id)
    elif intent in ("cancelar_cita", "modificar_cita"):
        context["appointment"] = await get_appointment_by_phone(tenant_id, wa_phone)
    
    # 6. Generar respuesta (llamada 2 al LLM)
    response = await generate_response(message_text, intent, context, history)
    
    # 7. Guardar nombre si se detectó
    if response.get("nombre_detectado") and not conversation.nombre_paciente:
        conversation.nombre_paciente = response["nombre_detectado"]
    
    # 8. Ejecutar acción si existe (con safety net)
    action = response.get("action")
    if action:
        if action["type"] in ("create", "modify", "cancel"):
            if user_confirmed(message_text):
                await execute_action(action, tenant_id, wa_phone)
            else:
                logger.warning("safety_net_triggered", action=action["type"])
        elif action["type"] == "derivar":
            await send_notification_email(
                tenant_id, conversation.nombre_paciente, wa_phone, action.get("motivo", "")
            )
        elif action["type"] == "despedida":
            await deactivate_conversation(conversation, db)
    
    # 9. Persistir mensajes (PG primero, Redis después)
    await append_message(tenant_id, wa_phone, "user", message_text, intent=intent)
    await append_message(tenant_id, wa_phone, "assistant", response["message"],
                        action=action["type"] if action else None)
    
    # 10. Enviar respuesta por WhatsApp
    await send_text(tenant_id, wa_phone, response["message"])
    
    # 11. Actualizar timestamp
    conversation.ultimo_mensaje_at = now_madrid()
    await db.commit()
```

---

## 7. HISTORIAL DE MENSAJES

### Redis: ventana de 20 mensajes
```python
# Clave: conversation:{tenant_id}:{wa_phone}
# Valor: JSON array de {role, content}
# TTL: 24 horas

async def get_history(tenant_id: UUID, wa_phone: str, max_messages: int = 20) -> list[dict]:
    redis = await get_redis()
    key = f"conversation:{tenant_id}:{wa_phone}"
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)[-max_messages:]
    # Fallback: reconstruir desde PG
    messages = await fetch_recent_from_pg(tenant_id, wa_phone, max_messages)
    history = [{"role": m.role, "content": m.content} for m in messages]
    await redis.set(key, json.dumps(history), ex=86400)
    return history
```

### Nota sobre qué se guarda en el historial
En el historial se guarda el `response["message"]` (texto para el paciente), NO el JSON completo.
Esto es lo que ve el LLM en siguientes turnos — el texto natural, no datos internos.

---

## 8. MANEJO DE ERRORES

```python
# Error en detect_intent → asumir "faq" como fallback seguro
try:
    intent = await detect_intent(message_text, history)
except Exception as e:
    logger.error("detect_intent_error", error=str(e))
    intent = "faq"

# Error en generate_response → mensaje fallback + derivar
try:
    response = await generate_response(...)
except Exception as e:
    logger.error("generate_response_error", error=str(e))
    await send_text(tenant_id, wa_phone, FALLBACK_MSG)
    await send_notification_email(tenant_id, None, wa_phone, "Error técnico LLM")
    return

# Error en execute_action → informar + derivar
try:
    await execute_action(action, ...)
except Exception as e:
    logger.error("action_error", action=action["type"], error=str(e))
    await send_text(tenant_id, wa_phone, "Disculpa, ha habido un problema. He avisado a la clínica.")
    await send_notification_email(tenant_id, None, wa_phone, f"Error en {action['type']}")
    return

FALLBACK_MSG = (
    "Disculpa, ha habido un problema técnico. "
    "He avisado a la clínica para que te contacten lo antes posible."
)
```

---

## 9. REGLAS TRANSVERSALES

1. **Expiración/Despedida**: >24h sin actividad o acción "despedida" → estado INACTIVA. Siguiente mensaje → reactivar (historial limpio, nombre conservado)
2. **Mensajes no-texto**: "Solo puedo leer mensajes de texto" — sin llamar al LLM
3. **Error de sistema**: fallback + derivar a humano automáticamente
4. **Deduplicación**: wa_message_id duplicado en BD → ignorar
5. **Longitud**: truncar mensajes > 1000 chars antes de enviar al LLM
6. **Nombre**: guardar en conversations.nombre_paciente. Inyectar en contexto de generate_response
7. **El LLM nunca ve datos técnicos**: no event_ids, no tokens, no errores internos
