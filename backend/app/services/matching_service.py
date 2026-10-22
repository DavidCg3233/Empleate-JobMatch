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
    return load_applicant_contexts(db, [applicant])[applicant.id]


def load_applicant_contexts(db: Session, applicants: list[Applicant]) -> dict[int, ApplicantContext]:
    """Contexto de varios aspirantes con 3 consultas en total (sirve para listas de candidatos)."""
    ids = [a.id for a in applicants]
    if not ids:
        return {}

    skills: dict[int, set[str]] = {i: set() for i in ids}
    for applicant_id, name in db.execute(
        select(ApplicantSkill.applicant_id, Skill.name)
        .join(Skill, Skill.id == ApplicantSkill.skill_id)
        .where(ApplicantSkill.applicant_id.in_(ids))
    ):
        skills[applicant_id].add(normalize_text(name))

    today = date.today()
    periods: dict[int, list[tuple[date, date]]] = {i: [] for i in ids}
    for applicant_id, start, end in db.execute(
        select(ApplicantExperience.applicant_id, ApplicantExperience.start_date, ApplicantExperience.end_date)
        .where(ApplicantExperience.applicant_id.in_(ids))
    ):
        if start and start <= today:
            periods[applicant_id].append((start, min(end or today, today)))

    education: dict[int, int] = {}
    for applicant_id, rank in db.execute(
        select(ApplicantEducation.applicant_id, EducationLevel.rank_order)
        .join(EducationLevel, EducationLevel.id == ApplicantEducation.education_level_id)
        .where(ApplicantEducation.applicant_id.in_(ids))
    ):
        education[applicant_id] = max(education.get(applicant_id, 0), rank)

    return {
        a.id: ApplicantContext(
            applicant_id=a.id,
            city_id=a.city_id,
            desired_modality=a.desired_modality,
            willing_to_relocate=bool(a.willing_to_relocate),
            desired_salary_min=float(a.desired_salary_min) if a.desired_salary_min else None,
            skills=skills[a.id],
            experience_years=_experience_years(periods[a.id]),
            education_rank=education.get(a.id, 0),
        )
        for a in applicants
    }


def _plural_years(n: float) -> str:
    """2 -> "2 años" · 1 -> "1 año" · 5.8 -> "5,8 años" (coma decimal, como se escribe en Colombia)."""
    n = int(n) if float(n).is_integer() else n
    text = str(n).replace(".", ",")
    return f"{text} año" if n == 1 else f"{text} años"


# Las razones se redactan según quién las lee: el aspirante ("tienes") o la empresa ("tiene")
PHRASES = {
    "aspirante": {
        "req_hit": "Tienes {hit} de {total} habilidades requeridas: {names}",
        "req_none": "Aún no registras las habilidades requeridas para esta vacante",
        "desired": "Sumas puntos con: {names}",
        "no_exp": "No exige experiencia previa",
        "exp_ok": "Cumples la experiencia mínima ({need})",
        "exp_low": "Pide {need} de experiencia; registras {has}",
        "edu_ok": "Cumples el nivel educativo ({level})",
        "edu_low": "Pide nivel educativo mínimo: {level}",
        "remote": "Trabajo 100% remoto",
        "same_city": "Es en tu ciudad",
        "relocate": "Es en otra ciudad, pero aceptas trasladarte",
        "modality": "Modalidad {modality}, como prefieres",
        "salary": "El salario cumple tu aspiración",
    },
    "empresa": {
        "req_hit": "Tiene {hit} de {total} habilidades requeridas: {names}",
        "req_none": "No registra las habilidades requeridas",
        "desired": "Suma puntos con: {names}",
        "no_exp": "La vacante no exige experiencia",
        "exp_ok": "Cumple la experiencia mínima ({need}); registra {has}",
        "exp_low": "Registra {has} de experiencia; la vacante pide {need}",
        "edu_ok": "Cumple el nivel educativo ({level})",
        "edu_low": "No registra el nivel educativo mínimo ({level})",
        "remote": "Trabajo remoto: la ciudad no es un problema",
        "same_city": "Vive en la ciudad de la vacante",
        "relocate": "Vive en otra ciudad, pero acepta trasladarse",
        "modality": "Prefiere la modalidad {modality}",
        "salary": "Su aspiración salarial está dentro del rango",
    },
}


def compute_score(ctx: ApplicantContext, job: Job, audience: str = "aspirante") -> tuple[int, list[str], set[str]]:
    """Devuelve (puntaje 0-100, razones para mostrar, habilidades de la vacante que el aspirante tiene)."""
    t = PHRASES[audience]
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
                names = ", ".join(req_hit[:4]) + ("…" if len(req_hit) > 4 else "")
                reasons.append(t["req_hit"].format(hit=len(req_hit), total=len(required), names=names))
            else:
                reasons.append(t["req_none"])
        if des_hit:
            reasons.append(t["desired"].format(names=", ".join(des_hit[:3])))
    else:
        # La vacante no lista habilidades: se buscan las del aspirante en el texto
        text = normalize_text(f"{job.title} {job.description} {job.requirements or ''}")
        hits = [s for s in ctx.skills if len(s) > 2 and s in text]
        score += min(50, 25 + 8 * len(hits)) if hits else 25

    # ---- Experiencia (15) ----
    need = job.min_experience_years or 0
    if need == 0:
        score += 15
        reasons.append(t["no_exp"])
    elif ctx.experience_years >= need:
        score += 15
        reasons.append(t["exp_ok"].format(need=_plural_years(need), has=_plural_years(ctx.experience_years)))
    else:
        score += 15 * ctx.experience_years / need
        reasons.append(t["exp_low"].format(need=_plural_years(need), has=_plural_years(ctx.experience_years)))

    # ---- Educación (10) ----
    if job.min_education is None:
        score += 10
    elif ctx.education_rank >= job.min_education.rank_order:
        score += 10
        reasons.append(t["edu_ok"].format(level=job.min_education.name))
    else:
        score += 3 if ctx.education_rank else 0
        reasons.append(t["edu_low"].format(level=job.min_education.name))

    # ---- Ubicación (15) ----
    if job.modality == "remoto":
        score += 15
        reasons.append(t["remote"])
    elif job.city_id and job.city_id == ctx.city_id:
        score += 15
        reasons.append(t["same_city"])
    elif ctx.willing_to_relocate:
        score += 8
        reasons.append(t["relocate"])
    elif job.modality == "hibrido":
        score += 4

    # ---- Modalidad (5) ----
    if ctx.desired_modality is None or ctx.desired_modality == job.modality:
        score += 5
        if ctx.desired_modality:
            reasons.append(t["modality"].format(modality=MODALITY_LABELS[job.modality]))

    # ---- Salario (5) ----
    top = job.salary_max or job.salary_min
    if ctx.desired_salary_min is None or top is None:
        score += 3
    elif float(top) >= ctx.desired_salary_min:
        score += 5
        reasons.append(t["salary"])

    return max(0, min(100, round(score))), reasons, matched
