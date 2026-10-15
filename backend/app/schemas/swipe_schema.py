from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.job_schema import JobOut


class SwipeRequest(BaseModel):
    job_id: int
    action: Literal["like", "dislike"]


class SwipeResult(BaseModel):
    job_id: int
    action: Literal["like", "dislike"]
    matched: bool  # True si con este like se formó un match
    match_id: int | None = None


class CompanyContact(BaseModel):
    """Datos de contacto de la empresa: solo se muestran cuando hay match."""

    name: str
    email: str
    phone: str | None


class MatchItem(BaseModel):
    match_id: int
    matched_at: datetime
    job: JobOut
    contact: CompanyContact


class ApplicantMatchesOut(BaseModel):
    matches: list[MatchItem]  # la empresa también dijo que sí
    liked: list[JobOut]  # me interesan, esperando respuesta de la empresa
