"""Servicio LLM: deteccion de intencion y generacion de respuesta."""

import json
from pathlib import Path

import structlog

from app.services.llm_client import get_llm_client

logger = structlog.get_logger()

# --- Cache de prompts en memoria ---
_prompt_cache: dict[str, str] = {}

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

VALID_INTENTS = {
    "faq",
    "agendar_cita",
    "modificar_cita",
    "cancelar_cita",
    "derivar_humano",
    "otro",
}

MAX_MESSAGE_LENGTH = 1000


def load_prompt(filename: str) -> str:
    """Lee archivo .md de prompts/ y cachea en memoria."""
    if filename not in _prompt_cache:
        path = PROMPTS_DIR / filename
        _prompt_cache[filename] = path.read_text(encoding="utf-8")
        logger.debug("prompt_loaded", filename=filename)
    return _prompt_cache[filename]


def _truncate(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> str:
    """Trunca texto si excede max_length."""
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


async def detect_intent(message: str, history: list[dict]) -> str:
    """Clasifica la intencion del mensaje del paciente.

    Args:
        message: Texto del paciente.
        history: Ultimos mensajes de la conversacion.

    Returns:
        Una de: "faq", "agendar_cita", "modificar_cita",
        "cancelar_cita", "derivar_humano", "otro".
    """
    prompt = load_prompt("intent_detection.md")

    messages = [{"role": "system", "content": prompt}]

    for msg in history[-4:]:
        messages.append({
            "role": msg["role"],
            "content": _truncate(msg["content"]),
        })

    messages.append({"role": "user", "content": _truncate(message)})

    client = get_llm_client()
    response = await client.chat(messages)

    intent = response.content.strip().lower()
    logger.info(
        "intent_detected",
        intent=intent,
        tokens_in=response.usage.get("input_tokens"),
        tokens_out=response.usage.get("output_tokens"),
    )

    return intent if intent in VALID_INTENTS else "otro"


async def generate_response(
    message: str,
    intent: str,
    context: dict,
    history: list[dict],
) -> dict:
    """Genera respuesta + accion opcional en formato JSON.

    Args:
        message: Texto del paciente.
        intent: Intencion detectada.
        context: Dict con business_info, current_datetime,
                 nombre_paciente, es_primera_interaccion, free_slots,
                 appointment.
        history: Historial completo de la conversacion (hasta 20 msgs).

    Returns:
        Dict con keys: "message", "action", "nombre_detectado".
    """
    prompt_template = load_prompt("response_generation.md")

    system_content = f"""{prompt_template}

---

## Informacion del negocio
{context["business_info"]}

---

## Contexto actual
- Intencion detectada: {intent}
- Fecha y hora actual: {context["current_datetime"]}
- Nombre del paciente: {context.get("nombre_paciente") or "Desconocido"}
- Es primera interaccion: {context.get("es_primera_interaccion", False)}
"""

    if context.get("free_slots"):
        system_content += (
            f"\n## Huecos disponibles\n"
            f"{json.dumps(context['free_slots'], indent=2, ensure_ascii=False)}\n"
        )

    if context.get("appointment"):
        system_content += (
            f"\n## Cita existente del paciente\n"
            f"{json.dumps(context['appointment'], indent=2, ensure_ascii=False)}\n"
        )

    messages = [{"role": "system", "content": system_content}]

    for msg in history:
        messages.append({
            "role": msg["role"],
            "content": _truncate(msg["content"]),
        })

    messages.append({"role": "user", "content": _truncate(message)})

    client = get_llm_client()
    response = await client.chat(messages, json_mode=True)

    logger.info(
        "response_generated",
        intent=intent,
        tokens_in=response.usage.get("input_tokens"),
        tokens_out=response.usage.get("output_tokens"),
    )

    return json.loads(response.content)
