"""Lado empresa del match: candidatos para una vacante, me interesa / no me interesa,
matches con datos de contacto y descarga de la hoja de vida."""
from pathlib import Path

from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import api_error
from app.models.applicant import Applicant
from app.models.applicant_profile import (
    ApplicantEducation,
    ApplicantExperience,
    ApplicantLanguage,
    ApplicantSkill,
)
from app.models.catalogs import EducationLevel, Language, Skill
from app.models.city import City
from app.models.job import Job
from app.models.match import Match
from app.models.swipe import ApplicantSwipe, CompanySwipe
from app.models.user import User
from app.services import storage_service
from app.services.company_service import get_company, get_owned_job
from app.services.matching_service import compute_score, load_applicant_contexts
from app.utils.helpers import normalize_text

FEED_SIZE = 20
OTHER_CANDIDATES = 300  # aspirantes que no han marcado la vacante y se puntúan para sugerirlos
PROFICIENCY_LABEL = {"basico": "Básico", "intermedio": "Intermedio", "avanzado": "Avanzado", "nativo": "Nativo"}


# =====================================================================
# Utilidades
# =====================================================================
def _reviewable_job(db: Session, user: User, job_id: int) -> Job:
    """Se pueden revisar candidatos de vacantes activas o pausadas (no cerradas ni deshabilitadas)."""
    job = get_owned_job(db, get_company(db, user), job_id)
    if job.status == "cerrada":
        raise api_error(409, "La vacante está cerrada. Reábrela para revisar candidatos.")
    if not job.is_enabled:
        raise api_error(409, "El administrador deshabilitó esta vacante.")
    return job


def _display_name(applicant: Applicant, full: bool) -> str:
    if full:
        return f"{applicant.first_name} {applicant.last_name}"
    # Antes del match se protege la identidad: "Laura G."
    return f"{applicant.first_name} {applicant.last_name.strip()[:1].upper()}."


def _serialize_candidates(
    db: Session,
    job: Job,
    applicants: list[Applicant],
    interested_ids: set[int],
    company_actions: dict[int, str],
    matched_ids: set[int],
) -> list[dict]:
    """Arma el perfil de varios aspirantes con pocas consultas (una por tipo de dato)."""
    ids = [a.id for a in applicants]
    if not ids:
        return []

    contexts = load_applicant_contexts(db, applicants)
    city_names = dict(db.execute(select(City.id, City.name)).all())
    job_skill_names = {normalize_text(js.skill.name) for js in job.skills}

    experiences: dict[int, list[dict]] = {i: [] for i in ids}
    for exp in db.scalars(
        select(ApplicantExperience)
        .where(ApplicantExperience.applicant_id.in_(ids))
        .order_by(ApplicantExperience.is_current.desc(), ApplicantExperience.start_date.desc())
    ):
        experiences[exp.applicant_id].append({
            "position": exp.position, "company_name": exp.company_name, "start_date": exp.start_date,
            "end_date": exp.end_date, "is_current": exp.is_current, "description": exp.description,
        })

    educations: dict[int, list[dict]] = {i: [] for i in ids}
    top_level: dict[int, tuple[int, str]] = {}
    for edu, level_name, rank in db.execute(
        select(ApplicantEducation, EducationLevel.name, EducationLevel.rank_order)
        .join(EducationLevel, EducationLevel.id == ApplicantEducation.education_level_id)
        .where(ApplicantEducation.applicant_id.in_(ids))
        .order_by(EducationLevel.rank_order.desc())
    ):
        educations[edu.applicant_id].append({
            "degree": edu.degree, "institution": edu.institution, "field_of_study": edu.field_of_study,
            "level": level_name, "start_date": edu.start_date, "end_date": edu.end_date,
        })
        if rank > top_level.get(edu.applicant_id, (0, ""))[0]:
            top_level[edu.applicant_id] = (rank, level_name)

    skills: dict[int, list[dict]] = {i: [] for i in ids}
    for applicant_id, name in db.execute(
        select(ApplicantSkill.applicant_id, Skill.name)
        .join(Skill, Skill.id == ApplicantSkill.skill_id)
        .where(ApplicantSkill.applicant_id.in_(ids))
        .order_by(Skill.name)
    ):
        skills[applicant_id].append({"name": name, "matched": normalize_text(name) in job_skill_names})

    languages: dict[int, list[dict]] = {i: [] for i in ids}
    for applicant_id, name, proficiency in db.execute(
        select(ApplicantLanguage.applicant_id, Language.name, ApplicantLanguage.proficiency)
        .join(Language, Language.id == ApplicantLanguage.language_id)
        .where(ApplicantLanguage.applicant_id.in_(ids))
        .order_by(Language.id)
    ):
        languages[applicant_id].append({"name": name, "proficiency": PROFICIENCY_LABEL.get(proficiency, proficiency)})

    result = []
    for a in applicants:
        ctx = contexts[a.id]
        score, reasons, _ = compute_score(ctx, job, audience="empresa")
        matched = a.id in matched_ids
        result.append({
            "applicant_id": a.id,
            "display_name": _display_name(a, full=matched),
            "city": city_names.get(a.city_id),
            "desired_position": a.desired_position,
            "summary": a.summary,
            "experience_years": ctx.experience_years,
            "education_level": top_level.get(a.id, (0, None))[1],
            "experiences": experiences[a.id],
            "educations": educations[a.id],
            # Primero las habilidades que pide la vacante
            "skills": sorted(skills[a.id], key=lambda s: not s["matched"]),
            "languages": languages[a.id],
            "willing_to_relocate": bool(a.willing_to_relocate),
            "desired_modality": a.desired_modality,
            "score": score,
            "score_reasons": reasons,
            "interested": a.id in interested_ids,
            "company_action": company_actions.get(a.id),
            "matched": matched,
        })
    return result


def _active_applicant(db: Session, applicant_id: int) -> Applicant:
    applicant = db.scalar(
        select(Applicant)
        .join(User, User.id == Applicant.user_id)
        .where(Applicant.id == applicant_id, User.is_active.is_(True))
    )
    if applicant is None:
        raise api_error(404, "Este aspirante ya no está disponible.")
    return applicant


# =====================================================================
# Candidatos para deslizar
# =====================================================================
def get_candidates(
    db: Session, user: User, job_id: int, only_interested: bool = False, exclude_ids: list[int] | None = None
) -> dict:
    """Primero los aspirantes a los que les interesó la vacante; luego (si se piden) otros perfiles
    que están buscando empleo, del más compatible al menos. Nunca se repite a alguien ya revisado."""
    job = _reviewable_job(db, user, job_id)

    liked_job = exists().where(
        ApplicantSwipe.applicant_id == Applicant.id, ApplicantSwipe.job_id == job.id, ApplicantSwipe.action == "like"
    )
    disliked_job = exists().where(
        ApplicantSwipe.applicant_id == Applicant.id, ApplicantSwipe.job_id == job.id, ApplicantSwipe.action == "dislike"
    )
    already_reviewed = exists().where(CompanySwipe.applicant_id == Applicant.id, CompanySwipe.job_id == job.id)

    base = (
        select(Applicant)
        .join(User, User.id == Applicant.user_id)
        .where(User.is_active.is_(True), ~already_reviewed, ~disliked_job)
    )
    if exclude_ids:
        base = base.where(Applicant.id.not_in(exclude_ids))

    interested = list(db.scalars(base.where(liked_job).order_by(Applicant.id)).all())
    others: list[Applicant] = []
    if not only_interested:
        others = list(db.scalars(
            base.where(~liked_job, Applicant.search_status == "buscando_empleo")
            .order_by(Applicant.updated_at.desc(), Applicant.id.desc())
            .limit(OTHER_CANDIDATES)
        ).all())

    interested_ids = {a.id for a in interested}
    items = _serialize_candidates(db, job, interested + others, interested_ids, {}, set())
    # Interesados primero; dentro de cada grupo, del más compatible al menos
    items.sort(key=lambda c: (not c["interested"], -c["score"]))
    return {"job_id": job.id, "job_title": job.title, "items": items[:FEED_SIZE]}


# =====================================================================
# Me interesa / No me interesa (empresa)
# =====================================================================
def swipe_candidate(db: Session, user: User, job_id: int, applicant_id: int, action: str) -> dict:
    job = _reviewable_job(db, user, job_id)
    applicant = _active_applicant(db, applicant_id)

    match = db.scalar(select(Match).where(Match.job_id == job.id, Match.applicant_id == applicant.id))
    if match is not None and match.is_active and action == "dislike":
        raise api_error(409, "Ya tienes un match con este aspirante para esta vacante.")

    swipe = db.scalar(
        select(CompanySwipe).where(CompanySwipe.job_id == job.id, CompanySwipe.applicant_id == applicant.id)
    )
    if swipe is None:
        db.add(CompanySwipe(job_id=job.id, applicant_id=applicant.id, action=action))
    else:
        swipe.action = action

    new_match = False
    if action == "like" and (match is None or not match.is_active):
        applicant_liked = db.scalar(
            select(ApplicantSwipe.id).where(
                ApplicantSwipe.job_id == job.id,
                ApplicantSwipe.applicant_id == applicant.id,
                ApplicantSwipe.action == "like",
            )
        )
        if applicant_liked is not None:
            if match is None:
                match = Match(job_id=job.id, applicant_id=applicant.id)
                db.add(match)
            else:
                match.is_active = True
            new_match = True

    try:
        db.commit()
    except IntegrityError:
        # Doble clic: otra petición igual guardó primero
        db.rollback()
        new_match = False

    return {
        "job_id": job.id,
        "applicant_id": applicant.id,
        "action": action,
        "matched": new_match,
        "match_id": match.id if new_match and match is not None else None,
    }


def undo_candidate_swipe(db: Session, user: User, job_id: int, applicant_id: int) -> None:
    job = _reviewable_job(db, user, job_id)
    swipe = db.scalar(
        select(CompanySwipe).where(CompanySwipe.job_id == job.id, CompanySwipe.applicant_id == applicant_id)
    )
    if swipe is None:
        raise api_error(404, "No hay ninguna decisión para deshacer con este aspirante.")
    has_match = db.scalar(
        select(Match.id).where(
            Match.job_id == job.id, Match.applicant_id == applicant_id, Match.is_active.is_(True)
        )
    )
    if has_match is not None:
        raise api_error(409, "No puedes deshacer un aspirante con el que ya tienes match.")
    db.delete(swipe)
    db.commit()


# =====================================================================
# Matches de la empresa
# =====================================================================
def get_company_matches(db: Session, user: User, job_id: int | None = None) -> list[dict]:
    company = get_company(db, user)
    stmt = (
        select(Match, Job, Applicant, User.email)
        .join(Job, Job.id == Match.job_id)
        .join(Applicant, Applicant.id == Match.applicant_id)
        .join(User, User.id == Applicant.user_id)
        .where(Job.company_id == company.id, Match.is_active.is_(True))
        .order_by(Match.matched_at.desc(), Match.id.desc())
    )
    if job_id is not None:
        get_owned_job(db, company, job_id)
        stmt = stmt.where(Job.id == job_id)
    rows = db.execute(stmt).unique().all()

    # Los perfiles se arman por vacante (la compatibilidad depende de cada una)
    by_job: dict[int, tuple[Job, list[Applicant]]] = {}
    for _, job, applicant, _ in rows:
        by_job.setdefault(job.id, (job, []))[1].append(applicant)
    profiles: dict[tuple[int, int], dict] = {}
    for job, applicants in by_job.values():
        ids = {a.id for a in applicants}
        for candidate in _serialize_candidates(db, job, applicants, ids, {i: "like" for i in ids}, ids):
            profiles[(job.id, candidate["applicant_id"])] = candidate

    return [
        {
            "match_id": match.id,
            "matched_at": match.matched_at,
            "job": {"id": job.id, "title": job.title, "status": job.status},
            "candidate": profiles[(job.id, applicant.id)],
            "contact": {
                "full_name": f"{applicant.first_name} {applicant.last_name}",
                "email": email,
                "phone": applicant.phone,
                "has_cv": bool(applicant.cv_path),
            },
        }
        for match, job, applicant, email in rows
    ]


def get_match_cv(db: Session, user: User, match_id: int) -> tuple[Path, str]:
    """Ruta del archivo de la hoja de vida y el nombre con que se descarga. Solo con match activo."""
    company = get_company(db, user)
    row = db.execute(
        select(Applicant)
        .join(Match, Match.applicant_id == Applicant.id)
        .join(Job, Job.id == Match.job_id)
        .where(Match.id == match_id, Match.is_active.is_(True), Job.company_id == company.id)
    ).scalar_one_or_none()
    if row is None:
        raise api_error(404, "El match no existe.")
    if not row.cv_path:
        raise api_error(404, "Este aspirante no subió hoja de vida.")

    path = storage_service.resolve_upload(row.cv_path)
    if path is None:
        raise api_error(404, "No encontramos el archivo de la hoja de vida.")

    ext = path.suffix.lower()
    name = row.cv_original_name or f"hoja_de_vida{ext}"
    if not name.lower().endswith(ext):
        name += ext
    return path, name
