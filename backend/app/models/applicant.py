from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Applicant(Base):
    __tablename__ = "applicants"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id"), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    desired_position: Mapped[str | None] = mapped_column(String(150), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_status: Mapped[str] = mapped_column(
        Enum("buscando_empleo", "sin_busqueda_activa", name="search_status_enum"),
        default="buscando_empleo",
    )
    desired_salary_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    desired_modality: Mapped[str | None] = mapped_column(
        Enum("presencial", "remoto", "hibrido", name="modality_enum"), nullable=True
    )
    willing_to_relocate: Mapped[bool] = mapped_column(Boolean, default=False)
    cv_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cv_original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cv_text: Mapped[str | None] = mapped_column(Text().with_variant(LONGTEXT(), "mysql"), nullable=True)
    cv_parsed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    profile_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())