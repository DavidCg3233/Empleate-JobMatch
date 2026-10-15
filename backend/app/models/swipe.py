from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

SWIPE_ACTIONS = ("like", "dislike")


class ApplicantSwipe(Base):
    """El aspirante desliza una vacante (like = me interesa, dislike = no me interesa)."""

    __tablename__ = "applicant_swipes"
    __table_args__ = (UniqueConstraint("applicant_id", "job_id", name="uq_applicant_swipes"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicants.id", ondelete="CASCADE"))
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(Enum(*SWIPE_ACTIONS, name="swipe_action_enum"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CompanySwipe(Base):
    """La empresa desliza a un aspirante para una vacante concreta."""

    __tablename__ = "company_swipes"
    __table_args__ = (UniqueConstraint("job_id", "applicant_id", name="uq_company_swipes"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    applicant_id: Mapped[int] = mapped_column(ForeignKey("applicants.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(Enum(*SWIPE_ACTIONS, name="swipe_action_enum"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
