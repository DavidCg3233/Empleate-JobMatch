"""Catálogos de apoyo para el perfil del aspirante."""
from sqlalchemy import Boolean, Enum, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EducationLevel(Base):
    __tablename__ = "education_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    rank_order: Mapped[int] = mapped_column(SmallInteger, unique=True)  # mayor = nivel más alto


class Language(Base):
    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


SKILL_CATEGORIES = ("tecnica", "herramienta", "blanda")


class Skill(Base):
    """Catálogo de habilidades y herramientas.
    Las curadas (is_curated) se sugieren en los formularios; el catálogo también crece con lo que
    escriben aspirantes y empresas o se extrae de las hojas de vida."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str | None] = mapped_column(Enum(*SKILL_CATEGORIES, name="skill_category_enum"), nullable=True)
    is_curated: Mapped[bool] = mapped_column(Boolean, default=False)
