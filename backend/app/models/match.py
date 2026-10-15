from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Match(Base):
    """Match = like del aspirante a la vacante + like de la empresa a ese aspirante."""

    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("job_id", "applicant_id", name="uq_matches"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicants.id", ondelete="CASCADE"))
    matched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
