"""Proveedor de IA: OpenAI. Documentación: https://platform.openai.com/docs"""
import httpx

from app.config import settings
from app.services.ai.base import AIError, AIProvider

API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self) -> None:
        self.model = settings.OPENAI_MODEL

    def _complete(self, system: str, user: str, max_tokens: int) -> str:
        try:
            response = httpx.post(
                API_URL,
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=settings.AI_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise AIError(f"No se pudo conectar con OpenAI: {exc}") from exc

        if response.status_code != 200:
            raise AIError(f"OpenAI respondió {response.status_code}: {response.text[:300]}")

        return response.json()["choices"][0]["message"]["content"] or ""
