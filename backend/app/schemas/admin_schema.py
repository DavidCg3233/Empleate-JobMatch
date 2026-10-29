"""Esquemas del panel de administrador: /api/admin/..."""
from datetime import datetime

from pydantic import BaseModel


# ---------------- Resumen ----------------
class DayCount(BaseModel):
    date: str  # AAAA-MM-DD
    count: int


class ActivityOut(BaseModel):
    id: int
    action: str
    user_email: str | None
    user_role: str | None
    entity_type: str | None
    entity_id: int | None
    details: dict | None
    created_at: datetime


class AdminStatsOut(BaseModel):
    total_applicants: int
    total_companies: int
    total_admins: int
    inactive_users: int
    locked_users: int
    new_users_7d: int
    total_jobs: int
    active_jobs: int
    disabled_jobs: int
    total_matches: int
    new_matches_7d: int
    total_applicant_swipes: int
    total_company_swipes: int
    ai_analyses: int
    ai_embeddings: int
    signups_by_day: list[DayCount]
    recent_activity: list[ActivityOut]


# ---------------- Usuarios ----------------
class AdminUserOut(BaseModel):
    id: int
    email: str
    role: str
    display_name: str
    is_active: bool
    is_locked: bool
    last_login_at: datetime | None
    created_at: datetime
    entity_id: int | None  # id del aspirante o de la empresa
    detail: str | None     # cargo buscado (aspirante) o NIT (empresa)


class AdminUserPage(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    pages: int


class UserStatusIn(BaseModel):
    is_active: bool


# ---------------- Vacantes ----------------
class AdminJobOut(BaseModel):
    id: int
    title: str
    company_name: str
    company_active: bool
    status: str
    is_enabled: bool
    modality: str
    city: str | None
    closes_at: str | None
    created_at: datetime
    likes: int
    matches: int


class AdminJobPage(BaseModel):
    items: list[AdminJobOut]
    total: int
    page: int
    pages: int


class JobEnabledIn(BaseModel):
    is_enabled: bool


# ---------------- Matches ----------------
class AdminMatchOut(BaseModel):
    id: int
    matched_at: datetime
    is_active: bool
    job_id: int
    job_title: str
    company_name: str
    applicant_name: str
    applicant_email: str


class AdminMatchPage(BaseModel):
    items: list[AdminMatchOut]
    total: int
    page: int
    pages: int


# ---------------- Bitácora ----------------
class AdminActivityPage(BaseModel):
    items: list[ActivityOut]
    total: int
    page: int
    pages: int
    actions: list[str]  # acciones disponibles para el filtro
