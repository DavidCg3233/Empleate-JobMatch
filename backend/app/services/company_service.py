"""Módulo de empresa: perfil y gestión de vacantes (crear, ver, editar, cambiar estado, eliminar)."""
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import api_error
from app.models.catalogs import EducationLevel
from app.models.city import City
from app.models.company import Company
from app.models.industry import Industry
from app.models.job import ContractType, Job, JobSkill
from app.models.match import Match
from app.models.swipe import ApplicantSwipe, CompanySwipe
from app.models.user import User
from app.schemas.company_schema import CompanyProfileUpdate, JobCreate, JobIn
from app.services import audit_service
from app.services.skill_service import get_or_create_skill_id


# =====================================================================
# Utilidades
# =====================================================================
def get_company(db: Session, user: User) -> Company:
    company = db.scalar(select(Company).where(Company.user_id == user.id))
    if company is None:
        raise api_error(404, "No encontramos el perfil de tu empresa.")
    return company


def get_owned_job(db: Session, company: Company, job_id: int) -> Job:
    """La vacante debe existir y ser de esta empresa (si es de otra, se responde igual que si no existiera)."""
    job = db.get(Job, job_id)
    if job is None or job.company_id != company.id:
        raise api_error(404, "La vacante no existe.")
    return job


def _city_name(db: Session, city_id: int | None) -> str | None:
    return db.scalar(select(City.name).where(City.id == city_id)) if city_id else None


# =====================================================================
# Perfil
# =====================================================================
def _profile_out(db: Session, company: Company, user: User) -> dict:
    return {
        "id": company.id,
        "account_email": user.email,
        "name": company.name,
        "tax_id": company.tax_id,
        "industry_id": company.industry_id,
        "industry": db.scalar(select(Industry.name).where(Industry.id == company.industry_id)),
        "size": company.size,
        "city_id": company.city_id,
        "city": _city_name(db, company.city_id),
        "description": company.description,
        "address": company.address,
        "website": company.website,
        "contact_name": company.contact_name,
        "contact_phone": company.contact_phone,
        "contact_email": company.contact_email,
        "created_at": company.created_at,
    }


def get_profile(db: Session, user: User) -> dict:
    return _profile_out(db, get_company(db, user), user)


def update_profile(db: Session, user: User, data: CompanyProfileUpdate) -> dict:
    company = get_company(db, user)
    if db.get(Industry, data.industry_id) is None:
        raise api_error(400, "El sector seleccionado no existe.")
    if db.get(City, data.city_id) is None:
        raise api_error(400, "La ciudad seleccionada no existe.")

    for field, value in data.model_dump().items():
        setattr(company, field, value)
    company.contact_email = data.contact_email.lower()
    db.commit()
    db.refresh(company)
    return _profile_out(db, company, user)


# =====================================================================
# Vacantes: lectura
# =====================================================================
def _job_stats(db: Session, job_ids: list[int]) -> dict[int, dict]:
    stats = {job_id: {"interested": 0, "pending": 0, "matches": 0, "touched": False} for job_id in job_ids}
    if not job_ids:
        return stats

    reviewed = (
        select(CompanySwipe.id)
        .where(CompanySwipe.job_id == ApplicantSwipe.job_id, CompanySwipe.applicant_id == ApplicantSwipe.applicant_id)
        .exists()
    )
    for job_id, total in db.execute(
        select(ApplicantSwipe.job_id, func.count(ApplicantSwipe.id))
        .where(ApplicantSwipe.job_id.in_(job_ids), ApplicantSwipe.action == "like")
        .group_by(ApplicantSwipe.job_id)
    ):
        stats[job_id]["interested"] = total

    for job_id, pending in db.execute(
        select(ApplicantSwipe.job_id, func.count(ApplicantSwipe.id))
        .where(ApplicantSwipe.job_id.in_(job_ids), ApplicantSwipe.action == "like", ~reviewed)
        .group_by(ApplicantSwipe.job_id)
    ):
        stats[job_id]["pending"] = pending

    for job_id, total in db.execute(
        select(Match.job_id, func.count(Match.id))
        .where(Match.job_id.in_(job_ids), Match.is_active.is_(True))
        .group_by(Match.job_id)
    ):
        stats[job_id]["matches"] = total

    # Vacantes con las que alguien ya interactuó (no se pueden eliminar)
    touched = set(db.scalars(select(ApplicantSwipe.job_id).where(ApplicantSwipe.job_id.in_(job_ids))))
    touched |= set(db.scalars(select(CompanySwipe.job_id).where(CompanySwipe.job_id.in_(job_ids))))
    touched |= set(db.scalars(select(Match.job_id).where(Match.job_id.in_(job_ids))))
    for job_id in touched:
        stats[job_id]["touched"] = True
    return stats


def _job_out(job: Job, city_names: dict[int, str], stats: dict) -> dict:
    today = date.today()
    is_expired = job.closes_at is not None and job.closes_at < today
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "requirements": job.requirements,
        "modality": job.modality,
        "city_id": job.city_id,
        "city": city_names.get(job.city_id),
        "contract_type_id": job.contract_type_id,
        "contract_type": job.contract_type.name,
        "min_education_id": job.min_education_id,
        "min_education": job.min_education.name if job.min_education else None,
        "min_experience_years": job.min_experience_years or 0,
        "salary_min": float(job.salary_min) if job.salary_min is not None else None,
        "salary_max": float(job.salary_max) if job.salary_max is not None else None,
        "currency": job.currency,
        "status": job.status,
        "is_enabled": job.is_enabled,
        "is_expired": is_expired,
        "is_visible": job.status == "activa" and job.is_enabled and not is_expired,
        "can_delete": not stats["touched"],
        "published_at": job.published_at,
        "closes_at": job.closes_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "skills": [
            {"name": js.skill.name, "is_required": js.is_required}
            for js in sorted(job.skills, key=lambda js: (not js.is_required, js.skill.name.lower()))
        ],
        "stats": {k: stats[k] for k in ("interested", "pending", "matches")},
    }


def _serialize_jobs(db: Session, jobs: list[Job]) -> list[dict]:
    stats = _job_stats(db, [j.id for j in jobs])
    city_ids = {j.city_id for j in jobs if j.city_id}
    city_names = dict(db.execute(select(City.id, City.name).where(City.id.in_(city_ids))).all()) if city_ids else {}
    return [_job_out(job, city_names, stats[job.id]) for job in jobs]


def list_jobs(db: Session, user: User) -> list[dict]:
    company = get_company(db, user)
    jobs = db.scalars(
        select(Job).where(Job.company_id == company.id).order_by(Job.created_at.desc(), Job.id.desc())
    ).unique().all()
    return _serialize_jobs(db, list(jobs))


def get_job(db: Session, user: User, job_id: int) -> dict:
    job = get_owned_job(db, get_company(db, user), job_id)
    return _serialize_jobs(db, [job])[0]


# =====================================================================
# Vacantes: crear / editar
# =====================================================================
def _check_catalogs(db: Session, data: JobIn) -> None:
    if data.city_id is not None and db.get(City, data.city_id) is None:
        raise api_error(400, "La ciudad seleccionada no existe.")
    if db.get(ContractType, data.contract_type_id) is None:
        raise api_error(400, "El tipo de contrato seleccionado no existe.")
    if data.min_education_id is not None and db.get(EducationLevel, data.min_education_id) is None:
        raise api_error(400, "El nivel educativo seleccionado no existe.")


def _apply_fields(job: Job, data: JobIn) -> None:
    for field in (
        "title", "description", "requirements", "modality", "city_id", "contract_type_id", "min_education_id",
        "min_experience_years", "salary_min", "salary_max", "currency", "closes_at",
    ):
        setattr(job, field, getattr(data, field))


def _sync_skills(db: Session, job: Job, data: JobIn) -> None:
    """Actualiza las habilidades sin borrar y volver a crear las que siguen (evita choques de llave)."""
    wanted: dict[int, bool] = {}
    for skill in data.skills:
        skill_id = get_or_create_skill_id(db, skill.name)
        wanted[skill_id] = wanted.get(skill_id, False) or skill.is_required

    for job_skill in list(job.skills):
        if job_skill.skill_id in wanted:
            job_skill.is_required = wanted.pop(job_skill.skill_id)
        else:
            job.skills.remove(job_skill)  # delete-orphan la borra de job_skills
    for skill_id, is_required in wanted.items():
        job.skills.append(JobSkill(skill_id=skill_id, is_required=is_required))


def create_job(db: Session, user: User, data: JobCreate) -> dict:
    company = get_company(db, user)
    _check_catalogs(db, data)

    job = Job(company_id=company.id, status=data.status, is_enabled=True)
    _apply_fields(job, data)
    if data.status == "activa":
        job.published_at = datetime.now()
    db.add(job)
    db.flush()
    _sync_skills(db, job, data)
    audit_service.record(db, "vacante_creada", user.id, "vacante", job.id, {"titulo": job.title})
    db.commit()
    return get_job(db, user, job.id)


def update_job(db: Session, user: User, job_id: int, data: JobIn) -> dict:
    job = get_owned_job(db, get_company(db, user), job_id)
    _check_catalogs(db, data)
    _apply_fields(job, data)
    _sync_skills(db, job, data)
    db.commit()
    return get_job(db, user, job.id)


# =====================================================================
# Vacantes: estado y eliminación
# =====================================================================
def change_status(db: Session, user: User, job_id: int, status: str) -> dict:
    job = get_owned_job(db, get_company(db, user), job_id)
    if status == job.status:
        return get_job(db, user, job.id)

    if status == "activa":
        if not job.is_enabled:
            raise api_error(409, "El administrador deshabilitó esta vacante. Contáctalo para reactivarla.")
        if job.closes_at is not None and job.closes_at < date.today():
            raise api_error(409, "La fecha de cierre ya pasó. Edita la vacante y cambia la fecha antes de publicarla.")
        if job.published_at is None:
            job.published_at = datetime.now()  # primera publicación

    audit_service.record(db, "vacante_estado", user.id, "vacante", job.id, {"de": job.status, "a": status})
    job.status = status
    db.commit()
    return get_job(db, user, job.id)


def delete_job(db: Session, user: User, job_id: int) -> None:
    job = get_owned_job(db, get_company(db, user), job_id)
    if _job_stats(db, [job.id])[job.id]["touched"]:
        raise api_error(
            409,
            "Esta vacante ya tiene aspirantes o matches, por eso no se puede eliminar. Puedes cerrarla.",
        )
    audit_service.record(db, "vacante_eliminada", user.id, "vacante", job.id, {"titulo": job.title})
    db.delete(job)
    db.commit()
