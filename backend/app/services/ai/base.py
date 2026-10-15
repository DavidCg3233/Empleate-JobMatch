"""Interfaz común para cualquier proveedor de IA.

El resto del proyecto solo usa get_ai_provider() y .complete_json(...): así se puede
cambiar de Claude a OpenAI (o a otro) tocando únicamente el archivo .env.
"""
import json
import re
from abc import ABC, abstractmethod

from app.config import settings


class AIError(Exception):
    """La IA no respondió o respondió algo que no se pudo interpretar."""


class AIProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def _complete(self, system: str, user: str, max_tokens: int) -> str:
        """Envía el mensaje y devuelve el texto de la respuesta."""

    def complete_json(self, system: str, user: str, max_tokens: int = 4000) -> dict:
        """Pide una respuesta y la convierte en diccionario (la IA debe responder JSON)."""
        text = self._complete(system, user, max_tokens)
        return parse_json(text)


def parse_json(text: str) -> dict:
    """Extrae el objeto JSON aunque venga dentro de ```json ... ``` o con texto alrededor."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIError("La IA no devolvió un JSON válido.") from exc
    if not isinstance(data, dict):
        raise AIError("La IA no devolvió un objeto JSON.")
    return data


def get_ai_provider() -> AIProvider | None:
    """Devuelve el proveedor configurado en .env, o None si no hay IA disponible."""
    provider = settings.AI_PROVIDER.strip().lower()

    if provider == "claude" and settings.ANTHROPIC_API_KEY:
        from app.services.ai.claude_provider import ClaudeProvider

        return ClaudeProvider()

    if provider == "openai" and settings.OPENAI_API_KEY:
        from app.services.ai.openai_provider import OpenAIProvider

        return OpenAIProvider()

    return None
