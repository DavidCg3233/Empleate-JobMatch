"""Perfil de la empresa: /api/company/profile"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.schemas.company_schema import CompanyProfileOut, CompanyProfileUpdate
from app.services import company_service

router = APIRouter(prefix="/api/company", tags=["Empresa"])
company_only = require_role("empresa")


@router.get("/profile", response_model=CompanyProfileOut)
def get_profile(user: User = Depends(company_only), db: Session = Depends(get_db)):
    return company_service.get_profile(db, user)


@router.put("/profile", response_model=CompanyProfileOut)
def update_profile(data: CompanyProfileUpdate, user: User = Depends(company_only), db: Session = Depends(get_db)):
    """Actualiza los datos de la empresa. El NIT y el correo de la cuenta no se cambian aquí."""
    return company_service.update_profile(db, user, data)
