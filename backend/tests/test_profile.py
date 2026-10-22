"""Perfil del aspirante, hoja de vida nueva, cambio de contraseña, sugerencias de habilidades y términos."""
from app import models as m
from app.config import settings
from tests.cv_samples import make_docx, make_pdf

PASSWORD = "Clave1234"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def register_applicant(client, email="laura@correo.com", **extra):
    payload = {"first_name": "Laura", "last_name": "Gómez", "email": email, "password": PASSWORD,
               "accept_terms": True, "city_id": 1}
    payload.update(extra)
    r = client.post("/api/auth/register/applicant", json=payload)
    assert r.status_code == 201, r.text
    return auth(r.json()["access_token"])


PROFILE = {
    "first_name": "Laura Marcela", "last_name": "Gómez Ríos", "phone": "300 123 4567", "city_id": 2,
    "desired_position": "Desarrolladora Backend", "summary": "Me gusta construir APIs.",
    "search_status": "buscando_empleo", "desired_salary_min": 4500000, "desired_modality": "remoto",
    "willing_to_relocate": True,
    "experiences": [{"position": "Desarrolladora", "company_name": "ACME", "start_date": "2021-03-01", "is_current": True}],
    "educations": [{"education_level_id": 4, "institution": "Univalle", "degree": "Ingeniería de Sistemas"}],
    "skills": ["python", "Docker", "comunicacion"],
    "languages": [{"language_id": 2, "proficiency": "avanzado"}],
}


# ---------------- Términos y condiciones ----------------
def test_register_requires_accepting_terms(client):
    base = {"first_name": "Ana", "last_name": "Ruiz", "email": "ana@correo.com", "password": PASSWORD}
    assert client.post("/api/auth/register/applicant", json=base).status_code == 422
    r = client.post("/api/auth/register/applicant", json={**base, "accept_terms": False})
    assert r.status_code == 422 and "términos" in str(r.json()["detail"])
    company = {"name": "Otra", "tax_id": "900111222-3", "industry_id": 1, "size": "1-10", "city_id": 1,
               "contact_name": "Leo", "email": "leo@otra.com", "password": PASSWORD}
    assert client.post("/api/auth/register/company", json=company).status_code == 422
    r = client.post("/api/auth/register/company", json={**company, "accept_terms": True, "contact_email": "Contacto@Otra.com"})
    assert r.status_code == 201


# ---------------- Perfil ----------------
def test_profile_read_and_full_update(client, db_session):
    headers = register_applicant(client, skills=["Excel"])
    profile = client.get("/api/applicant/profile", headers=headers).json()
    assert profile["first_name"] == "Laura" and profile["account_email"] == "laura@correo.com"
    assert profile["skills"] == ["Excel"] and profile["cv"] is None and profile["search_status"] == "buscando_empleo"

    r = client.put("/api/applicant/profile", json=PROFILE, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["first_name"] == "Laura Marcela" and body["city_id"] == 2
    assert body["desired_salary_min"] == 4500000 and body["desired_modality"] == "remoto" and body["willing_to_relocate"]
    # Habilidades con el nombre del catálogo y sin duplicados; la anterior ("Excel") se quitó
    assert body["skills"] == ["Comunicación", "Docker", "Python"]
    assert len(body["experiences"]) == 1 and body["experiences"][0]["company_name"] == "ACME"
    assert body["languages"] == [{"language_id": 2, "proficiency": "avanzado"}]
    assert body["profile_completed"] is True

    # Guardar dos veces no duplica nada
    client.put("/api/applicant/profile", json=PROFILE, headers=headers)
    with db_session() as db:
        assert db.query(m.ApplicantExperience).count() == 1
        assert db.query(m.ApplicantSkill).count() == 3


def test_profile_search_status_hides_from_company_suggestions(client):
    headers = register_applicant(client)
    r = client.put("/api/applicant/profile", json={**PROFILE, "search_status": "sin_busqueda_activa"}, headers=headers)
    assert r.json()["search_status"] == "sin_busqueda_activa"


def test_profile_validation(client):
    headers = register_applicant(client)
    assert client.put("/api/applicant/profile", json={**PROFILE, "city_id": 999}, headers=headers).status_code == 400
    bad_edu = [{"education_level_id": 99, "institution": "U", "degree": "Ing"}]
    assert client.put("/api/applicant/profile", json={**PROFILE, "educations": bad_edu}, headers=headers).status_code == 422
    bad_edu = [{"education_level_id": 99, "institution": "Univalle", "degree": "Ingeniería"}]
    assert client.put("/api/applicant/profile", json={**PROFILE, "educations": bad_edu}, headers=headers).status_code == 400
    assert client.put("/api/applicant/profile", json={**PROFILE, "desired_salary_min": -5}, headers=headers).status_code == 422
    assert client.put("/api/applicant/profile", json={**PROFILE, "phone": "abc"}, headers=headers).status_code == 422
    assert client.put("/api/applicant/profile", json={**PROFILE, "first_name": ""}, headers=headers).status_code == 422
    empty_optional = {**PROFILE, "phone": "", "desired_salary_min": "", "desired_modality": "", "summary": "  "}
    body = client.put("/api/applicant/profile", json=empty_optional, headers=headers).json()
    assert body["phone"] is None and body["desired_salary_min"] is None and body["summary"] is None


def test_only_applicants_have_a_profile(client):
    r = client.post("/api/auth/register/company", json={
        "name": "Otra", "tax_id": "900111222-3", "industry_id": 1, "size": "1-10", "city_id": 1,
        "contact_name": "Leo", "email": "leo@otra.com", "password": PASSWORD, "accept_terms": True,
    })
    company = auth(r.json()["access_token"])
    assert client.get("/api/applicant/profile", headers=company).status_code == 403
    assert client.get("/api/applicant/profile").status_code == 401


# ---------------- Hoja de vida nueva ----------------
def test_upload_new_cv_replaces_file_but_not_profile(client, db_session):
    headers = register_applicant(client)
    client.put("/api/applicant/profile", json=PROFILE, headers=headers)

    r = client.post("/api/applicant/cv", files={"file": ("Mi CV 2026.docx", make_docx(), "application/octet-stream")}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cv"]["original_name"] == "Mi CV 2026.docx" and body["source"] == "basico"
    assert body["data"]["email"] == "laura.gomez@correo.com" and "Python" in body["data"]["skills"]

    # El perfil no cambia hasta que la persona guarde
    profile = client.get("/api/applicant/profile", headers=headers).json()
    assert profile["first_name"] == "Laura Marcela" and profile["cv"]["original_name"] == "Mi CV 2026.docx"
    with db_session() as db:
        first_path = db.query(m.Applicant).one().cv_path
    assert (settings.UPLOAD_DIR / first_path).exists()

    # Subir otra reemplaza el archivo anterior (y lo borra del disco)
    r = client.post("/api/applicant/cv", files={"file": ("cv.pdf", make_pdf(), "application/pdf")}, headers=headers)
    assert r.status_code == 200
    with db_session() as db:
        applicant = db.query(m.Applicant).one()
        assert applicant.cv_path != first_path and applicant.cv_original_name == "cv.pdf"
        assert "Soluciones Andinas" in applicant.cv_text
    assert not (settings.UPLOAD_DIR / first_path).exists()

    download = client.get("/api/applicant/cv", headers=headers)
    assert download.status_code == 200 and download.content.startswith(b"%PDF")
    assert "cv.pdf" in download.headers["content-disposition"]


def test_upload_invalid_cv(client):
    headers = register_applicant(client)
    assert client.get("/api/applicant/cv", headers=headers).status_code == 404
    r = client.post("/api/applicant/cv", files={"file": ("cv.doc", b"\xd0\xcf\x11\xe0", "application/msword")}, headers=headers)
    assert r.status_code == 400 and ".doc" in r.json()["detail"]["message"]
    r = client.post("/api/applicant/cv", files={"file": ("cv.pdf", make_pdf(["Hola"]), "application/pdf")}, headers=headers)
    assert r.status_code == 422


# ---------------- Contraseña ----------------
def test_change_password(client):
    headers = register_applicant(client)

    def change(current, new):
        return client.post("/api/auth/change-password", json={"current_password": current, "new_password": new}, headers=headers)

    assert change("Incorrecta1", "NuevaClave9").status_code == 400
    assert change(PASSWORD, PASSWORD).status_code == 400  # debe ser diferente
    assert change(PASSWORD, "corta").status_code == 422
    assert change(PASSWORD, "NuevaClave9").status_code == 200
    assert client.post("/api/auth/login", json={"email": "laura@correo.com", "password": "NuevaClave9"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "laura@correo.com", "password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/change-password", json={"current_password": "x", "new_password": "NuevaClave9"}).status_code == 401


# ---------------- Sugerencias de habilidades ----------------
def test_skill_suggestions(client):
    def names(q, **params):
        r = client.get("/api/catalogs/skills", params={"q": q, **params})
        assert r.status_code == 200, r.text
        return [s["name"] for s in r.json()]

    assert names("pyt")[0] == "Python"
    assert names("comunicacion")[:2] == ["Comunicación", "Comunicación asertiva"]  # sin tilde también
    assert names("EXCEL")[:2] == ["Excel", "Excel avanzado"]
    assert len(names("a", limit=3)) == 3
    categories = {s["name"]: s["category"] for s in client.get("/api/catalogs/skills", params={"q": "doc"}).json()}
    assert categories["Docker"] == "herramienta"
    assert client.get("/api/catalogs/skills", params={"q": ""}).status_code == 422

    # Una habilidad escrita por un usuario solo se sugiere si alguien la usa
    register_applicant(client, "otro@correo.com", skills=["Repostería artesanal"])
    assert names("reposter") == ["Repostería artesanal"]
    assert names("zzzz") == []
