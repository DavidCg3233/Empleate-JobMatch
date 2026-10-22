"""Caché de la IA para el emparejamiento (para no pagar dos veces por el mismo cálculo).

- applicant_embeddings / job_embeddings: vector semántico del perfil y de la vacante.
- match_scores: análisis de la IA para una pareja aspirante-vacante (puntaje y explicación).

`content_hash` es la huella del texto con que se calculó: si el perfil o la vacante cambian,
la huella cambia y el dato se vuelve a calcular.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CHAR, JSON, DateTime, ForeignKey, Numeric, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApplicantEmbedding(Base):
    __tablename__ = "applicant_embeddings"

    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicants.id", ondelete="CASCADE"), primary_key=True)
    model: Mapped[str] = mapped_column(String(80))
    vector: Mapped[list] = mapped_column(JSON)
    content_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class JobEmbedding(Base):
    __tablename__ = "job_embeddings"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    model: Mapped[str] = mapped_column(String(80))
    vector: Mapped[list] = mapped_column(JSON)
    content_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class MatchScore(Base):
    __tablename__ = "match_scores"
    __table_args__ = (UniqueConstraint("applicant_id", "job_id", name="uq_match_scores"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicants.id", ondelete="CASCADE"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    semantic_similarity: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    score: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON con el análisis para cada parte
    model_used: Mapped[str | None] = mapped_column(String(80), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
