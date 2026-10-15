"""Configuración de pruebas: base de datos SQLite en memoria (no toca MySQL),
carpeta de archivos temporal y correos capturados en una lista."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as m
from app.config import settings
from app.controllers import auth_controller
from app.database import Base, get_db
from app.services import email_service
from main import app

# test_db.py es un script manual para probar MySQL (python tests/test_db.py), no una prueba de pytest
collect_ignore = ["test_db.py"]


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session() as s:  # mismos datos iniciales que el script SQL
        s.add_all([m.Role(id=1, name="aspirante"), m.Role(id=2, name="empresa"), m.Role(id=3, name="administrador")])
        s.add_all([m.Department(id=1, name="Valle del Cauca"), m.Department(id=2, name="Bogotá D.C.")])
        s.add_all([m.City(id=1, department_id=1, name="Cali"), m.City(id=2, department_id=2, name="Bogotá")])
        s.add(m.Industry(id=1, name="Tecnología"))
        levels = ["Bachillerato", "Técnico", "Tecnólogo", "Pregrado", "Especialización", "Maestría", "Doctorado"]
        s.add_all([m.EducationLevel(id=i, name=n, rank_order=i) for i, n in enumerate(levels, 1)])
        s.add_all([m.Language(id=1, name="Español"), m.Language(id=2, name="Inglés")])
        s.add_all([m.ContractType(id=1, name="Término indefinido"), m.ContractType(id=2, name="Término fijo")])
        s.commit()

    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "AI_PROVIDER", "none")
    yield Session


@pytest.fixture()
def sent_emails(monkeypatch):
    outbox = []
    monkeypatch.setattr(
        email_service, "send_email", lambda to, subject, text, html=None: outbox.append({"to": to, "text": text})
    )
    return outbox


@pytest.fixture()
def client(db_session, sent_emails):
    def override_get_db():
        db = db_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    for limiter in (auth_controller.cv_limiter, auth_controller.forgot_limiter):
        limiter._hits.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
