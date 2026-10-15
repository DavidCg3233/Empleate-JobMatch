"""Funciones de ayuda generales."""
import time
import unicodedata
from collections import defaultdict, deque

from fastapi import HTTPException, Request


def normalize_text(value: str) -> str:
    """'Educación Académica:' -> 'educacion academica'  (minúsculas, sin tildes ni signos al final)."""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return value.lower().strip().strip(":.-•*").strip()


class RateLimiter:
    """Límite simple en memoria: máximo `limit` peticiones por IP cada `window` segundos.
    Protege rutas públicas costosas (ej: la lectura de CV con IA)."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        ip = request.client.host if request.client else "desconocida"
        now = time.monotonic()
        hits = self._hits[ip]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            raise HTTPException(
                429, detail={"message": "Hiciste demasiados intentos. Espera unos minutos e inténtalo de nuevo."}
            )
        hits.append(now)
