"""Datos del perfil del aspirante que se autocompletan desde la hoja de vida."""
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

SKILL_LEVELS = ("basico", "intermedio", "avanzado", "experto")
LANGUAGE_LEVELS = ("basico", "intermedio", "avanzado", "nativo")


class ApplicantExperience(Base):
    __tablename__ = "applicant_experiences"

    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicants.id", ondelete="CASCADE"))
    company_name: Mapped[str] = mapped_column(String(150))
    position: Mapped[str] = mapped_column(String(150))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class ApplicantEducation(Base):
    __tablename__ = "applicant_educations"

    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicants.id", ondelete="CASCADE"))
    education_level_id: Mapped[int] = mapped_column(ForeignKey("education_levels.id"))
    institution: Mapped[str] = mapped_column(String(150))
    degree: Mapped[str] = mapped_column(String(150))
    field_of_study: Mapped[str | None] = mapped_column(String(150), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class ApplicantSkill(Base):
    """Tabla puente N:M aspirante <-> habilidad."""

    __tablename__ = "applicant_skills"

    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicants.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    level: Mapped[str | None] = mapped_column(Enum(*SKILL_LEVELS, name="skill_level_enum"), nullable=True)


class ApplicantLanguage(Base):
    """Tabla puente N:M aspirante <-> idioma."""

    __tablename__ = "applicant_languages"

    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicants.id", ondelete="CASCADE"), primary_key=True)
    language_id: Mapped[int] = mapped_column(ForeignKey("languages.id"), primary_key=True)
    proficiency: Mapped[str] = mapped_column(
        Enum(*LANGUAGE_LEVELS, name="language_level_enum"), default="basico"
    )
