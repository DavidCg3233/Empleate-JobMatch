"""Rutas de vacantes para el aspirante: /api/jobs/..."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.job_schema import JobFeedOut, JobOut, JobPageOut, Modality, SortOption
from app.services import job_service

router = APIRouter(prefix="/api/jobs", tags=["Vacantes"])
applicant_only = require_role("aspirante")


@router.get("/feed", response_model=JobFeedOut)
def feed(
    city_id: int | None = Query(default=None, gt=0),
    modality: Modality | None = None,
    contract_type_id: int | None = Query(default=None, gt=0),
    exclude: list[int] = Query(default=[], max_length=100),
    user: User = Depends(applicant_only),
    db: Session = Depends(get_db),
):
    """Tarjetas para deslizar: vacantes que el aspirante aún no ha visto, de la más compatible a la menos."""
    return job_service.get_feed(db, user, city_id, modality, contract_type_id, exclude)


@router.get("/search", response_model=JobPageOut)
def search(
    q: str | None = Query(default=None, max_length=100),
    city_id: int | None = Query(default=None, gt=0),
    modality: Modality | None = None,
    contract_type_id: int | None = Query(default=None, gt=0),
    salary_min: float | None = Query(default=None, ge=0),
    sort: SortOption = "relevancia",
    hide_discarded: bool = False,
    page: int = Query(default=1, ge=1, le=100),
    page_size: int = Query(default=12, ge=1, le=50),
    user: User = Depends(applicant_only),
    db: Session = Depends(get_db),
):
    """Buscador con filtros. Incluye las vacantes ya marcadas (con su estado en my_action)."""
    return job_service.search_jobs(
        db, user, q, city_id, modality, contract_type_id, salary_min, sort, hide_discarded, page, page_size
    )


@router.get("/{job_id}", response_model=JobOut)
def job_detail(job_id: int, user: User = Depends(applicant_only), db: Session = Depends(get_db)):
    return job_service.get_job_detail(db, user, job_id)
