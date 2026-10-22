"""Rutas de vacantes: búsqueda del aspirante (/api/jobs) y CRUD de la empresa (/api/company/jobs)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.auth_schema import MessageResponse
from app.schemas.company_schema import CandidateFeedOut, CompanyJobOut, JobCreate, JobIn, JobStatusIn
from app.schemas.job_schema import JobFeedOut, JobOut, JobPageOut, Modality, SortOption
from app.services import candidate_service, company_service, job_service

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


# =====================================================================
# Vacantes de la empresa (CRUD): /api/company/jobs/...
# =====================================================================
company_router = APIRouter(prefix="/api/company/jobs", tags=["Vacantes de la empresa"])
company_only = require_role("empresa")


@company_router.get("", response_model=list[CompanyJobOut])
def list_company_jobs(user: User = Depends(company_only), db: Session = Depends(get_db)):
    """Vacantes de la empresa con sus números: interesados, pendientes por revisar y matches."""
    return company_service.list_jobs(db, user)


@company_router.post("", response_model=CompanyJobOut, status_code=201)
def create_company_job(data: JobCreate, user: User = Depends(company_only), db: Session = Depends(get_db)):
    return company_service.create_job(db, user, data)


@company_router.get("/{job_id}", response_model=CompanyJobOut)
def get_company_job(job_id: int, user: User = Depends(company_only), db: Session = Depends(get_db)):
    return company_service.get_job(db, user, job_id)


@company_router.put("/{job_id}", response_model=CompanyJobOut)
def update_company_job(job_id: int, data: JobIn, user: User = Depends(company_only), db: Session = Depends(get_db)):
    return company_service.update_job(db, user, job_id, data)


@company_router.patch("/{job_id}/status", response_model=CompanyJobOut)
def change_company_job_status(
    job_id: int, data: JobStatusIn, user: User = Depends(company_only), db: Session = Depends(get_db)
):
    """Publicar (activa), pausar o cerrar la vacante."""
    return company_service.change_status(db, user, job_id, data.status)


@company_router.delete("/{job_id}", response_model=MessageResponse)
def delete_company_job(job_id: int, user: User = Depends(company_only), db: Session = Depends(get_db)):
    """Solo se pueden eliminar vacantes con las que nadie ha interactuado; las demás se cierran."""
    company_service.delete_job(db, user, job_id)
    return {"message": "Vacante eliminada."}


@company_router.get("/{job_id}/candidates", response_model=CandidateFeedOut)
def list_candidates(
    job_id: int,
    only_interested: bool = False,
    exclude: list[int] = Query(default=[], max_length=100),
    user: User = Depends(company_only),
    db: Session = Depends(get_db),
):
    """Aspirantes para deslizar: primero los interesados en la vacante, luego otros perfiles compatibles."""
    return candidate_service.get_candidates(db, user, job_id, only_interested, exclude)
