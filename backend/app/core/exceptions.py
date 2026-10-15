"""Errores de la API con un formato único: {"detail": {"message": "...", ...}}.

El frontend (assets/js/api/http.js) lee siempre detail.message.
"""
from fastapi import HTTPException


def api_error(status_code: int, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"message": message, **extra})
