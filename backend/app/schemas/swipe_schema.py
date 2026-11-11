from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.job_schema import JobOut

# Etapas del proceso después del match (mismo orden que app.models.match.MATCH_STAGES)
MatchStage = Literal["match", "en_revision", "entrevista", "seleccionado", "descartado"]


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
    stage: MatchStage
    stage_updated_at: datetime | None
    job: JobOut
    contact: CompanyContact


class MatchStageIn(BaseModel):
    stage: MatchStage


class MatchStageOut(BaseModel):
    match_id: int
    stage: MatchStage
    stage_updated_at: datetime | None


class ApplicantMatchesOut(BaseModel):
    matches: list[MatchItem]  # la empresa también dijo que sí
    liked: list[JobOut]  # me interesan, esperando respuesta de la empresa
