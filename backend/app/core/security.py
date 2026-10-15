"""Contraseñas (bcrypt) y tokens de sesión (JWT)."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


# ---------------- Contraseñas ----------------
def hash_password(password: str) -> str:
    """Convierte la contraseña en un hash irreversible para guardarlo en la BD."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Compara la contraseña escrita con el hash guardado."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:  # hash con formato inválido o contraseña de más de 72 bytes
        return False


# ---------------- Tokens JWT ----------------
def create_access_token(user_id: int, role: str) -> str:
    """Crea el 'carné' que el frontend envía en cada petición (Authorization: Bearer ...)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Devuelve el contenido del token. Lanza jwt.PyJWTError si es inválido o venció."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
