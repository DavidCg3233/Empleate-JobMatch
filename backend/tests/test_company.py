"""Módulo de empresa: perfil, CRUD de vacantes, candidatos, decisiones, matches y hoja de vida."""
from datetime import date, timedelta

import pytest

from app import models as m
from tests.cv_samples import make_docx

PASSWORD = "Clave1234"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def register_company(client, email="rrhh@andino.com", tax_id="900123456-7", name="Talento Andino"):
    r = client.post("/api/auth/register/company", json={
        "name": name, "tax_id": tax_id, "industry_id": 1, "size": "11-50", "city_id": 1,
        "contact_name": "Ana Ruiz", "email": email, "password": PASSWORD, "accept_terms": True,
    })
    assert r.status_code == 201, r.text
    return auth(r.json()["access_token"])


def register_applicant(client, email, first="Laura", last="Gómez", skills=("Python", "SQL"), **extra):
    payload = {"first_name": first, "last_name": last, "email": email, "password": PASSWORD, "accept_terms": True, "city_id": 1,
               "phone": "300 123 4567", "skills": list(skills)}
    payload.update(extra)
    r = client.post("/api/auth/register/applicant", json=payload)
    assert r.status_code == 201, r.text
    return auth(r.json()["access_token"])


JOB = {
    "title": "Desarrollador Backend Python",
    "description": "Construirás APIs REST con FastAPI y bases de datos MySQL para nuestros clientes.",
    "requirements": "Dos años con Python.",
    "modality": "presencial", "city_id": 1, "contract_type_id": 1, "min_education_id": 4,
    "min_experience_years": 0, "salary_min": 4_000_000, "salary_max": 6_000_000, "currency": "COP",
    "skills": [{"name": "Python", "is_required": True}, {"name": "Docker", "is_required": False}],
}


def create_job(client, headers, **overrides):
    r = client.post("/api/company/jobs", json={**JOB, **overrides}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def applicant_id(db_session, email):
    with db_session() as db:
        user = db.query(m.User).filter_by(email=email).one()
        return db.query(m.Applicant).filter_by(user_id=user.id).one().id


# =====================================================================
# Perfil
# =====================================================================
def test_company_profile_read_and_update(client):
    headers = register_company(client)
    profile = client.get("/api/company/profile", headers=headers).json()
    assert profile["name"] == "Talento Andino" and profile["tax_id"] == "900123456-7"
    assert profile["industry"] == "Tecnología" and profile["city"] == "Cali"
    assert profile["account_email"] == "rrhh@andino.com"

    update = {
        "name": "Talento Andino S.A.S.", "industry_id": 1, "size": "51-200", "city_id": 2,
        "description": "Consultoría de software.", "address": "Calle 10 # 5-20", "website": "andino.co",
        "contact_name": "Mario Paz", "contact_phone": "+57 310 000 0000", "contact_email": "Seleccion@Andino.com",
        "tax_id": "111", "account_email": "otro@x.com",  # se ignoran: no se pueden cambiar
    }
    r = client.put("/api/company/profile", json=update, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Talento Andino S.A.S." and body["city"] == "Bogotá" and body["size"] == "51-200"
    assert body["website"] == "https://andino.co" and body["contact_email"] == "seleccion@andino.com"
    assert body["tax_id"] == "900123456-7" and body["account_email"] == "rrhh@andino.com"

    assert client.put("/api/company/profile", json={**update, "industry_id": 99}, headers=headers).status_code == 400
    assert client.put("/api/company/profile", json={**update, "contact_phone": "abc"}, headers=headers).status_code == 422
    assert client.put("/api/company/profile", json={**update, "name": ""}, headers=headers).status_code == 422


def test_only_companies_use_company_routes(client):
    headers = register_applicant(client, "laura@correo.com")
    assert client.get("/api/company/profile", headers=headers).status_code == 403
    assert client.get("/api/company/jobs", headers=headers).status_code == 403
    assert client.post("/api/swipes/candidates", json={"job_id": 1, "applicant_id": 1, "action": "like"},
                       headers=headers).status_code == 403
    assert client.get("/api/matches/company", headers=headers).status_code == 403
    assert client.get("/api/company/jobs").status_code == 401


# =====================================================================
# Vacantes: crear, validar, listar
# =====================================================================
def test_create_job_published_or_paused(client):
    headers = register_company(client)
    active = create_job(client, headers)
    assert active["status"] == "activa" and active["is_visible"] and active["published_at"]
    assert active["city"] == "Cali" and active["contract_type"] == "Término indefinido"
    assert active["min_education"] == "Pregrado" and active["can_delete"] is True
    assert active["skills"] == [{"name": "Python", "is_required": True}, {"name": "Docker", "is_required": False}]
    assert active["stats"] == {"interested": 0, "pending": 0, "matches": 0}

    paused = create_job(client, headers, title="Analista QA", status="pausada")
    assert paused["status"] == "pausada" and not paused["is_visible"] and paused["published_at"] is None

    jobs = client.get("/api/company/jobs", headers=headers).json()
    assert [j["id"] for j in jobs] == [paused["id"], active["id"]]  # la más reciente primero


def test_job_validations(client):
    headers = register_company(client)

    def post(**overrides):
        return client.post("/api/company/jobs", json={**JOB, **overrides}, headers=headers)

    assert post(title="ab").status_code == 422
    assert post(description="muy corta").status_code == 422
    assert post(city_id=None).status_code == 422  # presencial sin ciudad
    assert post(salary_min=5_000_000, salary_max=1_000_000).status_code == 422
    assert post(closes_at=str(date.today() - timedelta(days=1))).status_code == 422
    assert post(min_experience_years=-1).status_code == 422
    assert post(currency="EUR").status_code == 422
    assert post(contract_type_id=99).status_code == 400
    assert post(min_education_id=99).status_code == 400
    assert post(city_id=999).status_code == 400

    remote = post(modality="remoto", city_id=1).json()
    assert remote["city_id"] is None and remote["city"] is None  # remoto = sin ciudad

    deduped = post(skills=[{"name": "python", "is_required": False}, {"name": "Python ", "is_required": True},
                           {"name": "  Excel   avanzado ", "is_required": False}]).json()
    # "Python" ya existe en el catálogo de habilidades: se reutiliza con su nombre original
    assert deduped["skills"] == [{"name": "Python", "is_required": True},
                                 {"name": "Excel avanzado", "is_required": False}]

    optional = post(requirements="", salary_min="", salary_max="", min_education_id="", closes_at="").json()
    assert optional["requirements"] is None and optional["salary_min"] is None and optional["min_education_id"] is None


def test_company_cannot_see_or_edit_other_company_jobs(client):
    owner = register_company(client)
    job = create_job(client, owner)
    other = register_company(client, "rrhh@otra.com", "800111222-3", "Otra")
    assert client.get(f"/api/company/jobs/{job['id']}", headers=other).status_code == 404
    assert client.put(f"/api/company/jobs/{job['id']}", json=JOB, headers=other).status_code == 404
    assert client.patch(f"/api/company/jobs/{job['id']}/status", json={"status": "cerrada"}, headers=other).status_code == 404
    assert client.delete(f"/api/company/jobs/{job['id']}", headers=other).status_code == 404
    assert client.get(f"/api/company/jobs/{job['id']}/candidates", headers=other).status_code == 404
    assert client.get("/api/company/jobs", headers=other).json() == []


# =====================================================================
# Vacantes: editar, estado y eliminar
# =====================================================================
def test_update_job_syncs_skills(client, db_session):
    headers = register_company(client)
    job = create_job(client, headers)
    r = client.put(f"/api/company/jobs/{job['id']}", headers=headers, json={
        **JOB, "title": "Backend Senior", "modality": "hibrido",
        "skills": [{"name": "Docker", "is_required": True}, {"name": "AWS", "is_required": False}],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Backend Senior" and body["modality"] == "hibrido"
    assert body["skills"] == [{"name": "Docker", "is_required": True}, {"name": "AWS", "is_required": False}]
    assert body["status"] == "activa"  # editar no cambia el estado
    with db_session() as db:
        assert db.query(m.JobSkill).filter_by(job_id=job["id"]).count() == 2

    # Volver a enviar las mismas habilidades no rompe nada
    again = client.put(f"/api/company/jobs/{job['id']}", headers=headers, json={**JOB, "skills": body["skills"]})
    assert again.status_code == 200


def test_status_changes(client, db_session):
    headers = register_company(client)
    job = create_job(client, headers)
    applicant = register_applicant(client, "laura@correo.com")

    def feed_ids():
        return {j["id"] for j in client.get("/api/jobs/feed", headers=applicant).json()["items"]}

    def set_status(status):
        return client.patch(f"/api/company/jobs/{job['id']}/status", json={"status": status}, headers=headers)

    assert job["id"] in feed_ids()
    assert set_status("pausada").json()["is_visible"] is False
    assert job["id"] not in feed_ids()  # pausada: los aspirantes no la ven
    first_published = job["published_at"]
    reactivated = set_status("activa").json()
    assert reactivated["is_visible"] and reactivated["published_at"] == first_published
    assert set_status("cerrada").json()["status"] == "cerrada"
    assert job["id"] not in feed_ids()
    assert set_status("activa").status_code == 200  # se puede reabrir
    assert set_status("borrador").status_code == 422

    # Fecha de cierre vencida: hay que editarla antes de publicar
    set_status("pausada")
    with db_session() as db:
        db.get(m.Job, job["id"]).closes_at = date.today() - timedelta(days=1)
        db.commit()
    r = set_status("activa")
    assert r.status_code == 409 and "fecha de cierre" in r.json()["detail"]["message"]
    listed = client.get(f"/api/company/jobs/{job['id']}", headers=headers).json()
    assert listed["is_expired"] is True

    # Deshabilitada por el administrador
    with db_session() as db:
        db_job = db.get(m.Job, job["id"])
        db_job.closes_at, db_job.is_enabled = None, False
        db.commit()
    assert set_status("activa").status_code == 409


def test_paused_job_first_publication_sets_date(client):
    headers = register_company(client)
    job = create_job(client, headers, status="pausada")
    published = client.patch(f"/api/company/jobs/{job['id']}/status", json={"status": "activa"}, headers=headers).json()
    assert published["published_at"] is not None


def test_delete_only_untouched_jobs(client):
    headers = register_company(client)
    untouched = create_job(client, headers)
    assert client.delete(f"/api/company/jobs/{untouched['id']}", headers=headers).status_code == 200
    assert client.get(f"/api/company/jobs/{untouched['id']}", headers=headers).status_code == 404

    touched = create_job(client, headers)
    applicant = register_applicant(client, "laura@correo.com")
    client.post("/api/swipes/jobs", json={"job_id": touched["id"], "action": "dislike"}, headers=applicant)
    assert client.get(f"/api/company/jobs/{touched['id']}", headers=headers).json()["can_delete"] is False
    r = client.delete(f"/api/company/jobs/{touched['id']}", headers=headers)
    assert r.status_code == 409 and "cerrarla" in r.json()["detail"]["message"]


# =====================================================================
# Candidatos
# =====================================================================
@pytest.fixture()
def hiring(client, db_session):
    """Empresa con una vacante y cuatro aspirantes en distintas situaciones."""
    company = register_company(client)
    job = create_job(client, company)
    interested = register_applicant(client, "interesada@correo.com", "Laura", "Gómez")
    register_applicant(client, "sugerido@correo.com", "Pedro", "Pérez", skills=("Python",))
    rejecter = register_applicant(client, "rechaza@correo.com", "Ana", "Ruiz")
    register_applicant(client, "pasivo@correo.com", "Luis", "Mora")
    with db_session() as db:  # este aspirante no está buscando empleo
        db.get(m.Applicant, applicant_id(db_session, "pasivo@correo.com")).search_status = "sin_busqueda_activa"
        db.commit()

    client.post("/api/swipes/jobs", json={"job_id": job["id"], "action": "like"}, headers=interested)
    client.post("/api/swipes/jobs", json={"job_id": job["id"], "action": "dislike"}, headers=rejecter)
    ids = {key: applicant_id(db_session, f"{key}@correo.com") for key in ("interesada", "sugerido", "rechaza", "pasivo")}
    return {"company": company, "job": job, "interested": interested, "ids": ids}


def test_candidates_order_and_privacy(client, hiring):
    r = client.get(f"/api/company/jobs/{hiring['job']['id']}/candidates", headers=hiring["company"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job_title"] == JOB["title"]
    items = body["items"]
    # Interesada primero, luego el sugerido; nunca quien descartó la vacante ni quien no busca empleo
    assert [c["applicant_id"] for c in items] == [hiring["ids"]["interesada"], hiring["ids"]["sugerido"]]

    first = items[0]
    assert first["interested"] is True and items[1]["interested"] is False
    assert first["display_name"] == "Laura G."  # sin apellido completo antes del match
    assert "email" not in first and "phone" not in first
    assert {"name": "Python", "matched": True} in first["skills"]
    assert first["skills"][0]["matched"] is True  # las que pide la vacante, primero
    assert any(reason.startswith("Tiene 1 de 1 habilidades requeridas") for reason in first["score_reasons"])

    only = client.get(f"/api/company/jobs/{hiring['job']['id']}/candidates", params={"only_interested": True},
                      headers=hiring["company"]).json()["items"]
    assert [c["applicant_id"] for c in only] == [hiring["ids"]["interesada"]]

    excluded = client.get(f"/api/company/jobs/{hiring['job']['id']}/candidates",
                          params={"exclude": hiring["ids"]["interesada"]}, headers=hiring["company"]).json()["items"]
    assert [c["applicant_id"] for c in excluded] == [hiring["ids"]["sugerido"]]


def test_closed_job_has_no_candidates(client, hiring):
    job_id = hiring["job"]["id"]
    client.patch(f"/api/company/jobs/{job_id}/status", json={"status": "cerrada"}, headers=hiring["company"])
    assert client.get(f"/api/company/jobs/{job_id}/candidates", headers=hiring["company"]).status_code == 409
    r = client.post("/api/swipes/candidates", headers=hiring["company"],
                    json={"job_id": job_id, "applicant_id": hiring["ids"]["interesada"], "action": "like"})
    assert r.status_code == 409


def test_paused_job_can_still_review_candidates(client, hiring):
    job_id = hiring["job"]["id"]
    client.patch(f"/api/company/jobs/{job_id}/status", json={"status": "pausada"}, headers=hiring["company"])
    assert client.get(f"/api/company/jobs/{job_id}/candidates", headers=hiring["company"]).status_code == 200


# =====================================================================
# Decisiones de la empresa y matches
# =====================================================================
def test_company_like_on_interested_applicant_creates_match(client, hiring):
    job_id, ids, company = hiring["job"]["id"], hiring["ids"], hiring["company"]
    r = client.post("/api/swipes/candidates", headers=company,
                    json={"job_id": job_id, "applicant_id": ids["interesada"], "action": "like"})
    assert r.status_code == 200 and r.json()["matched"] is True and r.json()["match_id"]

    # Ya no aparece en candidatos
    remaining = client.get(f"/api/company/jobs/{job_id}/candidates", headers=company).json()["items"]
    assert ids["interesada"] not in [c["applicant_id"] for c in remaining]

    # La empresa ve el match con nombre completo y contacto
    matches = client.get("/api/matches/company", headers=company).json()
    assert len(matches) == 1
    match = matches[0]
    assert match["job"]["title"] == JOB["title"]
    assert match["candidate"]["display_name"] == "Laura Gómez" and match["candidate"]["matched"] is True
    assert match["contact"] == {"full_name": "Laura Gómez", "email": "interesada@correo.com",
                                "phone": "300 123 4567", "has_cv": False}

    # El aspirante también lo ve en sus matches
    applicant_matches = client.get("/api/matches/applicant", headers=hiring["interested"]).json()["matches"]
    assert [mt["job"]["id"] for mt in applicant_matches] == [job_id]

    # Números de la vacante
    stats = client.get(f"/api/company/jobs/{job_id}", headers=company).json()["stats"]
    assert stats == {"interested": 1, "pending": 0, "matches": 1}

    # Con match no se puede descartar ni deshacer
    r = client.post("/api/swipes/candidates", headers=company,
                    json={"job_id": job_id, "applicant_id": ids["interesada"], "action": "dislike"})
    assert r.status_code == 409
    assert client.delete(f"/api/swipes/candidates/{job_id}/{ids['interesada']}", headers=company).status_code == 409

    # Filtro por vacante
    assert len(client.get("/api/matches/company", params={"job_id": job_id}, headers=company).json()) == 1


def test_company_likes_first_then_applicant_likes(client, hiring, db_session):
    """La empresa puede dar el primer paso con un perfil sugerido; el match llega cuando el aspirante dice que sí."""
    job_id, ids, company = hiring["job"]["id"], hiring["ids"], hiring["company"]
    r = client.post("/api/swipes/candidates", headers=company,
                    json={"job_id": job_id, "applicant_id": ids["sugerido"], "action": "like"})
    assert r.json()["matched"] is False

    login = client.post("/api/auth/login", json={"email": "sugerido@correo.com", "password": PASSWORD, "accept_terms": True}).json()
    r = client.post("/api/swipes/jobs", json={"job_id": job_id, "action": "like"}, headers=auth(login["access_token"]))
    assert r.json()["matched"] is True
    assert len(client.get("/api/matches/company", headers=company).json()) == 1


def test_company_dislike_and_undo(client, hiring):
    job_id, ids, company = hiring["job"]["id"], hiring["ids"], hiring["company"]
    r = client.post("/api/swipes/candidates", headers=company,
                    json={"job_id": job_id, "applicant_id": ids["interesada"], "action": "dislike"})
    assert r.json()["matched"] is False
    stats = client.get(f"/api/company/jobs/{job_id}", headers=company).json()["stats"]
    assert stats == {"interested": 1, "pending": 0, "matches": 0}

    assert client.delete(f"/api/swipes/candidates/{job_id}/{ids['interesada']}", headers=company).status_code == 200
    items = client.get(f"/api/company/jobs/{job_id}/candidates", headers=company).json()["items"]
    assert items[0]["applicant_id"] == ids["interesada"]
    assert client.delete(f"/api/swipes/candidates/{job_id}/{ids['interesada']}", headers=company).status_code == 404


def test_swipe_inactive_or_missing_applicant(client, hiring, db_session):
    job_id, company = hiring["job"]["id"], hiring["company"]
    r = client.post("/api/swipes/candidates", headers=company, json={"job_id": job_id, "applicant_id": 999, "action": "like"})
    assert r.status_code == 404
    with db_session() as db:
        user = db.query(m.User).filter_by(email="sugerido@correo.com").one()
        user.is_active = False
        db.commit()
    items = client.get(f"/api/company/jobs/{job_id}/candidates", headers=company).json()["items"]
    assert hiring["ids"]["sugerido"] not in [c["applicant_id"] for c in items]


# =====================================================================
# Hoja de vida
# =====================================================================
def test_cv_download_only_with_match(client, db_session):
    company = register_company(client)
    job = create_job(client, company)

    parsed = client.post("/api/auth/cv/parse", files={"file": ("Mi CV.docx", make_docx(), "application/octet-stream")}).json()
    applicant = register_applicant(client, "laura@correo.com", cv_upload_id=parsed["cv_upload_id"])
    client.post("/api/swipes/jobs", json={"job_id": job["id"], "action": "like"}, headers=applicant)
    aid = applicant_id(db_session, "laura@correo.com")

    match = client.post("/api/swipes/candidates", headers=company,
                        json={"job_id": job["id"], "applicant_id": aid, "action": "like"}).json()
    matches = client.get("/api/matches/company", headers=company).json()
    assert matches[0]["contact"]["has_cv"] is True

    r = client.get(f"/api/matches/{match['match_id']}/cv", headers=company)
    assert r.status_code == 200
    assert r.content == make_docx() or r.content[:2] == b"PK"
    assert "Mi%20CV.docx" in r.headers["content-disposition"] or "Mi CV.docx" in r.headers["content-disposition"]

    other = register_company(client, "rrhh@otra.com", "800111222-3", "Otra")
    assert client.get(f"/api/matches/{match['match_id']}/cv", headers=other).status_code == 404
    assert client.get("/api/matches/9999/cv", headers=company).status_code == 404


def test_cv_download_without_cv(client, hiring):
    job_id, ids, company = hiring["job"]["id"], hiring["ids"], hiring["company"]
    match = client.post("/api/swipes/candidates", headers=company,
                        json={"job_id": job_id, "applicant_id": ids["interesada"], "action": "like"}).json()
    r = client.get(f"/api/matches/{match['match_id']}/cv", headers=company)
    assert r.status_code == 404 and "no subió" in r.json()["detail"]["message"]
