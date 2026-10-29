"""Eliminar mi cuenta (derecho de supresión, Ley 1581 de 2012).

Borra la cuenta y TODOS los datos personales asociados: perfil, hoja de vida (también el archivo),
decisiones, matches y análisis de la IA. Si es una empresa, también sus vacantes.
Los borrados se hacen uno por uno (sin depender del ON DELETE CASCADE de MySQL) para que funcionen igual en las pruebas.
La bitácora se conserva, pero sin enlazar a la persona (user_id queda en NULL).
"""
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import api_error
from app.core.security import verify_password
from app.models.applicant import Applicant
from app.models.applicant_profile import ApplicantEducation, ApplicantExperience, ApplicantLanguage, ApplicantSkill
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.job import Job, JobSkill
from app.models.match import Match
from app.models.match_score import ApplicantEmbedding, JobEmbedding, MatchScore
from app.models.password_reset import PasswordReset
from app.models.swipe import ApplicantSwipe, CompanySwipe
from app.models.user import User
from app.services import audit_service, storage_service


def _delete_applicant(db: Session, applicant: Applicant) -> None:
    aid = applicant.id
    for model in (ApplicantExperience, ApplicantEducation, ApplicantSkill, ApplicantLanguage,
                  ApplicantSwipe, CompanySwipe, Match, MatchScore, ApplicantEmbedding):
        db.execute(delete(model).where(model.applicant_id == aid))
    db.delete(applicant)


def _delete_company(db: Session, company: Company) -> int:
    job_ids = list(db.scalars(select(Job.id).where(Job.company_id == company.id)))
    if job_ids:
        for model in (JobSkill, ApplicantSwipe, CompanySwipe, Match, MatchScore, JobEmbedding):
            db.execute(delete(model).where(model.job_id.in_(job_ids)))
        db.execute(delete(Job).where(Job.id.in_(job_ids)).execution_options(synchronize_session=False))
    db.delete(company)
    return len(job_ids)


def delete_account(db: Session, user: User, password: str) -> None:
    role = user.role.name
    if role not in ("aspirante", "empresa"):
        raise api_error(403, "Las cuentas de administrador no se eliminan desde aquí.")
    if not verify_password(password, user.password_hash):
        raise api_error(400, "La contraseña no es correcta.")

    cv_path = None
    details: dict = {"rol": role}
    if role == "aspirante":
        applicant = db.scalar(select(Applicant).where(Applicant.user_id == user.id))
        if applicant is not None:
            cv_path = applicant.cv_path
            _delete_applicant(db, applicant)
    else:
        company = db.scalar(select(Company).where(Company.user_id == user.id))
        if company is not None:
            details["vacantes"] = _delete_company(db, company)

    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    db.execute(update(AuditLog).where(AuditLog.user_id == user.id).values(user_id=None))
    audit_service.record(db, "cuenta_eliminada", None, "user", user.id, details)  # sin correo ni nombre
    db.delete(user)
    db.commit()

    storage_service.delete_upload(cv_path)  # el archivo se borra solo si lo anterior se guardó
