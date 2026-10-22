"""Rutas de matches: /api/matches/..."""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.company_schema import CompanyMatchOut
from app.schemas.swipe_schema import ApplicantMatchesOut
from app.services import candidate_service, job_service

router = APIRouter(prefix="/api/matches", tags=["Matches"])


@router.get("/applicant", response_model=ApplicantMatchesOut)
def my_matches(user: User = Depends(require_role("aspirante")), db: Session = Depends(get_db)):
    """Matches del aspirante y vacantes que le interesan (esperando respuesta de la empresa)."""
    return job_service.get_my_matches(db, user)


@router.get("/company", response_model=list[CompanyMatchOut])
def company_matches(
    job_id: int | None = Query(default=None, gt=0),
    user: User = Depends(require_role("empresa")),
    db: Session = Depends(get_db),
):
    """Matches de la empresa (de todas sus vacantes o de una), con los datos de contacto del aspirante."""
    return candidate_service.get_company_matches(db, user, job_id)


@router.get("/{match_id}/cv", response_class=FileResponse)
def download_match_cv(match_id: int, user: User = Depends(require_role("empresa")), db: Session = Depends(get_db)):
    """Descarga la hoja de vida del aspirante. Solo la empresa con la que hizo match."""
    path, filename = candidate_service.get_match_cv(db, user, match_id)
    return FileResponse(path, filename=filename)
