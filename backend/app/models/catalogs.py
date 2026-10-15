"""Catálogos de apoyo para el perfil del aspirante."""
from sqlalchemy import SmallInteger, String
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


class Skill(Base):
    """Catálogo que crece con las habilidades que se extraen de las hojas de vida."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
