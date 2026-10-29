"""Búsqueda de vacantes para el aspirante: tarjetas para deslizar, buscador con filtros,
detalle, likes / dislikes y matches."""
from datetime import date

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import api_error
from app.models.applicant import Applicant
from app.models.catalogs import Skill
from app.models.city import City, Department
from app.models.company import Company
from app.models.industry import Industry
from app.models.job import Job, JobSkill
from app.models.match import Match
from app.models.swipe import ApplicantSwipe, CompanySwipe
from app.models.user import User
from app.services import ai_matching_service, audit_service
from app.services.matching_service import ApplicantContext, compute_score, load_applicant_context

FEED_SIZE = 20
FEED_CANDIDATES = 300   # vacantes recientes que se puntúan para armar las tarjetas
SEARCH_LIMIT = 500      # máximo de resultados que se ordenan en una búsqueda


# =====================================================================
# Utilidades
# =====================================================================
def get_applicant(db: Session, user: User) -> Applicant:
    applicant = db.scalar(select(Applicant).where(Applicant.user_id == user.id))
    if applicant is None:
        raise api_error(404, "No encontramos tu perfil de aspirante.")
    return applicant


def _open_jobs_filter():
    """Condiciones de una vacante visible: activa, habilitada, sin vencer y de una empresa activa."""
    today = date.today()
    return and_(
        Job.status == "activa",
        Job.is_enabled.is_(True),
        or_(Job.closes_at.is_(None), Job.closes_at >= today),
        exists().where(
            Company.id == Job.company_id,
            User.id == Company.user_id,
            User.is_active.is_(True),
        ),
    )


def _is_open(job: Job, active_company_ids: set[int]) -> bool:
    return (
        job.status == "activa"
        and job.is_enabled
        and (job.closes_at is None or job.closes_at >= date.today())
        and job.company_id in active_company_ids
    )


class _Catalogs:
    """Nombres de ciudades y sectores (tablas pequeñas: se cargan una vez por petición)."""

    def __init__(self, db: Session) -> None:
        self.cities = {
            r.id: (r.name, r.department)
            for r in db.execute(
                select(City.id, City.name, Department.name.label("department"))
                .join(Department, City.department_id == Department.id)
            )
        }
        self.industries = dict(db.execute(select(Industry.id, Industry.name)).all())


def _serialize(
    job: Job,
    ctx: ApplicantContext,
    catalogs: _Catalogs,
    my_action: str | None,
    matched: bool,
    is_open: bool = True,
    semantic: float | None = None,  # afinidad de la IA (None = solo reglas)
) -> dict:
    result = compute_score(ctx, job, semantic=semantic)
    matched_skills = result.matched_skills
    city, department = catalogs.cities.get(job.city_id, (None, None))
    company = job.company
    skills = sorted(job.skills, key=lambda js: (not js.is_required, js.skill.name.lower()))
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "requirements": job.requirements,
        "company": {
            "id": company.id,
            "name": company.name,
            "industry": catalogs.industries.get(company.industry_id),
            "size": company.size,
            "city": catalogs.cities.get(company.city_id, (None, None))[0],
            "description": company.description,
            "website": company.website,
        },
        "city": city,
        "department": department,
        "modality": job.modality,
        "contract_type": job.contract_type.name,
        "min_education": job.min_education.name if job.min_education else None,
        "min_experience_years": job.min_experience_years or 0,
        "salary_min": float(job.salary_min) if job.salary_min is not None else None,
        "salary_max": float(job.salary_max) if job.salary_max is not None else None,
        "currency": job.currency,
        "published_at": job.published_at,
        "closes_at": job.closes_at,
        "is_open": is_open,
        "skills": [
            {"name": js.skill.name, "is_required": js.is_required, "matched": js.skill.name in matched_skills}
            for js in skills
        ],
        "score": result.score,
        "score_reasons": result.strengths,  # a favor
        "score_gaps": result.gaps,  # en contra
        "my_action": my_action,
        "matched": matched,
    }


def _swipe_map(db: Session, applicant_id: int, job_ids: list[int]) -> dict[int, str]:
    if not job_ids:
        return {}
    rows = db.execute(
        select(ApplicantSwipe.job_id, ApplicantSwipe.action)
        .where(ApplicantSwipe.applicant_id == applicant_id, ApplicantSwipe.job_id.in_(job_ids))
    )
    return dict(rows.all())


def _matched_ids(db: Session, applicant_id: int, job_ids: list[int]) -> set[int]:
    if not job_ids:
        return set()
    return set(
        db.scalars(
            select(Match.job_id).where(
                Match.applicant_id == applicant_id, Match.job_id.in_(job_ids), Match.is_active.is_(True)
            )
        )
    )


def _apply_filters(stmt, city_id: int | None, modality: str | None, contract_type_id: int | None):
    if modality:
        stmt = stmt.where(Job.modality == modality)
    if city_id:
        # Las vacantes remotas sirven desde cualquier ciudad
        stmt = stmt.where(or_(Job.city_id == city_id, Job.modality == "remoto"))
    if contract_type_id:
        stmt = stmt.where(Job.contract_type_id == contract_type_id)
    return stmt


# =====================================================================
# Tarjetas para deslizar (solo vacantes que aún no ha visto)
# =====================================================================
def get_feed(
    db: Session,
    user: User,
    city_id: int | None = None,
    modality: str | None = None,
    contract_type_id: int | None = None,
    exclude_ids: list[int] | None = None,
    min_score: int | None = None,
) -> dict:
    applicant = get_applicant(db, user)
    ctx = load_applicant_context(db, applicant)

    already_swiped = exists().where(
        ApplicantSwipe.applicant_id == applicant.id, ApplicantSwipe.job_id == Job.id
    )
    stmt = select(Job).where(_open_jobs_filter(), ~already_swiped)
    stmt = _apply_filters(stmt, city_id, modality, contract_type_id)
    if exclude_ids:  # tarjetas que el navegador ya tiene en pantalla
        stmt = stmt.where(Job.id.not_in(exclude_ids))
    jobs = db.scalars(
        stmt.order_by(Job.published_at.desc(), Job.id.desc()).limit(FEED_CANDIDATES)
    ).unique().all()

    catalogs = _Catalogs(db)
    semantic = ai_matching_service.semantic_for_applicant(db, applicant, list(jobs))
    items = [_serialize(job, ctx, catalogs, None, False, semantic=semantic.get(job.id)) for job in jobs]
    # Primero las más compatibles; a igual puntaje, las más recientes (ya vienen en ese orden)
    items.sort(key=lambda item: -item["score"])
    # Solo las recomendadas: se ocultan las de baja compatibilidad (y se informa cuántas quedaron fuera)
    hidden = 0
    if min_score:
        visible = [item for item in items if item["score"] >= min_score]
        hidden = len(items) - len(visible)
        items = visible
    return {"items": items[:FEED_SIZE], "hidden_count": hidden}


# =====================================================================
# Buscador con filtros
# =====================================================================
def search_jobs(
    db: Session,
    user: User,
    q: str | None = None,
    city_id: int | None = None,
    modality: str | None = None,
    contract_type_id: int | None = None,
    salary_min: float | None = None,
    sort: str = "relevancia",
    hide_discarded: bool = False,
    page: int = 1,
    page_size: int = 12,
    min_score: int | None = None,
) -> dict:
    applicant = get_applicant(db, user)
    ctx = load_applicant_context(db, applicant)

    stmt = select(Job).where(_open_jobs_filter())
    stmt = _apply_filters(stmt, city_id, modality, contract_type_id)

    # Cada palabra debe aparecer en el cargo, descripción, requisitos, empresa o habilidades
    for word in (q or "").split()[:8]:
        word = word.lower()
        stmt = stmt.where(
            or_(
                func.lower(Job.title).contains(word, autoescape=True),
                func.lower(Job.description).contains(word, autoescape=True),
                func.lower(func.coalesce(Job.requirements, "")).contains(word, autoescape=True),
                exists().where(
                    Company.id == Job.company_id, func.lower(Company.name).contains(word, autoescape=True)
                ),
                exists().where(
                    JobSkill.job_id == Job.id,
                    Skill.id == JobSkill.skill_id,
                    func.lower(Skill.name).contains(word, autoescape=True),
                ),
            )
        )

    if salary_min:
        stmt = stmt.where(func.coalesce(Job.salary_max, Job.salary_min) >= salary_min)

    if hide_discarded:
        stmt = stmt.where(
            ~exists().where(
                ApplicantSwipe.applicant_id == applicant.id,
                ApplicantSwipe.job_id == Job.id,
                ApplicantSwipe.action == "dislike",
            )
        )

    jobs = db.scalars(
        stmt.order_by(Job.published_at.desc(), Job.id.desc()).limit(SEARCH_LIMIT)
    ).unique().all()

    job_ids = [j.id for j in jobs]
    swipes = _swipe_map(db, applicant.id, job_ids)
    matched = _matched_ids(db, applicant.id, job_ids)
    catalogs = _Catalogs(db)
    semantic = ai_matching_service.semantic_for_applicant(db, applicant, list(jobs))
    items = [_serialize(j, ctx, catalogs, swipes.get(j.id), j.id in matched, semantic=semantic.get(j.id)) for j in jobs]
    if min_score:
        items = [item for item in items if item["score"] >= min_score]

    if sort == "relevancia":
        items.sort(key=lambda item: -item["score"])
    elif sort == "salario":
        items.sort(key=lambda item: -(item["salary_max"] or item["salary_min"] or 0))
    # "recientes": ya vienen ordenadas por fecha de publicación

    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "total": len(items),
        "page": page,
        "page_size": page_size,
        "has_more": start + page_size < len(items),
    }


# =====================================================================
# Detalle de una vacante
# =====================================================================
def _active_company_ids(db: Session, company_ids: set[int]) -> set[int]:
    if not company_ids:
        return set()
    return set(
        db.scalars(
            select(Company.id)
            .join(User, User.id == Company.user_id)
            .where(Company.id.in_(company_ids), User.is_active.is_(True))
        )
    )


def get_viewable_job(db: Session, applicant: Applicant, job_id: int) -> tuple[Job, str | None, bool]:
    """La vacante si el aspirante la puede ver: abierta, o cerrada pero ya marcada por él (ej: sus matches).
    Devuelve (vacante, su decisión, si está abierta)."""
    job = db.get(Job, job_id)
    if job is None:
        raise api_error(404, "La vacante no existe.")
    my_action = _swipe_map(db, applicant.id, [job.id]).get(job.id)
    is_open = _is_open(job, _active_company_ids(db, {job.company_id}))
    if not is_open and my_action is None:
        raise api_error(404, "Esta vacante ya no está disponible.")
    return job, my_action, is_open


def get_job_detail(db: Session, user: User, job_id: int) -> dict:
    applicant = get_applicant(db, user)
    job, my_action, is_open = get_viewable_job(db, applicant, job_id)
    is_matched = job.id in _matched_ids(db, applicant.id, [job.id])

    ctx = load_applicant_context(db, applicant)
    semantic = ai_matching_service.semantic_for_applicant(db, applicant, [job]).get(job.id)
    return _serialize(job, ctx, _Catalogs(db), my_action, is_matched, is_open, semantic=semantic)


# =====================================================================
# Me interesa / No me interesa
# =====================================================================
def swipe_job(db: Session, user: User, job_id: int, action: str) -> dict:
    applicant = get_applicant(db, user)
    job = db.scalar(select(Job).where(Job.id == job_id, _open_jobs_filter()))
    if job is None:
        raise api_error(404, "Esta vacante ya no está disponible.")

    match = db.scalar(select(Match).where(Match.job_id == job_id, Match.applicant_id == applicant.id))
    if match is not None and match.is_active and action == "dislike":
        raise api_error(409, "Ya tienes un match con esta vacante.")

    swipe = db.scalar(
        select(ApplicantSwipe).where(ApplicantSwipe.applicant_id == applicant.id, ApplicantSwipe.job_id == job_id)
    )
    if swipe is None:
        db.add(ApplicantSwipe(applicant_id=applicant.id, job_id=job_id, action=action))
    else:
        swipe.action = action  # desde el buscador se puede cambiar de opinión

    new_match = False
    if action == "like" and (match is None or not match.is_active):
        company_liked = db.scalar(
            select(CompanySwipe.id).where(
                CompanySwipe.job_id == job_id,
                CompanySwipe.applicant_id == applicant.id,
                CompanySwipe.action == "like",
            )
        )
        if company_liked is not None:
            if match is None:
                match = Match(job_id=job_id, applicant_id=applicant.id)
                db.add(match)
            else:
                match.is_active = True
            new_match = True
            audit_service.record(db, "match", user.id, "vacante", job_id, {"aspirante_id": applicant.id})

    try:
        db.commit()
    except IntegrityError:
        # Doble clic: otra petición igual guardó primero. El resultado final es el mismo.
        db.rollback()
        match = db.scalar(select(Match).where(Match.job_id == job_id, Match.applicant_id == applicant.id))
        new_match = False

    return {
        "job_id": job_id,
        "action": action,
        "matched": new_match,
        "match_id": match.id if new_match and match is not None else None,
    }


def undo_swipe(db: Session, user: User, job_id: int) -> None:
    """Deshace la última decisión (botón ↺ de las tarjetas)."""
    applicant = get_applicant(db, user)
    swipe = db.scalar(
        select(ApplicantSwipe).where(ApplicantSwipe.applicant_id == applicant.id, ApplicantSwipe.job_id == job_id)
    )
    if swipe is None:
        raise api_error(404, "No hay ninguna decisión para deshacer en esta vacante.")
    if job_id in _matched_ids(db, applicant.id, [job_id]):
        raise api_error(409, "No puedes deshacer una vacante con la que ya tienes match.")
    db.delete(swipe)
    db.commit()


# =====================================================================
# Mis matches y vacantes que me interesan
# =====================================================================
def get_my_matches(db: Session, user: User) -> dict:
    applicant = get_applicant(db, user)
    ctx = load_applicant_context(db, applicant)
    catalogs = _Catalogs(db)

    matches = db.execute(
        select(Match, Job)
        .join(Job, Job.id == Match.job_id)
        .where(Match.applicant_id == applicant.id, Match.is_active.is_(True))
        .order_by(Match.matched_at.desc(), Match.id.desc())
    ).unique().all()
    matched_job_ids = {job.id for _, job in matches}

    liked_jobs = db.scalars(
        select(Job)
        .join(ApplicantSwipe, ApplicantSwipe.job_id == Job.id)
        .where(
            ApplicantSwipe.applicant_id == applicant.id,
            ApplicantSwipe.action == "like",
            _open_jobs_filter(),
        )
        .order_by(ApplicantSwipe.created_at.desc(), ApplicantSwipe.id.desc())
    ).unique().all()

    active_companies = _active_company_ids(db, {job.company_id for _, job in matches})
    semantic = ai_matching_service.semantic_for_applicant(db, applicant, [job for _, job in matches] + list(liked_jobs))
    return {
        "matches": [
            {
                "match_id": match.id,
                "matched_at": match.matched_at,
                "job": _serialize(job, ctx, catalogs, "like", True, _is_open(job, active_companies), semantic=semantic.get(job.id)),
                "contact": {
                    "name": job.company.contact_name,
                    "email": job.company.contact_email,
                    "phone": job.company.contact_phone,
                },
            }
            for match, job in matches
        ],
        "liked": [
            _serialize(job, ctx, catalogs, "like", False, semantic=semantic.get(job.id))
            for job in liked_jobs if job.id not in matched_job_ids
        ],
    }
