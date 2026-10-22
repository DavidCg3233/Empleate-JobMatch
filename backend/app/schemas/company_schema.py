"""Esquemas del módulo de empresa: perfil, vacantes (CRUD), candidatos y matches."""
import re
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator, model_validator

from app.schemas.auth_schema import WEBSITE_RE, CompanySize, _check_phone, _empty_to_none

Modality = Literal["presencial", "remoto", "hibrido"]
JobStatus = Literal["activa", "pausada", "cerrada"]
Text150 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]
MAX_SALARY = 9_999_999_999  # DECIMAL(12,2)


# =====================================================================
# Perfil de la empresa
# =====================================================================
class CompanyProfileOut(BaseModel):
    id: int
    account_email: str  # correo con el que inicia sesión (no se edita aquí)
    name: str
    tax_id: str  # el NIT identifica a la empresa: no se puede cambiar
    industry_id: int
    industry: str | None
    size: CompanySize
    city_id: int
    city: str | None
    description: str | None
    address: str | None
    website: str | None
    contact_name: str
    contact_phone: str | None
    contact_email: str
    created_at: datetime


class CompanyProfileUpdate(BaseModel):
    name: Text150
    industry_id: int
    size: CompanySize
    city_id: int
    description: str | None = Field(default=None, max_length=2000)
    address: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=255)
    contact_name: Text150
    contact_phone: str | None = None
    contact_email: EmailStr

    _clean = field_validator("description", "address", "website", "contact_phone", mode="before")(_empty_to_none)
    _phone = field_validator("contact_phone")(_check_phone)

    @field_validator("website")
    @classmethod
    def check_website(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not re.match(r"^https?://", value, re.IGNORECASE):
            value = "https://" + value
        if not WEBSITE_RE.match(value):
            raise ValueError("El sitio web no es válido. Ejemplo: https://miempresa.com")
        return value


# =====================================================================
# Vacantes de la empresa
# =====================================================================
class JobSkillIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    is_required: bool = True


class JobIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=150)]
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=30, max_length=5000)]
    requirements: str | None = Field(default=None, max_length=3000)
    modality: Modality
    city_id: int | None = None  # obligatoria salvo en vacantes 100% remotas
    contract_type_id: int
    min_education_id: int | None = None
    min_experience_years: int = Field(default=0, ge=0, le=40)
    salary_min: float | None = Field(default=None, ge=0, le=MAX_SALARY)
    salary_max: float | None = Field(default=None, ge=0, le=MAX_SALARY)
    currency: Literal["COP", "USD"] = "COP"
    closes_at: date | None = None
    skills: list[JobSkillIn] = Field(default_factory=list, max_length=20)

    _clean = field_validator(
        "requirements", "city_id", "min_education_id", "salary_min", "salary_max", "closes_at", mode="before"
    )(_empty_to_none)

    @field_validator("requirements")
    @classmethod
    def strip_requirements(cls, value: str | None) -> str | None:
        return value.strip() if value else None

    @field_validator("skills")
    @classmethod
    def dedupe_skills(cls, skills: list[JobSkillIn]) -> list[JobSkillIn]:
        """'Python' y 'python' son la misma; si alguna de las dos es obligatoria, queda obligatoria."""
        result: dict[str, JobSkillIn] = {}
        for skill in skills:
            name = re.sub(r"\s+", " ", skill.name)
            key = name.lower()
            if key in result:
                result[key].is_required = result[key].is_required or skill.is_required
            else:
                result[key] = JobSkillIn(name=name, is_required=skill.is_required)
        return list(result.values())

    @model_validator(mode="after")
    def check_consistency(self):
        if self.modality == "remoto":
            self.city_id = None  # en la base de datos: NULL = 100% remoto
        elif self.city_id is None:
            raise ValueError("Selecciona la ciudad de la vacante.")
        if self.salary_min is not None and self.salary_max is not None and self.salary_max < self.salary_min:
            raise ValueError("El salario máximo no puede ser menor que el mínimo.")
        if self.closes_at is not None and self.closes_at < date.today():
            raise ValueError("La fecha de cierre no puede estar en el pasado.")
        return self


class JobCreate(JobIn):
    # "activa" = se publica de una vez; "pausada" = se guarda sin que los aspirantes la vean
    status: Literal["activa", "pausada"] = "activa"


class JobStatusIn(BaseModel):
    status: JobStatus


class JobSkillOut(BaseModel):
    name: str
    is_required: bool


class JobStats(BaseModel):
    interested: int  # aspirantes que dijeron "me interesa"
    pending: int  # interesados que la empresa aún no ha revisado
    matches: int


class CompanyJobOut(BaseModel):
    id: int
    title: str
    description: str
    requirements: str | None
    modality: Modality
    city_id: int | None
    city: str | None
    contract_type_id: int
    contract_type: str
    min_education_id: int | None
    min_education: str | None
    min_experience_years: int
    salary_min: float | None
    salary_max: float | None
    currency: str
    status: JobStatus
    is_enabled: bool  # False = el administrador la deshabilitó
    is_expired: bool  # la fecha de cierre ya pasó
    is_visible: bool  # los aspirantes la están viendo ahora mismo
    can_delete: bool  # solo si nadie ha interactuado con ella
    published_at: datetime | None
    closes_at: date | None
    created_at: datetime
    updated_at: datetime
    skills: list[JobSkillOut]
    stats: JobStats


# =====================================================================
# Candidatos (aspirantes para una vacante)
# =====================================================================
class CandidateExperience(BaseModel):
    position: str
    company_name: str
    start_date: date
    end_date: date | None
    is_current: bool
    description: str | None


class CandidateEducation(BaseModel):
    degree: str
    institution: str
    field_of_study: str | None
    level: str
    start_date: date | None
    end_date: date | None


class CandidateSkill(BaseModel):
    name: str
    matched: bool  # la vacante pide esta habilidad


class CandidateLanguage(BaseModel):
    name: str
    proficiency: str


class CandidateContact(BaseModel):
    """Solo se entrega cuando hay match."""

    full_name: str
    email: str
    phone: str | None
    has_cv: bool


class CandidateOut(BaseModel):
    applicant_id: int
    display_name: str  # antes del match: nombre y la inicial del apellido
    city: str | None
    desired_position: str | None
    summary: str | None
    experience_years: float
    education_level: str | None
    experiences: list[CandidateExperience]
    educations: list[CandidateEducation]
    skills: list[CandidateSkill]
    languages: list[CandidateLanguage]
    willing_to_relocate: bool
    desired_modality: Modality | None
    score: int
    score_reasons: list[str]  # a favor: por qué encaja
    score_gaps: list[str]  # en contra: qué no encaja o falta
    interested: bool  # el aspirante ya dijo "me interesa" a esta vacante
    company_action: Literal["like", "dislike"] | None
    matched: bool


class CandidateFeedOut(BaseModel):
    job_id: int
    job_title: str
    items: list[CandidateOut]


class CompanySwipeIn(BaseModel):
    job_id: int
    applicant_id: int
    action: Literal["like", "dislike"]


class CompanySwipeResult(BaseModel):
    job_id: int
    applicant_id: int
    action: Literal["like", "dislike"]
    matched: bool
    match_id: int | None = None


class JobBrief(BaseModel):
    id: int
    title: str
    status: JobStatus


class CompanyMatchOut(BaseModel):
    match_id: int
    matched_at: datetime
    job: JobBrief
    candidate: CandidateOut
    contact: CandidateContact
