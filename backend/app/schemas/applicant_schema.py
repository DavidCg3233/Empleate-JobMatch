"""Datos del perfil del aspirante (experiencia, educación, habilidades, idiomas)."""
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

Text150 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]
SkillName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
LanguageLevel = Literal["basico", "intermedio", "avanzado", "nativo"]


def _not_future(value: date | None) -> date | None:
    if value and value > date.today():
        raise ValueError("La fecha no puede estar en el futuro.")
    return value


class ExperienceIn(BaseModel):
    company_name: Text150
    position: Text150
    start_date: date
    end_date: date | None = None
    is_current: bool = False
    description: str | None = Field(default=None, max_length=1000)

    _dates = field_validator("start_date", "end_date")(_not_future)

    @model_validator(mode="after")
    def check_dates(self):
        if self.is_current:
            self.end_date = None
        elif self.end_date and self.end_date < self.start_date:
            raise ValueError("La fecha de fin de una experiencia no puede ser anterior a la de inicio.")
        return self


class EducationIn(BaseModel):
    education_level_id: int
    institution: Text150
    degree: Text150
    field_of_study: str | None = Field(default=None, max_length=150)
    start_date: date | None = None
    end_date: date | None = None

    _dates = field_validator("start_date", "end_date")(_not_future)

    @model_validator(mode="after")
    def check_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("La fecha de fin de un estudio no puede ser anterior a la de inicio.")
        return self


class LanguageIn(BaseModel):
    language_id: int
    proficiency: LanguageLevel = "basico"


class CvParseResponse(BaseModel):
    """Respuesta al subir la hoja de vida durante el registro."""

    cv_upload_id: str                 # se envía luego en el registro para ligar el archivo
    original_name: str
    source: Literal["ia", "basico"]   # quién extrajo los datos
    data: dict                        # campos para autocompletar el formulario
