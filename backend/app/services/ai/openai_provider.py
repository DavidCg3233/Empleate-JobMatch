"""Proveedor de IA: OpenAI (respuestas en JSON y embeddings). Documentación: https://platform.openai.com/docs"""
import httpx

from app.config import settings
from app.services.ai.base import AIError, AIProvider

CHAT_URL = "https://api.openai.com/v1/chat/completions"
EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class OpenAIProvider(AIProvider):
    name = "openai"
    supports_embeddings = True

    def __init__(self) -> None:
        self.model = settings.OPENAI_MODEL
        self.embedding_model = settings.OPENAI_EMBEDDING_MODEL

    def _post(self, url: str, payload: dict) -> dict:
        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json=payload,
                timeout=settings.AI_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise AIError(f"No se pudo conectar con OpenAI: {exc}") from exc
        if response.status_code != 200:
            # No se incluye la clave ni el texto enviado: solo el código y el mensaje de OpenAI
            raise AIError(f"OpenAI respondió {response.status_code}: {response.text[:300]}")
        try:
            return response.json()
        except ValueError as exc:
            raise AIError("OpenAI devolvió una respuesta que no es JSON.") from exc

    def _complete(self, system: str, user: str, max_tokens: int) -> str:
        data = self._post(CHAT_URL, {
            "model": self.model,
            "max_completion_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        })
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as exc:
            raise AIError("OpenAI no devolvió ninguna respuesta.") from exc
        if choice.get("finish_reason") == "length":
            raise AIError("La respuesta de OpenAI quedó incompleta.")
        return choice.get("message", {}).get("content") or ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = self._post(EMBEDDINGS_URL, {"model": self.embedding_model, "input": texts})
        try:
            rows = sorted(data["data"], key=lambda item: item["index"])
            vectors = [row["embedding"] for row in rows]
        except (KeyError, TypeError) as exc:
            raise AIError("OpenAI devolvió embeddings con un formato inesperado.") from exc
        if len(vectors) != len(texts):
            raise AIError("OpenAI no devolvió un vector por cada texto.")
        return vectors
