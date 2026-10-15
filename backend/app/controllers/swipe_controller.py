"""Rutas de likes / dislikes del aspirante: /api/swipes/..."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.auth_schema import MessageResponse
from app.schemas.swipe_schema import SwipeRequest, SwipeResult
from app.services import job_service

router = APIRouter(prefix="/api/swipes", tags=["Swipes"])
applicant_only = require_role("aspirante")


@router.post("/jobs", response_model=SwipeResult)
def swipe_job(data: SwipeRequest, user: User = Depends(applicant_only), db: Session = Depends(get_db)):
    """Me interesa (like) o No me interesa (dislike). Si la empresa ya había dicho que sí, se crea el match."""
    return job_service.swipe_job(db, user, data.job_id, data.action)


@router.delete("/jobs/{job_id}", response_model=MessageResponse)
def undo_swipe(job_id: int, user: User = Depends(applicant_only), db: Session = Depends(get_db)):
    """Deshace la decisión sobre una vacante (vuelve a aparecer en las tarjetas)."""
    job_service.undo_swipe(db, user, job_id)
    return {"message": "Decisión deshecha."}
