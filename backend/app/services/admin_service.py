"""Panel de administrador: indicadores, usuarios, vacantes, matches y bitácora.

Los conteos se hacen con el ORM (y no con la vista v_admin_stats de MySQL) para que también
funcionen en las pruebas con SQLite.
"""
import math
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import api_error
from app.models.applicant import Applicant
from app.models.audit_log import AuditLog
from app.models.city import City
from app.models.company import Company
from app.models.job import Job
from app.models.match import Match
from app.models.match_score import ApplicantEmbedding, JobEmbedding, MatchScore
from app.models.role import Role
from app.models.swipe import ApplicantSwipe, CompanySwipe
from app.models.user import User
from app.services import audit_service

PAGE_SIZE = 20


def _count(db: Session, stmt) -> int:
    return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def _paginate(db: Session, stmt, page: int) -> tuple[list, int, int, int]:
    """Devuelve (filas, total, página, páginas). Si la página pedida no existe, se usa la última."""
    total = _count(db, stmt)
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(max(1, page), pages)
    rows = db.execute(stmt.limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE)).all()
    return rows, total, page, pages


def _like(q: str) -> str:
    return f"%{q.strip()}%"


# =====================================================================
# Resumen
# =====================================================================
def _activity_rows(db: Session, stmt) -> list[dict]:
    return [
        {
            "id": log.id, "action": log.action, "user_email": email, "user_role": role,
            "entity_type": log.entity_type, "entity_id": log.entity_id, "details": log.details,
            "created_at": log.created_at,
        }
        for log, email, role in db.execute(stmt)
    ]


def _activity_stmt():
    return (
        select(AuditLog, User.email, Role.name)
        .outerjoin(User, User.id == AuditLog.user_id)
        .outerjoin(Role, Role.id == User.role_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )


def _users_by_role(db: Session) -> dict[str, int]:
    return dict(db.execute(select(Role.name, func.count(User.id)).join(User, User.role_id == Role.id).group_by(Role.name)).all())


def get_stats(db: Session) -> dict:
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    by_role = _users_by_role(db)

    # Registros por día de los últimos 14 días (aspirantes y empresas)
    start = date.today() - timedelta(days=13)
    created = db.scalars(
        select(User.created_at)
        .join(Role, Role.id == User.role_id)
        .where(User.created_at >= datetime.combine(start, datetime.min.time()), Role.name != "administrador")
    ).all()
    per_day = {start + timedelta(days=i): 0 for i in range(14)}
    for value in created:
        if value is not None and value.date() in per_day:
            per_day[value.date()] += 1

    scalar = lambda stmt: db.scalar(stmt) or 0  # noqa: E731
    return {
        "total_applicants": by_role.get("aspirante", 0),
        "total_companies": by_role.get("empresa", 0),
        "total_admins": by_role.get("administrador", 0),
        "inactive_users": scalar(select(func.count(User.id)).where(User.is_active.is_(False))),
        "locked_users": scalar(select(func.count(User.id)).where(User.locked_until > now)),
        "new_users_7d": scalar(
            select(func.count(User.id)).join(Role, Role.id == User.role_id)
            .where(User.created_at >= week_ago, Role.name != "administrador")
        ),
        "total_jobs": scalar(select(func.count(Job.id))),
        "active_jobs": scalar(select(func.count(Job.id)).where(Job.status == "activa", Job.is_enabled.is_(True))),
        "disabled_jobs": scalar(select(func.count(Job.id)).where(Job.is_enabled.is_(False))),
        "total_matches": scalar(select(func.count(Match.id)).where(Match.is_active.is_(True))),
        "new_matches_7d": scalar(
            select(func.count(Match.id)).where(Match.is_active.is_(True), Match.matched_at >= week_ago)
        ),
        "total_applicant_swipes": scalar(select(func.count(ApplicantSwipe.id))),
        "total_company_swipes": scalar(select(func.count(CompanySwipe.id))),
        "ai_analyses": scalar(select(func.count(MatchScore.id)).where(MatchScore.explanation.is_not(None))),
        "ai_embeddings": scalar(select(func.count(ApplicantEmbedding.applicant_id)))
        + scalar(select(func.count(JobEmbedding.job_id))),
        "signups_by_day": [{"date": d.isoformat(), "count": c} for d, c in per_day.items()],
        "recent_activity": _activity_rows(db, _activity_stmt().limit(8)),
    }


# =====================================================================
# Usuarios
# =====================================================================
def list_users(db: Session, q: str | None, role: str | None, status: str | None, page: int) -> dict:
    now = datetime.now()
    stmt = (
        select(User, Role.name, Applicant, Company)
        .join(Role, Role.id == User.role_id)
        .outerjoin(Applicant, Applicant.user_id == User.id)
        .outerjoin(Company, Company.user_id == User.id)
        .order_by(User.created_at.desc(), User.id.desc())
    )
    if role:
        stmt = stmt.where(Role.name == role)
    if status == "activo":
        stmt = stmt.where(User.is_active.is_(True))
    elif status == "inactivo":
        stmt = stmt.where(User.is_active.is_(False))
    elif status == "bloqueado":
        stmt = stmt.where(User.locked_until > now)
    if q and q.strip():
        term = _like(q)
        stmt = stmt.where(or_(
            User.email.ilike(term),
            Company.name.ilike(term),
            Company.tax_id.ilike(term),
            (Applicant.first_name + " " + Applicant.last_name).ilike(term),
        ))

    rows, total, page, pages = _paginate(db, stmt, page)
    items = []
    for user, role_name, applicant, company in rows:
        if applicant is not None:
            name, entity_id, detail = f"{applicant.first_name} {applicant.last_name}", applicant.id, applicant.desired_position
        elif company is not None:
            name, entity_id, detail = company.name, company.id, f"NIT {company.tax_id}"
        else:
            name, entity_id, detail = "Administrador", None, None
        items.append({
            "id": user.id, "email": user.email, "role": role_name, "display_name": name,
            "is_active": user.is_active, "is_locked": bool(user.locked_until and user.locked_until > now),
            "last_login_at": user.last_login_at, "created_at": user.created_at,
            "entity_id": entity_id, "detail": detail,
        })
    return {"items": items, "total": total, "page": page, "pages": pages}


def _managed_user(db: Session, admin: User, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise api_error(404, "El usuario no existe.")
    if user.id == admin.id:
        raise api_error(409, "No puedes cambiar el estado de tu propia cuenta.")
    if user.role.name == "administrador":
        raise api_error(409, "Las cuentas de administrador no se gestionan desde el panel.")
    return user


def set_user_status(db: Session, admin: User, user_id: int, is_active: bool) -> None:
    user = _managed_user(db, admin, user_id)
    if user.is_active == is_active:
        return
    user.is_active = is_active
    audit_service.record(
        db, "usuario_activado" if is_active else "usuario_desactivado", admin.id, "user", user.id,
        {"correo": user.email, "rol": user.role.name},
    )
    db.commit()


def unlock_user(db: Session, admin: User, user_id: int) -> None:
    user = _managed_user(db, admin, user_id)
    user.failed_attempts = 0
    user.locked_until = None
    audit_service.record(db, "usuario_desbloqueado", admin.id, "user", user.id, {"correo": user.email})
    db.commit()


# =====================================================================
# Vacantes
# =====================================================================
def list_jobs(db: Session, q: str | None, status: str | None, enabled: bool | None, page: int) -> dict:
    stmt = (
        select(Job, Company.name, User.is_active, City.name)
        .join(Company, Company.id == Job.company_id)
        .join(User, User.id == Company.user_id)
        .outerjoin(City, City.id == Job.city_id)
        .order_by(Job.created_at.desc(), Job.id.desc())
    )
    if status:
        stmt = stmt.where(Job.status == status)
    if enabled is not None:
        stmt = stmt.where(Job.is_enabled.is_(enabled))
    if q and q.strip():
        term = _like(q)
        stmt = stmt.where(or_(Job.title.ilike(term), Company.name.ilike(term)))

    rows, total, page, pages = _paginate(db, stmt, page)
    ids = [job.id for job, *_ in rows]
    likes = dict(db.execute(
        select(ApplicantSwipe.job_id, func.count()).where(ApplicantSwipe.job_id.in_(ids), ApplicantSwipe.action == "like")
        .group_by(ApplicantSwipe.job_id)
    ).all()) if ids else {}
    matches = dict(db.execute(
        select(Match.job_id, func.count()).where(Match.job_id.in_(ids), Match.is_active.is_(True)).group_by(Match.job_id)
    ).all()) if ids else {}

    items = [
        {
            "id": job.id, "title": job.title, "company_name": company_name, "company_active": company_active,
            "status": job.status, "is_enabled": job.is_enabled, "modality": job.modality,
            "city": city_name, "closes_at": job.closes_at.isoformat() if job.closes_at else None,
            "created_at": job.created_at, "likes": likes.get(job.id, 0), "matches": matches.get(job.id, 0),
        }
        for job, company_name, company_active, city_name in rows
    ]
    return {"items": items, "total": total, "page": page, "pages": pages}


def set_job_enabled(db: Session, admin: User, job_id: int, is_enabled: bool) -> None:
    job = db.get(Job, job_id)
    if job is None:
        raise api_error(404, "La vacante no existe.")
    if job.is_enabled == is_enabled:
        return
    job.is_enabled = is_enabled
    audit_service.record(
        db, "vacante_habilitada" if is_enabled else "vacante_deshabilitada", admin.id, "vacante", job.id,
        {"titulo": job.title},
    )
    db.commit()


# =====================================================================
# Matches
# =====================================================================
def list_matches(db: Session, q: str | None, page: int) -> dict:
    stmt = (
        select(Match, Job.title, Company.name, Applicant.first_name, Applicant.last_name, User.email)
        .join(Job, Job.id == Match.job_id)
        .join(Company, Company.id == Job.company_id)
        .join(Applicant, Applicant.id == Match.applicant_id)
        .join(User, User.id == Applicant.user_id)
        .order_by(Match.matched_at.desc(), Match.id.desc())
    )
    if q and q.strip():
        term = _like(q)
        stmt = stmt.where(or_(
            Job.title.ilike(term), Company.name.ilike(term), User.email.ilike(term),
            (Applicant.first_name + " " + Applicant.last_name).ilike(term),
        ))
    rows, total, page, pages = _paginate(db, stmt, page)
    items = [
        {
            "id": match.id, "matched_at": match.matched_at, "is_active": match.is_active,
            "job_id": match.job_id, "job_title": title, "company_name": company,
            "applicant_name": f"{first} {last}", "applicant_email": email,
        }
        for match, title, company, first, last, email in rows
    ]
    return {"items": items, "total": total, "page": page, "pages": pages}


# =====================================================================
# Bitácora
# =====================================================================
def list_activity(db: Session, action: str | None, page: int) -> dict:
    stmt = _activity_stmt()
    if action:
        stmt = stmt.where(AuditLog.action == action)
    total = _count(db, stmt)
    pages = max(1, math.ceil(total / PAGE_SIZE))
    page = min(max(1, page), pages)
    items = _activity_rows(db, stmt.limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE))
    actions = sorted(db.scalars(select(AuditLog.action).distinct()).all())
    return {"items": items, "total": total, "page": page, "pages": pages, "actions": actions}
