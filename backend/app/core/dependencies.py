"""Protección de rutas: quién está logueado y qué rol tiene.

Uso en un controller:
    @router.get("/mis-vacantes")
    def mis_vacantes(user: User = Depends(require_role("empresa"))):
        ...
"""
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(401, detail={"message": "Debes iniciar sesión."})

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, detail={"message": "Tu sesión expiró. Inicia sesión de nuevo."})
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, detail={"message": "Sesión inválida."})

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, detail={"message": "La cuenta no existe o está desactivada."})
    return user


def require_role(*roles: str):
    """Deja pasar solo a usuarios con alguno de los roles indicados."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role.name not in roles:
            raise HTTPException(403, detail={"message": "No tienes permiso para esta acción."})
        return user

    return checker
