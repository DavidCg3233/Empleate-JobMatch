"""Perfil del aspirante: ver y editar sus datos, y subir (o reemplazar) su hoja de vida."""
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import api_error
from app.models.applicant import Applicant
from app.models.applicant_profile import (
    ApplicantEducation,
    ApplicantExperience,
    ApplicantLanguage,
    ApplicantSkill,
)
from app.models.catalogs import Skill
from app.models.city import City
from app.models.user import User
from app.schemas.profile_schema import ApplicantProfileUpdate
from app.services import cv_parser_service, storage_service
from app.services.auth_service import _ensure_catalog_ids, _save_applicant_profile
from app.utils.file_validators import validate_cv


def _get_applicant(db: Session, user: User) -> Applicant:
    applicant = db.scalar(select(Applicant).where(Applicant.user_id == user.id))
    if applicant is None:
        raise api_error(404, "No encontramos tu perfil de aspirante.")
    return applicant


def _cv_info(applicant: Applicant) -> dict | None:
    if not applicant.cv_path:
        return None
    return {"original_name": applicant.cv_original_name or "hoja_de_vida", "uploaded_at": applicant.cv_parsed_at}


def get_profile(db: Session, user: User) -> dict:
    a = _get_applicant(db, user)
    experiences = db.scalars(
        select(ApplicantExperience).where(ApplicantExperience.applicant_id == a.id)
        .order_by(ApplicantExperience.is_current.desc(), ApplicantExperience.start_date.desc())
    ).all()
    educations = db.scalars(
        select(ApplicantEducation).where(ApplicantEducation.applicant_id == a.id).order_by(ApplicantEducation.id)
    ).all()
    skills = db.scalars(
        select(Skill.name).join(ApplicantSkill, ApplicantSkill.skill_id == Skill.id)
        .where(ApplicantSkill.applicant_id == a.id).order_by(Skill.name)
    ).all()
    languages = db.scalars(select(ApplicantLanguage).where(ApplicantLanguage.applicant_id == a.id)).all()
    return {
        "id": a.id,
        "account_email": user.email,
        "first_name": a.first_name,
        "last_name": a.last_name,
        "phone": a.phone,
        "city_id": a.city_id,
        "desired_position": a.desired_position,
        "summary": a.summary,
        "search_status": a.search_status,
        "desired_salary_min": float(a.desired_salary_min) if a.desired_salary_min is not None else None,
        "desired_modality": a.desired_modality,
        "willing_to_relocate": bool(a.willing_to_relocate),
        "profile_completed": bool(a.profile_completed),
        "experiences": [
            {"company_name": e.company_name, "position": e.position, "start_date": e.start_date,
             "end_date": e.end_date, "is_current": e.is_current, "description": e.description}
            for e in experiences
        ],
        "educations": [
            {"education_level_id": e.education_level_id, "institution": e.institution, "degree": e.degree,
             "field_of_study": e.field_of_study, "start_date": e.start_date, "end_date": e.end_date}
            for e in educations
        ],
        "skills": list(skills),
        "languages": [{"language_id": lg.language_id, "proficiency": lg.proficiency} for lg in languages],
        "cv": _cv_info(a),
    }


def update_profile(db: Session, user: User, data: ApplicantProfileUpdate) -> dict:
    a = _get_applicant(db, user)
    if data.city_id is not None and db.get(City, data.city_id) is None:
        raise api_error(400, "La ciudad seleccionada no existe.")
    _ensure_catalog_ids(db, data)

    for field in ("first_name", "last_name", "phone", "city_id", "desired_position", "summary",
                  "search_status", "desired_salary_min", "desired_modality", "willing_to_relocate"):
        setattr(a, field, getattr(data, field))
    a.profile_completed = bool(data.desired_position and data.skills and (data.experiences or data.educations))

    # Las listas se reemplazan completas por lo que la persona dejó en el formulario
    for model in (ApplicantExperience, ApplicantEducation, ApplicantSkill, ApplicantLanguage):
        db.execute(delete(model).where(model.applicant_id == a.id))
    _save_applicant_profile(db, a.id, data)
    db.commit()
    return get_profile(db, user)


def upload_cv(db: Session, user: User, filename: str | None, content: bytes) -> dict:
    """Guarda la nueva hoja de vida (reemplaza la anterior) y devuelve los datos leídos.
    El perfil NO se cambia aquí: la persona revisa los datos y decide si los usa."""
    a = _get_applicant(db, user)
    ext = validate_cv(filename, content)
    try:
        text = cv_parser_service.extract_text(content, ext)
    except cv_parser_service.CVReadError as exc:
        raise api_error(422, str(exc))
    data, source = cv_parser_service.parse_cv(db, text)

    old_path = a.cv_path
    a.cv_path = storage_service.save_cv(content, ext)
    a.cv_original_name = (filename or f"hoja_de_vida{ext}")[:255]
    a.cv_text = text
    a.cv_parsed_at = datetime.now()
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage_service.delete_upload(a.cv_path)
        raise
    if old_path and old_path != a.cv_path:
        storage_service.delete_upload(old_path)
    return {"cv": _cv_info(a), "source": source, "data": data}


def get_cv_file(db: Session, user: User) -> tuple[Path, str]:
    a = _get_applicant(db, user)
    path = storage_service.resolve_upload(a.cv_path)
    if path is None:
        raise api_error(404, "Aún no has subido tu hoja de vida.")
    name = a.cv_original_name or f"hoja_de_vida{path.suffix}"
    if not name.lower().endswith(path.suffix.lower()):
        name += path.suffix
    return path, name
