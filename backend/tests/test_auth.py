"""Flujos completos de autenticación contra la API (SQLite en memoria)."""
import re
from datetime import datetime, timedelta

from app import models as m
from app.config import settings
from tests.cv_samples import make_docx

PASSWORD = "Clave1234"


def register_company(client, **overrides):
    payload = {
        "name": "Talento Andino", "tax_id": "900.123.456-7", "industry_id": 1, "size": "11-50",
        "city_id": 2, "contact_name": "Ana Ruiz", "email": "rrhh@talento.com", "password": PASSWORD, "accept_terms": True,
    }
    payload.update(overrides)
    return client.post("/api/auth/register/company", json=payload)


def register_applicant(client, **overrides):
    payload = {"first_name": "Pedro", "last_name": "Pérez", "email": "pedro@correo.com",
               "password": PASSWORD, "accept_terms": True, "city_id": 1}
    payload.update(overrides)
    return client.post("/api/auth/register/applicant", json=payload)


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


# ---------------- Registro con hoja de vida ----------------
def test_cv_parse_then_register_applicant(client, db_session):
    files = {"file": ("mi_cv.docx", make_docx(), "application/octet-stream")}
    r = client.post("/api/auth/cv/parse", files=files)
    assert r.status_code == 200, r.text
    parsed = r.json()
    data = parsed["data"]
    assert parsed["source"] == "basico" and parsed["original_name"] == "mi_cv.docx"
    assert (data["first_name"], data["email"], data["city_id"]) == ("Laura Marcela", "laura.gomez@correo.com", 1)

    # El formulario se envía con los datos autocompletados (igual que registerController.js)
    payload = {
        "first_name": data["first_name"], "last_name": data["last_name"], "email": data["email"],
        "password": PASSWORD, "accept_terms": True, "phone": data["phone"], "city_id": data["city_id"],
        "cv_upload_id": parsed["cv_upload_id"], "desired_position": data["desired_position"],
        "summary": data["summary"], "skills": data["skills"] + ["python"],  # duplicado a propósito
        "experiences": data["experiences"], "educations": data["educations"], "languages": data["languages"],
    }
    r = client.post("/api/auth/register/applicant", json=payload)
    assert r.status_code == 201, r.text
    assert r.json()["role"] == "aspirante"

    with db_session() as db:
        applicant = db.query(m.Applicant).one()
        assert applicant.cv_original_name == "mi_cv.docx"
        assert "Soluciones Andinas" in applicant.cv_text
        assert applicant.cv_parsed_at is not None and applicant.profile_completed
        assert (settings.UPLOAD_DIR / applicant.cv_path).exists()
        assert db.query(m.ApplicantExperience).count() == 2
        assert db.query(m.ApplicantEducation).count() == 1
        assert db.query(m.ApplicantLanguage).count() == 2
        skills = [s.name for s in db.query(m.Skill)]
        assert "Python" in skills and len(skills) == len({s.lower() for s in skills})

    # El id temporal ya se usó: no sirve para otra cuenta
    r = register_applicant(client, email="otro@correo.com", cv_upload_id=parsed["cv_upload_id"])
    assert r.status_code == 400


def test_cv_parse_rejects_invalid_files(client):
    r = client.post("/api/auth/cv/parse", files={"file": ("cv.exe", b"MZ...", "application/octet-stream")})
    assert r.status_code == 400
    r = client.post("/api/auth/cv/parse", files={"file": ("foto.jpg", b"\xff\xd8\xff", "image/jpeg")})
    assert r.status_code == 400 and "imagen" in r.json()["detail"]["message"]
    r = client.post("/api/auth/cv/parse", files={"file": ("cv.txt", b"hola", "text/plain")})
    assert r.status_code == 422  # .txt sí se acepta, pero no tiene texto suficiente
    r = client.post("/api/auth/cv/parse", files={"file": ("cv.pdf", b"PK\x03\x04falso", "application/pdf")})
    assert r.status_code == 400
    big = b"%PDF" + b"0" * (settings.MAX_CV_MB * 1024 * 1024)
    r = client.post("/api/auth/cv/parse", files={"file": ("cv.pdf", big, "application/pdf")})
    assert r.status_code == 413


def test_register_applicant_without_cv_and_duplicate_email(client):
    assert register_applicant(client).status_code == 201
    assert register_applicant(client, email="PEDRO@correo.com").status_code == 409


def test_register_applicant_validates_profile(client):
    bad_exp = {"position": "Dev", "company_name": "ACME", "start_date": "2022-05-01", "end_date": "2021-01-01"}
    assert register_applicant(client, experiences=[bad_exp]).status_code == 422
    bad_edu = {"education_level_id": 99, "institution": "Univalle", "degree": "Ingeniería"}
    assert register_applicant(client, educations=[bad_edu]).status_code == 400
    assert register_applicant(client, password="solotexto").status_code == 422


def test_register_company_and_duplicate_tax_id(client, db_session):
    r = register_company(client)
    assert r.status_code == 201 and r.json()["role"] == "empresa"
    with db_session() as db:
        company = db.query(m.Company).one()
        assert company.tax_id == "900123456-7" and company.contact_email == "rrhh@talento.com"
    assert register_company(client, email="otro@talento.com", tax_id="900123456-7").status_code == 409


# ---------------- Login y sesión ----------------
def test_login_returns_role_and_me(client):
    register_company(client)
    r = login(client, "RRHH@talento.com", PASSWORD)
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "empresa"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["display_name"] == "Talento Andino"
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer basura"}).status_code == 401


def test_login_locks_after_max_attempts(client):
    register_applicant(client)
    r = login(client, "pedro@correo.com", "Incorrecta1")
    assert r.status_code == 401
    assert r.json()["detail"]["remaining_attempts"] == settings.MAX_LOGIN_ATTEMPTS - 1
    for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
        r = login(client, "pedro@correo.com", "Incorrecta1")
    assert r.status_code == 423
    # Sigue bloqueada aunque ahora escriba la contraseña correcta
    assert login(client, "pedro@correo.com", PASSWORD).status_code == 423


def test_login_unknown_email_gives_generic_error(client):
    r = login(client, "nadie@correo.com", PASSWORD)
    assert r.status_code == 401
    assert r.json()["detail"]["message"] == "Correo o contraseña incorrectos."


# ---------------- Recuperación de contraseña ----------------
def _token_from(email_text: str) -> str:
    return re.search(r"token=([\w-]+)", email_text).group(1)


def test_password_reset_full_flow(client, sent_emails):
    register_applicant(client)
    # Se bloquea la cuenta para comprobar que restablecer la contraseña la desbloquea
    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        login(client, "pedro@correo.com", "Incorrecta1")

    assert client.post("/api/auth/forgot-password", json={"email": "pedro@correo.com"}).status_code == 200
    assert len(sent_emails) == 1 and sent_emails[0]["to"] == "pedro@correo.com"
    token = _token_from(sent_emails[0]["text"])

    assert client.get("/api/auth/reset-password/validate", params={"token": token}).status_code == 200
    r = client.post("/api/auth/reset-password", json={"token": token, "password": "NuevaClave99"})
    assert r.status_code == 200

    # El enlace es de un solo uso
    r = client.post("/api/auth/reset-password", json={"token": token, "password": "OtraClave11"})
    assert r.status_code == 400
    assert login(client, "pedro@correo.com", PASSWORD).status_code == 401
    r = login(client, "pedro@correo.com", "NuevaClave99")
    assert r.status_code == 200 and r.json()["role"] == "aspirante"


def test_forgot_password_same_answer_for_unknown_email(client, sent_emails):
    register_applicant(client)
    known = client.post("/api/auth/forgot-password", json={"email": "pedro@correo.com"}).json()
    unknown = client.post("/api/auth/forgot-password", json={"email": "nadie@correo.com"}).json()
    assert known == unknown
    assert len(sent_emails) == 1


def test_new_reset_link_invalidates_previous_one(client, sent_emails):
    register_applicant(client)
    client.post("/api/auth/forgot-password", json={"email": "pedro@correo.com"})
    client.post("/api/auth/forgot-password", json={"email": "pedro@correo.com"})
    old, new = (_token_from(e["text"]) for e in sent_emails)
    assert client.get("/api/auth/reset-password/validate", params={"token": old}).status_code == 400
    assert client.get("/api/auth/reset-password/validate", params={"token": new}).status_code == 200


def test_expired_reset_link(client, sent_emails, db_session):
    register_applicant(client)
    client.post("/api/auth/forgot-password", json={"email": "pedro@correo.com"})
    with db_session() as db:
        reset = db.query(m.PasswordReset).one()
        reset.expires_at = datetime.now() - timedelta(minutes=1)
        db.commit()
    token = _token_from(sent_emails[0]["text"])
    r = client.post("/api/auth/reset-password", json={"token": token, "password": "NuevaClave99"})
    assert r.status_code == 400 and "venció" in r.json()["detail"]["message"]
