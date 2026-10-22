"""Emparejamiento con IA: /api/matching/..."""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.core.exceptions import api_error
from app.database import get_db
from app.models.applicant import Applicant
from app.models.match import Match
from app.models.swipe import ApplicantSwipe
from app.models.user import User
from app.services import ai_matching_service
from app.services.ai.base import AIError
from app.services.company_service import get_company, get_owned_job
from app.services.job_service import get_applicant, get_viewable_job
from app.utils.helpers import RateLimiter

router = APIRouter(prefix="/api/matching", tags=["Emparejamiento con IA"])
analysis_limiter = RateLimiter(limit=40, window_seconds=10 * 60)  # cada análisis nuevo cuesta: se limita


class MatchingStatus(BaseModel):
    provider: str | None
    semantic: bool  # la afinidad semántica se suma al porcentaje
    analysis: bool  # se puede pedir el análisis de cada pareja


class MatchAnalysisOut(BaseModel):
    score: int
    summary: str
    strengths: list[str]
    gaps: list[str]
    advice: str | None  # para el aspirante
    interview_questions: list[str]  # para la empresa
    model: str | None
    generated_at: datetime | None
    cached: bool


def _run(db: Session, applicant: Applicant, job, audience: str) -> dict:
    try:
        return ai_matching_service.analyze_pair(db, applicant, job, audience)
    except ai_matching_service.AnalysisUnavailable:
        raise api_error(503, "El análisis con IA no está disponible en este momento.")
    except AIError:
        raise api_error(502, "No pudimos generar el análisis con IA. Intenta de nuevo en unos minutos.")


@router.get("/status", response_model=MatchingStatus)
def matching_status():
    """Qué partes de la IA están activas (el frontend muestra u oculta el análisis según esto)."""
    return ai_matching_service.status()


@router.get("/jobs/{job_id}/analysis", response_model=MatchAnalysisOut, dependencies=[Depends(analysis_limiter)])
def analyze_for_applicant(job_id: int, user: User = Depends(require_role("aspirante")), db: Session = Depends(get_db)):
    """Análisis de la IA: qué tan bien encajas con esta vacante, qué te falta y un consejo."""
    applicant = get_applicant(db, user)
    job, _, _ = get_viewable_job(db, applicant, job_id)  # misma regla de acceso que el detalle
    return _run(db, applicant, job, "aspirante")


@router.get(
    "/jobs/{job_id}/candidates/{applicant_id}/analysis",
    response_model=MatchAnalysisOut,
    dependencies=[Depends(analysis_limiter)],
)
def analyze_for_company(
    job_id: int, applicant_id: int, user: User = Depends(require_role("empresa")), db: Session = Depends(get_db)
):
    """Análisis de la IA de un candidato para una vacante de la empresa (incluye preguntas de entrevista)."""
    job = get_owned_job(db, get_company(db, user), job_id)
    applicant = db.scalar(
        select(Applicant).join(User, User.id == Applicant.user_id)
        .where(Applicant.id == applicant_id, User.is_active.is_(True))
    )
    if applicant is None:
        raise api_error(404, "Este aspirante ya no está disponible.")

    # La empresa solo puede analizar a quien podría ver como candidato o con quien ya tiene match
    swipe = db.scalar(
        select(ApplicantSwipe.action).where(ApplicantSwipe.applicant_id == applicant.id, ApplicantSwipe.job_id == job.id)
    )
    matched = db.scalar(
        select(Match.id).where(Match.applicant_id == applicant.id, Match.job_id == job.id, Match.is_active.is_(True))
    )
    visible = matched is not None or swipe == "like" or (swipe is None and applicant.search_status == "buscando_empleo")
    if not visible:
        raise api_error(404, "Este aspirante ya no está disponible.")
    return _run(db, applicant, job, "empresa")
