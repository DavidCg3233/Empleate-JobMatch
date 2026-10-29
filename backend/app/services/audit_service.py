"""Bitácora de actividad (tabla audit_logs).

record() solo AGREGA el registro a la sesión: se guarda junto con la acción principal en el mismo commit,
así nunca queda una acción sin registro ni un registro de algo que no pasó.
No se guardan datos sensibles (contraseñas, tokens ni textos de hojas de vida).
"""
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record(
    db: Session,
    action: str,
    user_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: dict | None = None,
    ip: str | None = None,
) -> None:
    db.add(AuditLog(
        user_id=user_id, action=action[:60], entity_type=entity_type, entity_id=entity_id,
        details=details or None, ip_address=(ip or None) and ip[:45],
    ))
