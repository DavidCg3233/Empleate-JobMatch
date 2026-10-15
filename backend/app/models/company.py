from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    tax_id: Mapped[str] = mapped_column(String(30), unique=True)  # NIT
    industry_id: Mapped[int] = mapped_column(ForeignKey("industries.id"))
    size: Mapped[str] = mapped_column(
        Enum("1-10", "11-50", "51-200", "201-500", "501-1000", "1000+", name="company_size_enum")
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str] = mapped_column(String(150))
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())