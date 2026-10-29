"""Rutas de autenticación: /api/auth/..."""
from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.applicant_schema import CvParseResponse
from app.schemas.auth_schema import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    MessageResponse,
    RegisterApplicantRequest,
    RegisterCompanyRequest,
    ResetPasswordRequest,
)
from app.services import account_service, auth_service
from app.utils.helpers import RateLimiter

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])

# Límites por IP para rutas públicas que cuestan (IA) o que se pueden abusar (correos)
cv_limiter = RateLimiter(limit=10, window_seconds=10 * 60)
forgot_limiter = RateLimiter(limit=5, window_seconds=15 * 60)


# ---------------- Login ----------------
@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(db, data.email, data.password)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Datos del usuario con sesión iniciada (sirve para validar el token)."""
    return auth_service.get_me(db, user)


# ---------------- Registro ----------------
@router.post("/cv/parse", response_model=CvParseResponse, dependencies=[Depends(cv_limiter)])
def parse_cv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Recibe la hoja de vida (PDF/DOCX) y devuelve los datos para autocompletar el registro.
    Es síncrona a propósito: FastAPI la ejecuta en otro hilo y la lectura del archivo
    o la espera a la IA no bloquean al resto de usuarios."""
    content = file.file.read(settings.MAX_CV_MB * 1024 * 1024 + 1)
    return auth_service.parse_cv_upload(db, file.filename, content)


@router.post("/register/applicant", response_model=LoginResponse, status_code=201)
def register_applicant(data: RegisterApplicantRequest, db: Session = Depends(get_db)):
    """Crea la cuenta de un aspirante (con su perfil y CV opcional) y devuelve la sesión."""
    return auth_service.register_applicant(db, data)


@router.post("/register/company", response_model=LoginResponse, status_code=201)
def register_company(data: RegisterCompanyRequest, db: Session = Depends(get_db)):
    """Crea la cuenta de una empresa con su perfil y devuelve la sesión."""
    return auth_service.register_company(db, data)


# ---------------- Recuperación de contraseña ----------------
@router.post("/forgot-password", response_model=MessageResponse, dependencies=[Depends(forgot_limiter)])
def forgot_password(data: ForgotPasswordRequest, background: BackgroundTasks, db: Session = Depends(get_db)):
    result = auth_service.request_password_reset(db, data.email)
    if result:
        background.add_task(auth_service.send_reset_email, *result)  # el correo sale sin hacer esperar
    # Mismo mensaje exista o no la cuenta: así nadie puede averiguar qué correos están registrados
    return {"message": "Si el correo está registrado, te enviamos un enlace para restablecer tu contraseña."}


@router.get("/reset-password/validate", response_model=MessageResponse)
def validate_reset_token(token: str = Query(min_length=20, max_length=200), db: Session = Depends(get_db)):
    auth_service.validate_reset_token(db, token)
    return {"message": "Enlace válido."}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    auth_service.reset_password(db, data.token, data.password)
    return {"message": "Tu contraseña se actualizó. Ya puedes iniciar sesión."}


@router.post("/change-password", response_model=MessageResponse)
def change_password(data: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cambia la contraseña de quien tiene la sesión iniciada (aspirante o empresa)."""
    auth_service.change_password(db, user, data.current_password, data.new_password)
    return {"message": "Tu contraseña se actualizó."}


@router.delete("/account", response_model=MessageResponse)
def delete_account(data: DeleteAccountRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Elimina la cuenta del aspirante o de la empresa y todos sus datos (pide la contraseña para confirmar)."""
    account_service.delete_account(db, user, data.password)
    return {"message": "Tu cuenta y tus datos se eliminaron."}
