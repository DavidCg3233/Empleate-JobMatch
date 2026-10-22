"""Rutas de likes / dislikes: del aspirante a vacantes y de la empresa a aspirantes."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.auth_schema import MessageResponse
from app.schemas.company_schema import CompanySwipeIn, CompanySwipeResult
from app.schemas.swipe_schema import SwipeRequest, SwipeResult
from app.services import candidate_service, job_service

router = APIRouter(prefix="/api/swipes", tags=["Swipes"])
applicant_only = require_role("aspirante")
company_only = require_role("empresa")


# ---------------- Aspirante: vacantes ----------------
@router.post("/jobs", response_model=SwipeResult)
def swipe_job(data: SwipeRequest, user: User = Depends(applicant_only), db: Session = Depends(get_db)):
    """Me interesa (like) o No me interesa (dislike). Si la empresa ya había dicho que sí, se crea el match."""
    return job_service.swipe_job(db, user, data.job_id, data.action)


@router.delete("/jobs/{job_id}", response_model=MessageResponse)
def undo_swipe(job_id: int, user: User = Depends(applicant_only), db: Session = Depends(get_db)):
    """Deshace la decisión sobre una vacante (vuelve a aparecer en las tarjetas)."""
    job_service.undo_swipe(db, user, job_id)
    return {"message": "Decisión deshecha."}


# ---------------- Empresa: aspirantes para una vacante ----------------
@router.post("/candidates", response_model=CompanySwipeResult)
def swipe_candidate(data: CompanySwipeIn, user: User = Depends(company_only), db: Session = Depends(get_db)):
    """La empresa dice sí o no a un aspirante para una vacante. Si el aspirante ya había dicho que sí, hay match."""
    return candidate_service.swipe_candidate(db, user, data.job_id, data.applicant_id, data.action)


@router.delete("/candidates/{job_id}/{applicant_id}", response_model=MessageResponse)
def undo_candidate_swipe(
    job_id: int, applicant_id: int, user: User = Depends(company_only), db: Session = Depends(get_db)
):
    """Deshace la decisión sobre un aspirante (vuelve a aparecer en los candidatos)."""
    candidate_service.undo_candidate_swipe(db, user, job_id, applicant_id)
    return {"message": "Decisión deshecha."}
