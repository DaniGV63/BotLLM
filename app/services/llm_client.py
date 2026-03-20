"""Wrapper LLM: interfaz comun para OpenAI y Gemini."""

from dataclasses import dataclass

import structlog

from app.core.config import settings

logger = structlog.get_logger()


@dataclass
class LLMResponse:
    """Respuesta normalizada de cualquier provider LLM."""

    content: str
    usage: dict  # {"input_tokens": int, "output_tokens": int}


class LLMClient:
    """Interfaz base para providers LLM."""

    async def chat(
        self, messages: list[dict], json_mode: bool = False
    ) -> LLMResponse:
        raise NotImplementedError


class OpenAIClient(LLMClient):
    """GPT-4o-mini via SDK oficial de OpenAI."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        logger.info("llm_client_initialized", provider="openai", model=model)

    async def chat(
        self, messages: list[dict], json_mode: bool = False
    ) -> LLMResponse:
        kwargs: dict = {"model": self._model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._client.chat.completions.create(**kwargs)

        return LLMResponse(
            content=response.choices[0].message.content,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
        )


class GeminiClient(LLMClient):
    """Gemini 2.5 Flash via SDK oficial de Google."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model
        logger.info("llm_client_initialized", provider="gemini", model=model)

    async def chat(
        self, messages: list[dict], json_mode: bool = False
    ) -> LLMResponse:
        system_instruction = None
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append(
                    {"role": role, "parts": [{"text": msg["content"]}]}
                )

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
            },
        )


# --- Singleton ---
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Devuelve singleton del cliente LLM. Lee LLM_PROVIDER de config."""
    global _client
    if _client is None:
        if settings.LLM_PROVIDER == "gemini":
            _client = GeminiClient(
                api_key=settings.GEMINI_API_KEY, model=settings.LLM_MODEL
            )
        else:
            _client = OpenAIClient(
                api_key=settings.OPENAI_API_KEY, model=settings.LLM_MODEL
            )
    return _client
