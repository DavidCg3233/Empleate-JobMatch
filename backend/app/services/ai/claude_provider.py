"""Proveedor de IA: Claude (Anthropic), con el SDK oficial `anthropic`.
Documentación: https://platform.claude.com/docs"""
import anthropic

from app.config import settings
from app.services.ai.base import AIError, AIProvider


class ClaudeProvider(AIProvider):
    name = "claude"

    def __init__(self) -> None:
        self.model = settings.ANTHROPIC_MODEL
        self.client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY, timeout=settings.AI_TIMEOUT_SECONDS, max_retries=1
        )

    def _complete(self, system: str, user: str, max_tokens: int) -> str:
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                # El razonamiento del modelo también cuenta en max_tokens: se deja margen
                max_tokens=max(max_tokens, 16000),
                # Extraer datos de un CV es una tarea sencilla: poco esfuerzo = más rápido y barato
                output_config={"effort": "low"},
                system=system,
                messages=[{"role": "user", "content": user}],
                # Si el modelo rechaza la petición, la API la reintenta con otro modelo
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIConnectionError as exc:
            raise AIError(f"No se pudo conectar con Claude: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise AIError(f"Claude respondió {exc.status_code}: {exc.message}") from exc

        if response.stop_reason == "refusal":
            raise AIError("Claude no procesó esta hoja de vida.")
        if response.stop_reason == "max_tokens":
            raise AIError("La respuesta de Claude quedó incompleta.")
        return "".join(block.text for block in response.content if block.type == "text")
