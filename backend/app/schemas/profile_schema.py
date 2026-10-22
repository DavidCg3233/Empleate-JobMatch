"""Perfil del aspirante: lo que puede ver y administrar después del registro."""
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.applicant_schema import EducationIn, ExperienceIn, LanguageIn, SkillName
from app.schemas.auth_schema import _check_phone, _empty_to_none

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
SearchStatus = Literal["buscando_empleo", "sin_busqueda_activa"]
Modality = Literal["presencial", "remoto", "hibrido"]
MAX_SALARY = 9_999_999_999  # DECIMAL(12,2)


class CvInfo(BaseModel):
    original_name: str
    uploaded_at: datetime | None


class ExperienceOut(BaseModel):
    company_name: str
    position: str
    start_date: date
    end_date: date | None
    is_current: bool
    description: str | None


class EducationOut(BaseModel):
    education_level_id: int
    institution: str
    degree: str
    field_of_study: str | None
    start_date: date | None
    end_date: date | None


class LanguageOut(BaseModel):
    language_id: int
    proficiency: str


class ApplicantProfileOut(BaseModel):
    id: int
    account_email: str
    first_name: str
    last_name: str
    phone: str | None
    city_id: int | None
    desired_position: str | None
    summary: str | None
    search_status: SearchStatus
    desired_salary_min: float | None
    desired_modality: Modality | None
    willing_to_relocate: bool
    profile_completed: bool
    experiences: list[ExperienceOut]
    educations: list[EducationOut]
    skills: list[str]
    languages: list[LanguageOut]
    cv: CvInfo | None


class ApplicantProfileUpdate(BaseModel):
    first_name: Name
    last_name: Name
    phone: str | None = None
    city_id: int | None = None
    desired_position: str | None = Field(default=None, max_length=150)
    summary: str | None = Field(default=None, max_length=2000)
    search_status: SearchStatus = "buscando_empleo"
    desired_salary_min: float | None = Field(default=None, ge=0, le=MAX_SALARY)
    desired_modality: Modality | None = None
    willing_to_relocate: bool = False
    experiences: list[ExperienceIn] = Field(default_factory=list, max_length=15)
    educations: list[EducationIn] = Field(default_factory=list, max_length=10)
    skills: list[SkillName] = Field(default_factory=list, max_length=40)
    languages: list[LanguageIn] = Field(default_factory=list, max_length=10)

    _clean = field_validator(
        "phone", "city_id", "desired_position", "summary", "desired_salary_min", "desired_modality", mode="before"
    )(_empty_to_none)
    _phone = field_validator("phone")(_check_phone)

    @field_validator("desired_position", "summary")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None


class CvUploadOut(BaseModel):
    cv: CvInfo
    source: Literal["ia", "basico"]
    data: dict  # datos leídos de la nueva hoja de vida (se aplican al perfil solo si la persona quiere)
