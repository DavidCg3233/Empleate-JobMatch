"""Panel de administrador: /api/admin/..."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.admin_schema import (
    AdminActivityPage,
    AdminJobPage,
    AdminMatchPage,
    AdminStatsOut,
    AdminUserPage,
    JobEnabledIn,
    UserStatusIn,
)
from app.schemas.auth_schema import MessageResponse
from app.services import admin_service

router = APIRouter(prefix="/api/admin", tags=["Administrador"])
admin_only = require_role("administrador")


@router.get("/stats", response_model=AdminStatsOut)
def stats(_: User = Depends(admin_only), db: Session = Depends(get_db)):
    return admin_service.get_stats(db)


# ---------------- Usuarios ----------------
@router.get("/users", response_model=AdminUserPage)
def users(
    q: str | None = Query(None, max_length=100),
    role: Literal["aspirante", "empresa", "administrador"] | None = None,
    status: Literal["activo", "inactivo", "bloqueado"] | None = None,
    page: int = Query(1, ge=1, le=10_000),
    _: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return admin_service.list_users(db, q, role, status, page)


@router.patch("/users/{user_id}/status", response_model=MessageResponse)
def user_status(user_id: int, data: UserStatusIn, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Activa o desactiva una cuenta. Desactivada: no puede entrar y deja de aparecer en el emparejamiento."""
    admin_service.set_user_status(db, admin, user_id, data.is_active)
    return {"message": "Cuenta activada." if data.is_active else "Cuenta desactivada."}


@router.post("/users/{user_id}/unlock", response_model=MessageResponse)
def user_unlock(user_id: int, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Quita el bloqueo temporal por intentos fallidos de inicio de sesión."""
    admin_service.unlock_user(db, admin, user_id)
    return {"message": "Cuenta desbloqueada."}


# ---------------- Vacantes ----------------
@router.get("/jobs", response_model=AdminJobPage)
def jobs(
    q: str | None = Query(None, max_length=100),
    status: Literal["activa", "pausada", "cerrada"] | None = None,
    enabled: bool | None = None,
    page: int = Query(1, ge=1, le=10_000),
    _: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return admin_service.list_jobs(db, q, status, enabled, page)


@router.patch("/jobs/{job_id}/enabled", response_model=MessageResponse)
def job_enabled(job_id: int, data: JobEnabledIn, admin: User = Depends(admin_only), db: Session = Depends(get_db)):
    """Deshabilitar = la vacante deja de verse para los aspirantes y la empresa no la puede volver a publicar."""
    admin_service.set_job_enabled(db, admin, job_id, data.is_enabled)
    return {"message": "Vacante habilitada." if data.is_enabled else "Vacante deshabilitada."}


# ---------------- Matches y bitácora ----------------
@router.get("/matches", response_model=AdminMatchPage)
def matches(
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1, le=10_000),
    _: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return admin_service.list_matches(db, q, page)


@router.get("/activity", response_model=AdminActivityPage)
def activity(
    action: str | None = Query(None, max_length=60),
    page: int = Query(1, ge=1, le=10_000),
    _: User = Depends(admin_only),
    db: Session = Depends(get_db),
):
    return admin_service.list_activity(db, action, page)
