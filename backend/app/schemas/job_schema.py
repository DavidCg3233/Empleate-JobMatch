from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

Modality = Literal["presencial", "remoto", "hibrido"]
SortOption = Literal["relevancia", "recientes", "salario"]


class CompanyBrief(BaseModel):
    id: int
    name: str
    industry: str | None
    size: str
    city: str | None
    description: str | None
    website: str | None


class JobSkillOut(BaseModel):
    name: str
    is_required: bool
    matched: bool  # el aspirante tiene esta habilidad


class JobOut(BaseModel):
    id: int
    title: str
    description: str
    requirements: str | None
    company: CompanyBrief
    city: str | None
    department: str | None
    modality: Modality
    contract_type: str
    min_education: str | None
    min_experience_years: int
    salary_min: float | None
    salary_max: float | None
    currency: str
    published_at: datetime | None
    closes_at: date | None
    is_open: bool  # False si la vacante se cerró o pausó (puede pasar en un match antiguo)
    skills: list[JobSkillOut]
    score: int  # compatibilidad 0-100
    score_reasons: list[str]  # a favor: por qué encaja
    score_gaps: list[str]  # en contra: qué no encaja o falta
    my_action: Literal["like", "dislike"] | None
    matched: bool


class JobFeedOut(BaseModel):
    items: list[JobOut]
    hidden_count: int = 0  # vacantes que no salen por tener baja compatibilidad (con min_score)


class JobPageOut(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    page_size: int
    has_more: bool
