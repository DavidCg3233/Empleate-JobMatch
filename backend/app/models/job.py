from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CHAR, Date, DateTime, Enum, ForeignKey, Numeric, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.catalogs import EducationLevel, Skill
from app.models.company import Company

MODALITIES = ("presencial", "remoto", "hibrido")
JOB_STATUSES = ("activa", "pausada", "cerrada")


class ContractType(Base):
    __tablename__ = "contract_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


class JobSkill(Base):
    """Tabla puente N:M vacante <-> habilidad."""

    __tablename__ = "job_skills"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), primary_key=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)  # True = obligatoria, False = deseable

    skill: Mapped[Skill] = relationship(lazy="joined")


class Job(Base):
    """Vacante publicada por una empresa."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"), nullable=True)  # NULL = 100% remoto
    modality: Mapped[str] = mapped_column(Enum(*MODALITIES, name="modality_enum"))
    contract_type_id: Mapped[int] = mapped_column(ForeignKey("contract_types.id"))
    min_education_id: Mapped[int | None] = mapped_column(ForeignKey("education_levels.id"), nullable=True)
    min_experience_years: Mapped[int] = mapped_column(SmallInteger, default=0)
    salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(CHAR(3), default="COP")
    status: Mapped[str] = mapped_column(Enum(*JOB_STATUSES, name="job_status_enum"), default="activa")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # el administrador puede deshabilitarla
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closes_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    company: Mapped[Company] = relationship(lazy="joined")
    contract_type: Mapped[ContractType] = relationship(lazy="joined")
    min_education: Mapped[EducationLevel | None] = relationship(lazy="joined")
    skills: Mapped[list[JobSkill]] = relationship(lazy="selectin", cascade="all, delete-orphan")
