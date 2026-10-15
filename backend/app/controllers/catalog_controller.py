"""Catálogos públicos que necesitan los formularios (ciudades, sectores, educación, idiomas, contratos)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.catalogs import EducationLevel, Language
from app.models.city import City, Department
from app.models.industry import Industry
from app.models.job import ContractType
from app.schemas.catalog_schema import CatalogItemOut, CityOut, IndustryOut

router = APIRouter(prefix="/api/catalogs", tags=["Catálogos"])


@router.get("/cities", response_model=list[CityOut])
def list_cities(db: Session = Depends(get_db)):
    rows = db.execute(
        select(City.id, City.name, Department.name.label("department"))
        .join(Department, City.department_id == Department.id)
        .order_by(Department.name, City.name)
    ).all()
    return [{"id": r.id, "name": r.name, "department": r.department} for r in rows]


@router.get("/industries", response_model=list[IndustryOut])
def list_industries(db: Session = Depends(get_db)):
    rows = db.execute(select(Industry.id, Industry.name).order_by(Industry.name)).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/education-levels", response_model=list[CatalogItemOut])
def list_education_levels(db: Session = Depends(get_db)):
    rows = db.execute(select(EducationLevel.id, EducationLevel.name).order_by(EducationLevel.rank_order)).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/languages", response_model=list[CatalogItemOut])
def list_languages(db: Session = Depends(get_db)):
    rows = db.execute(select(Language.id, Language.name).order_by(Language.id)).all()
    return [{"id": r.id, "name": r.name} for r in rows]


@router.get("/contract-types", response_model=list[CatalogItemOut])
def list_contract_types(db: Session = Depends(get_db)):
    rows = db.execute(select(ContractType.id, ContractType.name).order_by(ContractType.id)).all()
    return [{"id": r.id, "name": r.name} for r in rows]
