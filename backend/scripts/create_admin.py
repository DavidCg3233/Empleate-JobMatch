"""Crea la cuenta de administrador (no hay registro público para este rol).

Ejecutar desde backend/ con el entorno virtual activo:
    python -m scripts.create_admin admin@empleate.co

La contraseña se pide en la terminal (no queda en el historial). Si el correo ya es de un administrador,
se le cambia la contraseña y se desbloquea (sirve también para recuperar el acceso).
"""
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registra todas las tablas)
from app.core.security import hash_password
from app.database import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.schemas.auth_schema import validate_password_rules
from app.services import audit_service


def create_or_update_admin(db: Session, email: str, password: str) -> str:
    """Devuelve "creado" o "actualizado". Lanza ValueError si los datos no sirven."""
    email = str(TypeAdapter(EmailStr).validate_python(email.strip())).lower()
    validate_password_rules(password)

    role = db.scalar(select(Role).where(Role.name == "administrador"))
    if role is None:
        role = Role(name="administrador")
        db.add(role)
        db.flush()

    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.role_id != role.id:
        raise ValueError(f"El correo {email} ya pertenece a una cuenta de {user.role.name}. Usa otro correo.")

    if user is None:
        user = User(role_id=role.id, email=email, password_hash=hash_password(password), is_active=True)
        db.add(user)
        db.flush()
        result = "creado"
    else:
        user.password_hash = hash_password(password)
        user.is_active = True
        user.failed_attempts = 0
        user.locked_until = None
        result = "actualizado"
    audit_service.record(db, f"administrador_{result}", None, "user", user.id)
    db.commit()
    return result


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m scripts.create_admin correo@dominio.com")
        sys.exit(1)
    email = sys.argv[1]
    password = getpass.getpass("Contraseña (mínimo 8 caracteres, con letras y números): ")
    if password != getpass.getpass("Repite la contraseña: "):
        print("Las contraseñas no coinciden.")
        sys.exit(1)
    try:
        with SessionLocal() as db:
            result = create_or_update_admin(db, email, password)
    except ValidationError:
        print("El correo no es válido.")
        sys.exit(1)
    except ValueError as exc:
        print(exc)
        sys.exit(1)
    print(f"Administrador {result}: {email.strip().lower()}. Ya puedes iniciar sesión en la página de login.")


if __name__ == "__main__":
    main()
