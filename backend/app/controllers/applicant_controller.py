"""Perfil del aspirante: /api/applicant/..."""
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.profile_schema import ApplicantProfileOut, ApplicantProfileUpdate, CvUploadOut
from app.services import applicant_service
from app.utils.helpers import RateLimiter

router = APIRouter(prefix="/api/applicant", tags=["Perfil del aspirante"])
applicant_only = require_role("aspirante")
cv_limiter = RateLimiter(limit=10, window_seconds=10 * 60)  # leer un CV puede usar IA: se limita


@router.get("/profile", response_model=ApplicantProfileOut)
def get_profile(user: User = Depends(applicant_only), db: Session = Depends(get_db)):
    return applicant_service.get_profile(db, user)


@router.put("/profile", response_model=ApplicantProfileOut)
def update_profile(data: ApplicantProfileUpdate, user: User = Depends(applicant_only), db: Session = Depends(get_db)):
    """Guarda todo el perfil: datos personales, lo que busca, experiencia, estudios, habilidades e idiomas."""
    return applicant_service.update_profile(db, user, data)


@router.post("/cv", response_model=CvUploadOut, dependencies=[Depends(cv_limiter)])
def upload_cv(file: UploadFile = File(...), user: User = Depends(applicant_only), db: Session = Depends(get_db)):
    """Sube una hoja de vida nueva (reemplaza la anterior) y devuelve lo que se leyó de ella."""
    content = file.file.read(settings.MAX_CV_MB * 1024 * 1024 + 1)
    return applicant_service.upload_cv(db, user, file.filename, content)


@router.get("/cv", response_class=FileResponse)
def download_my_cv(user: User = Depends(applicant_only), db: Session = Depends(get_db)):
    path, filename = applicant_service.get_cv_file(db, user)
    return FileResponse(path, filename=filename)
