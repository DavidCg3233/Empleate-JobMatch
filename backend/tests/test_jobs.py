"""Búsqueda de vacantes del aspirante: tarjetas, buscador, detalle, likes y matches."""
from datetime import date, datetime, timedelta

import pytest

from app import models as m
from app.core.security import hash_password

PASSWORD = "Clave1234"


# ---------------- Datos de prueba ----------------
def _skill(db, name):
    skill = db.query(m.Skill).filter_by(name=name).one_or_none()
    if skill is None:
        skill = m.Skill(name=name)
        db.add(skill)
        db.flush()
    return skill


def create_company(db, name="Talento Andino", tax_id="900123456-7", active=True):
    user = m.User(role_id=2, email=f"{tax_id}@empresa.com", password_hash=hash_password(PASSWORD), is_active=active)
    db.add(user)
    db.flush()
    company = m.Company(
        user_id=user.id, name=name, tax_id=tax_id, industry_id=1, size="11-50", city_id=2,
        contact_name="Ana", contact_email=user.email,
    )
    db.add(company)
    db.flush()
    return company


def create_job(db, company, title, required=(), desired=(), days_ago=0, **fields):
    data = {
        "description": f"Descripción de {title}", "modality": "presencial", "city_id": 1,
        "contract_type_id": 1, "status": "activa", "is_enabled": True,
        "published_at": datetime.now() - timedelta(days=days_ago),
    }
    data.update(fields)
    job = m.Job(company_id=company.id, title=title, **data)
    job.skills = [m.JobSkill(skill_id=_skill(db, s).id, is_required=True) for s in required] + [
        m.JobSkill(skill_id=_skill(db, s).id, is_required=False) for s in desired
    ]
    db.add(job)
    db.flush()
    return job


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def world(client, db_session):
    """Aspirante en Cali con Python/SQL y 3 años de experiencia + varias vacantes."""
    r = client.post("/api/auth/register/applicant", json={
        "first_name": "Laura", "last_name": "Gómez", "email": "laura@correo.com", "password": PASSWORD, "accept_terms": True,
        "city_id": 1, "skills": ["Python", "SQL"],
        "experiences": [{"position": "Dev", "company_name": "ACME", "start_date": "2021-01-01", "is_current": True}],
        "educations": [{"education_level_id": 4, "institution": "Univalle", "degree": "Ingeniería"}],
    })
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]

    with db_session() as db:
        andino = create_company(db)
        otra = create_company(db, "Logística Express", "800555111-2")
        jobs = {
            "backend": create_job(db, andino, "Desarrollador Backend Python", ["Python", "SQL"], ["Docker"],
                                  min_experience_years=2, min_education_id=4, salary_min=4_000_000,
                                  salary_max=6_000_000),
            "frontend": create_job(db, andino, "Desarrollador Frontend", ["React", "CSS"], days_ago=1,
                                   modality="remoto", city_id=None, contract_type_id=2),
            "bodega": create_job(db, otra, "Auxiliar de bodega", days_ago=2, city_id=2, salary_min=1_500_000),
            "cerrada": create_job(db, otra, "Vacante cerrada Python", ["Python"], status="cerrada"),
            "vencida": create_job(db, otra, "Vacante vencida Python", ["Python"],
                                  closes_at=date.today() - timedelta(days=1)),
            "oculta": create_job(db, otra, "Vacante deshabilitada Python", ["Python"], is_enabled=False),
        }
        db.commit()
        ids = {key: job.id for key, job in jobs.items()}
        applicant_id = db.query(m.Applicant).one().id
    return {"token": token, "ids": ids, "applicant_id": applicant_id}


# ---------------- Tarjetas ----------------
def test_feed_shows_only_open_jobs_sorted_by_score(client, world):
    r = client.get("/api/jobs/feed", headers=auth(world["token"]))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    ids = world["ids"]
    assert [j["id"] for j in items][0] == ids["backend"]  # la más compatible primero
    assert {j["id"] for j in items} == {ids["backend"], ids["frontend"], ids["bodega"]}
    scores = [j["score"] for j in items]
    assert scores == sorted(scores, reverse=True)

    backend = items[0]
    assert backend["score"] == 88  # 40 requeridas + 0 deseables + 15 exp + 10 edu + 15 ciudad + 5 + 3 salario
    assert backend["company"]["name"] == "Talento Andino" and backend["city"] == "Cali"
    assert {"name": "Python", "is_required": True, "matched": True} in backend["skills"]
    assert {"name": "Docker", "is_required": False, "matched": False} in backend["skills"]
    assert any("2 de 2 habilidades requeridas" in reason for reason in backend["score_reasons"])


def test_feed_filters_and_excludes(client, world):
    headers, ids = auth(world["token"]), world["ids"]
    remote = client.get("/api/jobs/feed", params={"modality": "remoto"}, headers=headers).json()["items"]
    assert [j["id"] for j in remote] == [ids["frontend"]]

    # Filtrar por Bogotá incluye las remotas, que sirven desde cualquier ciudad
    bogota = client.get("/api/jobs/feed", params={"city_id": 2}, headers=headers).json()["items"]
    assert {j["id"] for j in bogota} == {ids["frontend"], ids["bodega"]}

    rest = client.get("/api/jobs/feed", params=[("exclude", ids["backend"]), ("exclude", ids["bodega"])],
                      headers=headers).json()["items"]
    assert [j["id"] for j in rest] == [ids["frontend"]]


def test_swiped_jobs_leave_the_feed_and_undo_brings_them_back(client, world):
    headers, ids = auth(world["token"]), world["ids"]
    r = client.post("/api/swipes/jobs", json={"job_id": ids["bodega"], "action": "dislike"}, headers=headers)
    assert r.status_code == 200 and r.json() == {
        "job_id": ids["bodega"], "action": "dislike", "matched": False, "match_id": None,
    }
    feed_ids = {j["id"] for j in client.get("/api/jobs/feed", headers=headers).json()["items"]}
    assert ids["bodega"] not in feed_ids

    assert client.delete(f"/api/swipes/jobs/{ids['bodega']}", headers=headers).status_code == 200
    feed_ids = {j["id"] for j in client.get("/api/jobs/feed", headers=headers).json()["items"]}
    assert ids["bodega"] in feed_ids
    assert client.delete(f"/api/swipes/jobs/{ids['bodega']}", headers=headers).status_code == 404


def test_cannot_swipe_closed_or_missing_jobs(client, world):
    headers, ids = auth(world["token"]), world["ids"]
    for key in ("cerrada", "vencida", "oculta"):
        r = client.post("/api/swipes/jobs", json={"job_id": ids[key], "action": "like"}, headers=headers)
        assert r.status_code == 404
    r = client.post("/api/swipes/jobs", json={"job_id": 99999, "action": "like"}, headers=headers)
    assert r.status_code == 404
    r = client.post("/api/swipes/jobs", json={"job_id": ids["backend"], "action": "quizas"}, headers=headers)
    assert r.status_code == 422


# ---------------- Matches ----------------
def test_like_creates_match_when_company_already_liked(client, world, db_session):
    headers, ids = auth(world["token"]), world["ids"]
    with db_session() as db:
        db.add(m.CompanySwipe(job_id=ids["backend"], applicant_id=world["applicant_id"], action="like"))
        db.commit()

    r = client.post("/api/swipes/jobs", json={"job_id": ids["backend"], "action": "like"}, headers=headers)
    body = r.json()
    assert body["matched"] is True and body["match_id"]

    # Un like normal (sin like de la empresa) queda como "me interesa"
    client.post("/api/swipes/jobs", json={"job_id": ids["frontend"], "action": "like"}, headers=headers)

    data = client.get("/api/matches/applicant", headers=headers).json()
    assert [mt["job"]["id"] for mt in data["matches"]] == [ids["backend"]]
    assert data["matches"][0]["job"]["matched"] is True
    assert data["matches"][0]["contact"] == {"name": "Ana", "email": "900123456-7@empresa.com", "phone": None}
    assert [j["id"] for j in data["liked"]] == [ids["frontend"]]

    # Con match ya no se puede descartar ni deshacer
    r = client.post("/api/swipes/jobs", json={"job_id": ids["backend"], "action": "dislike"}, headers=headers)
    assert r.status_code == 409
    assert client.delete(f"/api/swipes/jobs/{ids['backend']}", headers=headers).status_code == 409

    # Repetir el like no crea otro match
    r = client.post("/api/swipes/jobs", json={"job_id": ids["backend"], "action": "like"}, headers=headers)
    assert r.json()["matched"] is False
    with db_session() as db:
        assert db.query(m.Match).count() == 1


def test_company_dislike_does_not_create_match(client, world, db_session):
    headers, ids = auth(world["token"]), world["ids"]
    with db_session() as db:
        db.add(m.CompanySwipe(job_id=ids["backend"], applicant_id=world["applicant_id"], action="dislike"))
        db.commit()
    r = client.post("/api/swipes/jobs", json={"job_id": ids["backend"], "action": "like"}, headers=headers)
    assert r.json()["matched"] is False


# ---------------- Buscador ----------------
def test_search_by_text_skill_and_company(client, world):
    headers, ids = auth(world["token"]), world["ids"]

    def search(**params):
        r = client.get("/api/jobs/search", params=params, headers=headers)
        assert r.status_code == 200, r.text
        return r.json()

    assert {j["id"] for j in search(q="desarrollador")["items"]} == {ids["backend"], ids["frontend"]}
    assert [j["id"] for j in search(q="react")["items"]] == [ids["frontend"]]  # por habilidad
    assert [j["id"] for j in search(q="logística")["items"]] == [ids["bodega"]]  # por empresa
    assert [j["id"] for j in search(q="desarrollador python")["items"]] == [ids["backend"]]  # todas las palabras
    assert search(q="100%_")["total"] == 0  # comodines escapados
    assert search(q="python")["total"] == 1  # las cerradas / vencidas / deshabilitadas no aparecen


def test_search_filters_sort_and_pagination(client, world):
    headers, ids = auth(world["token"]), world["ids"]

    def search(**params):
        return client.get("/api/jobs/search", params=params, headers=headers).json()

    assert [j["id"] for j in search(contract_type_id=2)["items"]] == [ids["frontend"]]
    assert {j["id"] for j in search(salary_min=2_000_000)["items"]} == {ids["backend"]}
    assert [j["id"] for j in search(sort="recientes")["items"]] == [ids["backend"], ids["frontend"], ids["bodega"]]
    assert [j["id"] for j in search(sort="salario")["items"]][:2] == [ids["backend"], ids["bodega"]]

    page1 = search(page_size=2)
    page2 = search(page_size=2, page=2)
    assert page1["total"] == 3 and page1["has_more"] is True and len(page1["items"]) == 2
    assert page2["has_more"] is False and len(page2["items"]) == 1
    assert not {j["id"] for j in page1["items"]} & {j["id"] for j in page2["items"]}

    assert client.get("/api/jobs/search", params={"sort": "otro"}, headers=headers).status_code == 422


def test_search_shows_my_decisions_and_can_hide_discarded(client, world):
    headers, ids = auth(world["token"]), world["ids"]
    client.post("/api/swipes/jobs", json={"job_id": ids["bodega"], "action": "dislike"}, headers=headers)
    client.post("/api/swipes/jobs", json={"job_id": ids["frontend"], "action": "like"}, headers=headers)

    items = {j["id"]: j for j in client.get("/api/jobs/search", headers=headers).json()["items"]}
    assert items[ids["bodega"]]["my_action"] == "dislike"
    assert items[ids["frontend"]]["my_action"] == "like"
    assert items[ids["backend"]]["my_action"] is None

    hidden = client.get("/api/jobs/search", params={"hide_discarded": True}, headers=headers).json()
    assert ids["bodega"] not in {j["id"] for j in hidden["items"]}

    # Cambiar de opinión desde el buscador
    client.post("/api/swipes/jobs", json={"job_id": ids["bodega"], "action": "like"}, headers=headers)
    detail = client.get(f"/api/jobs/{ids['bodega']}", headers=headers).json()
    assert detail["my_action"] == "like"


# ---------------- Detalle ----------------
def test_job_detail(client, world):
    headers, ids = auth(world["token"]), world["ids"]
    r = client.get(f"/api/jobs/{ids['backend']}", headers=headers)
    assert r.status_code == 200
    job = r.json()
    assert job["min_education"] == "Pregrado" and job["contract_type"] == "Término indefinido"
    assert job["salary_max"] == 6_000_000 and job["is_open"] is True
    assert job["company"]["industry"] == "Tecnología" and job["company"]["city"] == "Bogotá"
    assert client.get(f"/api/jobs/{ids['cerrada']}", headers=headers).status_code == 404
    assert client.get("/api/jobs/99999", headers=headers).status_code == 404


def test_closed_job_stays_visible_for_its_match(client, world, db_session):
    headers, ids = auth(world["token"]), world["ids"]
    with db_session() as db:
        db.add(m.CompanySwipe(job_id=ids["backend"], applicant_id=world["applicant_id"], action="like"))
        db.commit()
    client.post("/api/swipes/jobs", json={"job_id": ids["backend"], "action": "like"}, headers=headers)
    with db_session() as db:
        db.get(m.Job, ids["backend"]).status = "cerrada"
        db.commit()

    detail = client.get(f"/api/jobs/{ids['backend']}", headers=headers).json()
    assert detail["is_open"] is False and detail["matched"] is True
    matches = client.get("/api/matches/applicant", headers=headers).json()["matches"]
    assert matches[0]["job"]["is_open"] is False


def test_inactive_company_jobs_are_hidden(client, world, db_session):
    headers, ids = auth(world["token"]), world["ids"]
    with db_session() as db:
        company = db.query(m.Company).filter_by(name="Logística Express").one()
        db.get(m.User, company.user_id).is_active = False
        db.commit()
    feed_ids = {j["id"] for j in client.get("/api/jobs/feed", headers=headers).json()["items"]}
    assert ids["bodega"] not in feed_ids
    assert client.get(f"/api/jobs/{ids['bodega']}", headers=headers).status_code == 404


# ---------------- Permisos ----------------
def test_only_applicants_can_use_job_search(client, world):
    assert client.get("/api/jobs/feed").status_code == 401
    r = client.post("/api/auth/register/company", json={
        "name": "Otra SAS", "tax_id": "901000111-1", "industry_id": 1, "size": "1-10", "city_id": 1,
        "contact_name": "Leo", "email": "leo@otra.com", "password": PASSWORD, "accept_terms": True,
    })
    company_headers = auth(r.json()["access_token"])
    assert client.get("/api/jobs/feed", headers=company_headers).status_code == 403
    assert client.get("/api/jobs/search", headers=company_headers).status_code == 403
    assert client.get("/api/matches/applicant", headers=company_headers).status_code == 403


def test_contract_types_catalog(client):
    r = client.get("/api/catalogs/contract-types")
    assert r.status_code == 200 and r.json()[0] == {"id": 1, "name": "Término indefinido"}


def test_feed_and_search_filter_by_match_level(client, world):
    headers, ids = auth(world["token"]), world["ids"]
    everything = client.get("/api/jobs/feed", headers=headers).json()
    scores = {j["id"]: j["score"] for j in everything["items"]}
    assert everything["hidden_count"] == 0

    cut = sorted(scores.values())[1]  # deja por fuera al menos la de menor puntaje
    recommended = client.get("/api/jobs/feed", params={"min_score": cut}, headers=headers).json()
    assert all(j["score"] >= cut for j in recommended["items"])
    assert recommended["hidden_count"] == sum(1 for v in scores.values() if v < cut) >= 1

    found = client.get("/api/jobs/search", params={"min_score": cut}, headers=headers).json()
    assert found["total"] == len(recommended["items"]) and all(j["score"] >= cut for j in found["items"])
    assert client.get("/api/jobs/feed", params={"min_score": 101}, headers=headers).status_code == 422


def test_low_match_cards_show_gaps(client, world):
    items = {j["id"]: j for j in client.get("/api/jobs/feed", headers=auth(world["token"])).json()["items"]}
    frontend = items[world["ids"]["frontend"]]  # pide React y CSS, que el aspirante no tiene
    assert frontend["score_gaps"][0] == "No registras las habilidades requeridas: CSS, React"
    assert not any("habilidades requeridas" in reason for reason in frontend["score_reasons"])
