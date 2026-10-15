"""Rutas de matches: /api/matches/..."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.swipe_schema import ApplicantMatchesOut
from app.services import job_service

router = APIRouter(prefix="/api/matches", tags=["Matches"])


@router.get("/applicant", response_model=ApplicantMatchesOut)
def my_matches(user: User = Depends(require_role("aspirante")), db: Session = Depends(get_db)):
    """Matches del aspirante y vacantes que le interesan (esperando respuesta de la empresa)."""
    return job_service.get_my_matches(db, user)
