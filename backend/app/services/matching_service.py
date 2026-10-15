"""Compatibilidad aspirante <-> vacante (0 a 100) con sus razones.

Es un cálculo por reglas, rápido y sin costo (no usa IA):
  - Habilidades requeridas y deseables ........ 50 puntos
  - Años de experiencia ....................... 15 puntos
  - Nivel educativo ........................... 10 puntos
  - Ubicación (ciudad / remoto / traslado) .... 15 puntos
  - Modalidad preferida ........................ 5 puntos
  - Salario esperado ........................... 5 puntos
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.applicant import Applicant
from app.models.applicant_profile import ApplicantEducation, ApplicantExperience, ApplicantSkill
from app.models.catalogs import EducationLevel, Skill
from app.models.job import Job
from app.utils.helpers import normalize_text

MODALITY_LABELS = {"presencial": "presencial", "remoto": "remoto", "hibrido": "híbrido"}


@dataclass
class ApplicantContext:
    """Lo que se necesita del aspirante para calcular la compatibilidad (se carga una sola vez)."""

    applicant_id: int
    city_id: int | None
    desired_modality: str | None
    willing_to_relocate: bool
    desired_salary_min: float | None
    skills: set[str] = field(default_factory=set)  # nombres normalizados
    experience_years: float = 0.0
    education_rank: int = 0  # 0 = sin estudios registrados


def _experience_years(periods: list[tuple[date, date]]) -> float:
    """Suma los periodos trabajados sin contar dos veces los meses que se cruzan."""
    total_days, current_start, current_end = 0, None, None
    for start, end in sorted(periods):
        if current_end is None or start > current_end:
            if current_end is not None:
                total_days += (current_end - current_start).days
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_end is not None:
        total_days += (current_end - current_start).days
    return round(total_days / 365.25, 1)


def load_applicant_context(db: Session, applicant: Applicant) -> ApplicantContext:
    skills = db.scalars(
        select(Skill.name).join(ApplicantSkill, ApplicantSkill.skill_id == Skill.id)
        .where(ApplicantSkill.applicant_id == applicant.id)
    )
    today = date.today()
    periods = [
        (start, min(end or today, today))
        for start, end in db.execute(
            select(ApplicantExperience.start_date, ApplicantExperience.end_date)
            .where(ApplicantExperience.applicant_id == applicant.id)
        )
        if start and start <= today
    ]
    education_rank = db.scalar(
        select(EducationLevel.rank_order)
        .join(ApplicantEducation, ApplicantEducation.education_level_id == EducationLevel.id)
        .where(ApplicantEducation.applicant_id == applicant.id)
        .order_by(EducationLevel.rank_order.desc())
        .limit(1)
    )
    return ApplicantContext(
        applicant_id=applicant.id,
        city_id=applicant.city_id,
        desired_modality=applicant.desired_modality,
        willing_to_relocate=bool(applicant.willing_to_relocate),
        desired_salary_min=float(applicant.desired_salary_min) if applicant.desired_salary_min else None,
        skills={normalize_text(s) for s in skills},
        experience_years=_experience_years(periods),
        education_rank=education_rank or 0,
    )


def _plural_years(n: float) -> str:
    n = int(n) if float(n).is_integer() else n
    return f"{n} año" if n == 1 else f"{n} años"


def compute_score(ctx: ApplicantContext, job: Job) -> tuple[int, list[str], set[str]]:
    """Devuelve (puntaje 0-100, razones para mostrar, habilidades de la vacante que el aspirante tiene)."""
    reasons: list[str] = []
    score = 0.0

    # ---- Habilidades (50) ----
    required = [js.skill.name for js in job.skills if js.is_required]
    desired = [js.skill.name for js in job.skills if not js.is_required]
    matched = {name for name in required + desired if normalize_text(name) in ctx.skills}
    if required or desired:
        req_hit = [s for s in required if s in matched]
        des_hit = [s for s in desired if s in matched]
        if required:
            score += 40 * len(req_hit) / len(required)
            score += (10 * len(des_hit) / len(desired)) if desired else (10 * len(req_hit) / len(required))
        else:
            score += 50 * len(des_hit) / len(desired)
        if required:
            if req_hit:
                reasons.append(
                    f"Tienes {len(req_hit)} de {len(required)} habilidades requeridas: {', '.join(req_hit[:4])}"
                    + ("…" if len(req_hit) > 4 else "")
                )
            else:
                reasons.append("Aún no registras las habilidades requeridas para esta vacante")
        if des_hit:
            reasons.append(f"Sumas puntos con: {', '.join(des_hit[:3])}")
    else:
        # La vacante no lista habilidades: se buscan las del aspirante en el texto
        text = normalize_text(f"{job.title} {job.description} {job.requirements or ''}")
        hits = [s for s in ctx.skills if len(s) > 2 and s in text]
        score += min(50, 25 + 8 * len(hits)) if hits else 25

    # ---- Experiencia (15) ----
    need = job.min_experience_years or 0
    if need == 0:
        score += 15
        reasons.append("No exige experiencia previa")
    elif ctx.experience_years >= need:
        score += 15
        reasons.append(f"Cumples la experiencia mínima ({_plural_years(need)})")
    else:
        score += 15 * ctx.experience_years / need
        reasons.append(f"Pide {_plural_years(need)} de experiencia; registras {_plural_years(ctx.experience_years)}")

    # ---- Educación (10) ----
    if job.min_education is None:
        score += 10
    elif ctx.education_rank >= job.min_education.rank_order:
        score += 10
        reasons.append(f"Cumples el nivel educativo ({job.min_education.name})")
    else:
        score += 3 if ctx.education_rank else 0
        reasons.append(f"Pide nivel educativo mínimo: {job.min_education.name}")

    # ---- Ubicación (15) ----
    if job.modality == "remoto":
        score += 15
        reasons.append("Trabajo 100% remoto")
    elif job.city_id and job.city_id == ctx.city_id:
        score += 15
        reasons.append("Es en tu ciudad")
    elif ctx.willing_to_relocate:
        score += 8
        reasons.append("Es en otra ciudad, pero aceptas trasladarte")
    elif job.modality == "hibrido":
        score += 4

    # ---- Modalidad (5) ----
    if ctx.desired_modality is None or ctx.desired_modality == job.modality:
        score += 5
        if ctx.desired_modality:
            reasons.append(f"Modalidad {MODALITY_LABELS[job.modality]}, como prefieres")

    # ---- Salario (5) ----
    top = job.salary_max or job.salary_min
    if ctx.desired_salary_min is None or top is None:
        score += 3
    elif float(top) >= ctx.desired_salary_min:
        score += 5
        reasons.append("El salario cumple tu aspiración")

    return max(0, min(100, round(score))), reasons, matched
