"""Lógica de autenticación: registro (aspirante / empresa), inicio de sesión,
lectura de hoja de vida y recuperación de contraseña."""
import hashlib
import logging
import math
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.applicant import Applicant
from app.models.applicant_profile import (
    ApplicantEducation,
    ApplicantExperience,
    ApplicantLanguage,
    ApplicantSkill,
)
from app.models.catalogs import EducationLevel, Language
from app.models.city import City
from app.models.company import Company
from app.models.industry import Industry
from app.models.password_reset import PasswordReset
from app.models.role import Role
from app.models.user import User
from app.schemas.auth_schema import RegisterApplicantRequest, RegisterCompanyRequest
from app.services import audit_service, cv_parser_service, email_service, storage_service
from app.services.skill_service import get_or_create_skill_id
from app.utils.file_validators import validate_cv

logger = logging.getLogger("empleate.auth")


def _error(status_code: int, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"message": message, **extra})


def _session_payload(user_id: int, role_name: str, email: str) -> dict:
    """Respuesta que recibe el frontend al iniciar sesión o registrarse."""
    return {
        "access_token": create_access_token(user_id, role_name),
        "token_type": "bearer",
        "role": role_name,
        "user_id": user_id,
        "email": email,
    }


# =====================================================================
# REGISTRO
# =====================================================================
def _get_role_id(db: Session, role_name: str) -> int:
    role_id = db.scalar(select(Role.id).where(Role.name == role_name))
    if role_id is None:
        raise _error(500, f"Falta el rol '{role_name}' en la base de datos. Ejecuta jobmatch_schema.sql.")
    return role_id


def _ensure_email_available(db: Session, email: str) -> None:
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise _error(409, "Ya existe una cuenta con este correo.")


def _ensure_city_exists(db: Session, city_id: int | None) -> None:
    if city_id is not None and db.get(City, city_id) is None:
        raise _error(400, "La ciudad seleccionada no existe.")


def _ensure_industry_exists(db: Session, industry_id: int) -> None:
    if db.get(Industry, industry_id) is None:
        raise _error(400, "El sector seleccionado no existe.")


def _ensure_catalog_ids(db: Session, data: RegisterApplicantRequest) -> None:
    """Valida que los niveles educativos e idiomas enviados existan."""
    level_ids = {e.education_level_id for e in data.educations}
    if level_ids and len(set(db.scalars(select(EducationLevel.id).where(EducationLevel.id.in_(level_ids))))) != len(level_ids):
        raise _error(400, "Uno de los niveles educativos seleccionados no existe.")
    language_ids = [lg.language_id for lg in data.languages]
    if len(language_ids) != len(set(language_ids)):
        raise _error(400, "Hay idiomas repetidos.")
    if language_ids and len(set(db.scalars(select(Language.id).where(Language.id.in_(language_ids))))) != len(language_ids):
        raise _error(400, "Uno de los idiomas seleccionados no existe.")


def _save_applicant_profile(db: Session, applicant_id: int, data: RegisterApplicantRequest) -> None:
    """Guarda experiencia, educación, habilidades e idiomas (autocompletados desde el CV)."""
    for exp in data.experiences:
        db.add(ApplicantExperience(applicant_id=applicant_id, **exp.model_dump()))
    for edu in data.educations:
        db.add(ApplicantEducation(applicant_id=applicant_id, **edu.model_dump()))

    seen: set[int] = set()
    for name in data.skills:
        skill_id = get_or_create_skill_id(db, name)
        if skill_id not in seen:  # "Python" y "python" cuentan como la misma
            seen.add(skill_id)
            db.add(ApplicantSkill(applicant_id=applicant_id, skill_id=skill_id))

    for lang in data.languages:
        db.add(ApplicantLanguage(applicant_id=applicant_id, **lang.model_dump()))


def register_applicant(db: Session, data: RegisterApplicantRequest) -> dict:
    email = data.email.strip().lower()

    _ensure_email_available(db, email)
    _ensure_city_exists(db, data.city_id)
    _ensure_catalog_ids(db, data)
    role_id = _get_role_id(db, "aspirante")

    cv_meta = None
    if data.cv_upload_id:
        cv_meta = storage_service.load_temp_cv(data.cv_upload_id)
        if cv_meta is None:
            raise _error(400, "La hoja de vida que subiste ya no está disponible. Súbela de nuevo.")

    try:
        user = User(role_id=role_id, email=email, password_hash=hash_password(data.password))
        db.add(user)
        db.flush()  # obtiene user.id sin cerrar la transacción
        user_id = user.id

        applicant = Applicant(
            user_id=user_id,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            city_id=data.city_id,
            desired_position=data.desired_position,
            summary=data.summary,
            profile_completed=bool(
                data.desired_position and data.skills and (data.experiences or data.educations)
            ),
        )
        if cv_meta:
            applicant.cv_path = f"cvs/{data.cv_upload_id}{cv_meta['ext']}"
            applicant.cv_original_name = cv_meta["original_name"]
            applicant.cv_text = cv_meta["text"]
            applicant.cv_parsed_at = datetime.now()
        db.add(applicant)
        db.flush()

        _save_applicant_profile(db, applicant.id, data)
        audit_service.record(db, "registro", user_id, "aspirante", applicant.id)
        db.commit()  # usuario + perfil + CV se guardan juntos o no se guarda nada
    except IntegrityError:
        db.rollback()
        raise _error(409, "Ya existe una cuenta con este correo.")

    if cv_meta:
        try:
            storage_service.promote_temp_cv(data.cv_upload_id)
        except OSError:
            logger.exception("No se pudo mover la hoja de vida %s", data.cv_upload_id)

    return _session_payload(user_id, "aspirante", email)


# =====================================================================
# HOJA DE VIDA: subir y autocompletar el registro
# =====================================================================
def parse_cv_upload(db: Session, filename: str | None, content: bytes) -> dict:
    ext = validate_cv(filename, content)
    try:
        text = cv_parser_service.extract_text(content, ext)
    except cv_parser_service.CVReadError as exc:
        raise _error(422, str(exc))

    data, source = cv_parser_service.parse_cv(db, text)
    upload_id = storage_service.save_temp_cv(content, ext, filename or f"hoja_de_vida{ext}", text)
    return {
        "cv_upload_id": upload_id,
        "original_name": filename or f"hoja_de_vida{ext}",
        "source": source,
        "data": data,
    }


def register_company(db: Session, data: RegisterCompanyRequest) -> dict:
    email = data.email.strip().lower()

    _ensure_email_available(db, email)
    if db.scalar(select(Company.id).where(Company.tax_id == data.tax_id)) is not None:
        raise _error(409, "Ya existe una empresa registrada con ese NIT.")
    _ensure_city_exists(db, data.city_id)
    _ensure_industry_exists(db, data.industry_id)
    role_id = _get_role_id(db, "empresa")

    try:
        user = User(role_id=role_id, email=email, password_hash=hash_password(data.password))
        db.add(user)
        db.flush()
        user_id = user.id

        db.add(
            Company(
                user_id=user_id,
                name=data.name,
                tax_id=data.tax_id,
                industry_id=data.industry_id,
                size=data.size,
                description=data.description,
                city_id=data.city_id,
                address=data.address,
                website=data.website,
                contact_name=data.contact_name,
                contact_phone=data.contact_phone,
                contact_email=(data.contact_email or email).lower(),
            )
        )
        audit_service.record(db, "registro", user_id, "empresa", details={"nombre": data.name})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _error(409, "Ya existe una cuenta o una empresa con esos datos (correo o NIT).")

    return _session_payload(user_id, "empresa", email)


# =====================================================================
# LOGIN (máximo 3 intentos y bloqueo temporal)
# =====================================================================
def login(db: Session, email: str, password: str) -> dict:
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))

    # Mismo mensaje si el correo no existe (no revelar qué correos están registrados)
    if user is None:
        raise _error(401, "Correo o contraseña incorrectos.")

    if not user.is_active:
        raise _error(403, "Tu cuenta está desactivada. Contacta al administrador.")

    now = datetime.now()

    # ¿Sigue bloqueada?
    if user.locked_until and user.locked_until > now:
        minutes = math.ceil((user.locked_until - now).total_seconds() / 60)
        raise _error(423, f"Cuenta bloqueada temporalmente. Intenta de nuevo en {minutes} minuto(s).")

    # El bloqueo ya venció: reiniciar contador
    if user.locked_until and user.locked_until <= now:
        user.failed_attempts = 0
        user.locked_until = None

    # Contraseña incorrecta
    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        attempts = user.failed_attempts

        if attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOCK_MINUTES)
            audit_service.record(db, "cuenta_bloqueada", user.id, "user", user.id)
            db.commit()
            raise _error(
                423,
                f"Superaste los {settings.MAX_LOGIN_ATTEMPTS} intentos. "
                f"Tu cuenta quedó bloqueada por {settings.LOCK_MINUTES} minutos.",
            )

        db.commit()
        remaining = settings.MAX_LOGIN_ATTEMPTS - attempts
        raise _error(401, "Correo o contraseña incorrectos.", remaining_attempts=remaining)

    # Login correcto
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    role_name = user.role.name
    user_id = user.id
    user_email = user.email
    audit_service.record(db, "inicio_sesion", user_id)
    db.commit()

    return _session_payload(user_id, role_name, user_email)


# =====================================================================
# RECUPERACIÓN DE CONTRASEÑA
# =====================================================================
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(db: Session, email: str) -> tuple[str, str] | None:
    """Crea un token de recuperación. Devuelve (correo, enlace) o None si el correo no existe.
    El controlador SIEMPRE responde el mismo mensaje, exista o no la cuenta."""
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        return None

    now = datetime.now()
    # Invalida los enlaces anteriores que no se usaron: solo vale el más reciente
    for old in db.scalars(
        select(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
    ):
        old.used_at = now

    token = secrets.token_urlsafe(32)  # el token real solo viaja en el correo
    db.add(
        PasswordReset(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=now + timedelta(minutes=settings.RESET_TOKEN_MINUTES),
        )
    )
    db.commit()

    link = f"{settings.FRONTEND_URL.rstrip('/')}/pages/auth/reset_password.html?token={token}"
    return user.email, link


def send_reset_email(email: str, link: str) -> None:
    email_service.send_password_reset(email, link, settings.RESET_TOKEN_MINUTES)


def _get_valid_reset(db: Session, token: str) -> PasswordReset:
    reset = db.scalar(select(PasswordReset).where(PasswordReset.token_hash == _hash_token(token)))
    if reset is None or reset.used_at is not None:
        raise _error(400, "El enlace no es válido o ya fue usado. Solicita uno nuevo.")
    if reset.expires_at < datetime.now():
        raise _error(400, "El enlace venció. Solicita uno nuevo.")
    return reset


def validate_reset_token(db: Session, token: str) -> None:
    _get_valid_reset(db, token)


def reset_password(db: Session, token: str, new_password: str) -> None:
    reset = _get_valid_reset(db, token)
    user = db.get(User, reset.user_id)
    if user is None or not user.is_active:
        raise _error(400, "La cuenta no está disponible.")

    user.password_hash = hash_password(new_password)
    user.failed_attempts = 0     # si estaba bloqueada por intentos, queda desbloqueada
    user.locked_until = None
    reset.used_at = datetime.now()
    audit_service.record(db, "contrasena_restablecida", user.id, "user", user.id)
    db.commit()


# =====================================================================
# USUARIO ACTUAL
# =====================================================================
def get_me(db: Session, user: User) -> dict:
    role = user.role.name
    if role == "aspirante":
        a = db.scalar(select(Applicant).where(Applicant.user_id == user.id))
        name = f"{a.first_name} {a.last_name}" if a else user.email
    elif role == "empresa":
        c = db.scalar(select(Company).where(Company.user_id == user.id))
        name = c.name if c else user.email
    else:
        name = "Administrador"
    return {"user_id": user.id, "email": user.email, "role": role, "display_name": name}


# =====================================================================
# CAMBIAR CONTRASEÑA (con la sesión iniciada)
# =====================================================================
def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise _error(400, "La contraseña actual no es correcta.")
    if verify_password(new_password, user.password_hash):
        raise _error(400, "La nueva contraseña debe ser diferente a la actual.")
    user.password_hash = hash_password(new_password)
    audit_service.record(db, "contrasena_cambiada", user.id, "user", user.id)
    db.commit()
