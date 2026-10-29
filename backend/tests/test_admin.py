"""Panel de administrador, bitácora, creación del administrador y "Eliminar mi cuenta"."""
import pytest

from app import models as m
from scripts.create_admin import create_or_update_admin
from tests.cv_samples import make_docx
from tests.test_company import PASSWORD, applicant_id, auth, create_job, register_applicant, register_company

ADMIN_EMAIL = "admin@empleate.co"
ADMIN_PASSWORD = "Admin1234"


def login(client, email, password=PASSWORD):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return auth(r.json()["access_token"])


@pytest.fixture()
def admin(client, db_session):
    with db_session() as db:
        assert create_or_update_admin(db, ADMIN_EMAIL, ADMIN_PASSWORD) == "creado"
    return login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


def user_id(db_session, email):
    with db_session() as db:
        return db.query(m.User).filter_by(email=email).one().id


def make_match(client, db_session):
    company = register_company(client)
    job = create_job(client, company)
    applicant = register_applicant(client, "laura@correo.com")
    client.post("/api/swipes/jobs", json={"job_id": job["id"], "action": "like"}, headers=applicant)
    aid = applicant_id(db_session, "laura@correo.com")
    r = client.post("/api/swipes/candidates", headers=company, json={"job_id": job["id"], "applicant_id": aid, "action": "like"})
    assert r.json()["matched"] is True
    return company, job, applicant


# =====================================================================
# Crear el administrador
# =====================================================================
def test_create_admin_script(client, db_session):
    with db_session() as db:
        assert create_or_update_admin(db, " Admin@Empleate.co ", ADMIN_PASSWORD) == "creado"
        with pytest.raises(ValueError):
            create_or_update_admin(db, "no-es-correo", ADMIN_PASSWORD)
        with pytest.raises(ValueError):
            create_or_update_admin(db, ADMIN_EMAIL, "corta")

    r = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200 and r.json()["role"] == "administrador"

    # Volver a ejecutarlo cambia la contraseña (sirve para recuperar el acceso)
    with db_session() as db:
        assert create_or_update_admin(db, ADMIN_EMAIL, "Nueva1234") == "actualizado"
    assert client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": "Nueva1234"}).status_code == 200

    # No convierte en administrador a una cuenta de aspirante
    register_applicant(client, "laura@correo.com")
    with db_session() as db:
        with pytest.raises(ValueError, match="aspirante"):
            create_or_update_admin(db, "laura@correo.com", ADMIN_PASSWORD)


def test_admin_routes_need_admin_role(client, admin):
    applicant = register_applicant(client, "laura@correo.com")
    company = register_company(client)
    for path in ("/api/admin/stats", "/api/admin/users", "/api/admin/jobs", "/api/admin/matches", "/api/admin/activity"):
        assert client.get(path).status_code == 401
        assert client.get(path, headers=applicant).status_code == 403
        assert client.get(path, headers=company).status_code == 403
        assert client.get(path, headers=admin).status_code == 200, path
    assert client.get("/api/auth/me", headers=admin).json()["display_name"] == "Administrador"


# =====================================================================
# Resumen y listados
# =====================================================================
def test_stats(client, db_session, admin):
    make_match(client, db_session)
    register_applicant(client, "pedro@correo.com", "Pedro", "Pérez")
    s = client.get("/api/admin/stats", headers=admin).json()
    assert s["total_applicants"] == 2 and s["total_companies"] == 1 and s["total_admins"] == 1
    assert s["total_jobs"] == 1 and s["active_jobs"] == 1 and s["disabled_jobs"] == 0
    assert s["total_matches"] == 1 and s["new_matches_7d"] == 1
    assert s["total_applicant_swipes"] == 1 and s["total_company_swipes"] == 1
    assert s["new_users_7d"] == 3 and s["inactive_users"] == 0
    assert len(s["signups_by_day"]) == 14 and sum(d["count"] for d in s["signups_by_day"]) == 3
    actions = [a["action"] for a in s["recent_activity"]]
    assert "match" in actions and "vacante_creada" in actions and "registro" in actions


def test_list_users_search_and_filters(client, db_session, admin):
    register_applicant(client, "laura@correo.com", "Laura", "Gómez", desired_position="Analista de datos")
    register_company(client)

    body = client.get("/api/admin/users", headers=admin).json()
    assert body["total"] == 3 and body["page"] == 1 and body["pages"] == 1
    by_email = {u["email"]: u for u in body["items"]}
    assert by_email["laura@correo.com"]["display_name"] == "Laura Gómez"
    assert by_email["laura@correo.com"]["detail"] == "Analista de datos"
    assert by_email["rrhh@andino.com"]["display_name"] == "Talento Andino"
    assert by_email["rrhh@andino.com"]["detail"] == "NIT 900123456-7"

    def emails(**params):
        return [u["email"] for u in client.get("/api/admin/users", params=params, headers=admin).json()["items"]]

    assert emails(role="empresa") == ["rrhh@andino.com"]
    assert emails(q="laura gómez") == ["laura@correo.com"]
    assert emails(q="900123456") == ["rrhh@andino.com"]
    assert emails(q="ANDINO") == ["rrhh@andino.com"]
    assert emails(status="inactivo") == []
    assert client.get("/api/admin/users", params={"role": "otro"}, headers=admin).status_code == 422
    # Una página que no existe muestra la última
    assert client.get("/api/admin/users", params={"page": 50}, headers=admin).json()["page"] == 1


def test_deactivate_and_reactivate_user(client, db_session, admin):
    company, job, applicant = make_match(client, db_session)
    uid = user_id(db_session, "rrhh@andino.com")

    r = client.patch(f"/api/admin/users/{uid}/status", json={"is_active": False}, headers=admin)
    assert r.status_code == 200
    # Ya no puede usar la sesión ni entrar, y su vacante desaparece para los aspirantes
    assert client.get("/api/company/profile", headers=company).status_code == 401
    assert client.post("/api/auth/login", json={"email": "rrhh@andino.com", "password": PASSWORD}).status_code == 403
    assert client.get("/api/jobs/feed", headers=applicant).json()["items"] == []
    assert client.get("/api/admin/users", params={"status": "inactivo"}, headers=admin).json()["total"] == 1
    assert client.get("/api/admin/stats", headers=admin).json()["inactive_users"] == 1

    assert client.patch(f"/api/admin/users/{uid}/status", json={"is_active": True}, headers=admin).status_code == 200
    login(client, "rrhh@andino.com")

    log = client.get("/api/admin/activity", params={"action": "usuario_desactivado"}, headers=admin).json()
    assert log["total"] == 1 and log["items"][0]["user_email"] == ADMIN_EMAIL
    assert log["items"][0]["details"]["correo"] == "rrhh@andino.com"
    assert "usuario_activado" in log["actions"]


def test_admin_cannot_manage_itself_or_other_admins(client, db_session, admin):
    me = user_id(db_session, ADMIN_EMAIL)
    assert client.patch(f"/api/admin/users/{me}/status", json={"is_active": False}, headers=admin).status_code == 409
    with db_session() as db:
        create_or_update_admin(db, "otro.admin@empleate.co", ADMIN_PASSWORD)
    other = user_id(db_session, "otro.admin@empleate.co")
    assert client.patch(f"/api/admin/users/{other}/status", json={"is_active": False}, headers=admin).status_code == 409
    assert client.patch("/api/admin/users/9999/status", json={"is_active": False}, headers=admin).status_code == 404


def test_unlock_user(client, db_session, admin):
    register_applicant(client, "laura@correo.com")
    for _ in range(3):
        client.post("/api/auth/login", json={"email": "laura@correo.com", "password": "Incorrecta1"})
    assert client.post("/api/auth/login", json={"email": "laura@correo.com", "password": PASSWORD}).status_code == 423
    body = client.get("/api/admin/users", params={"status": "bloqueado"}, headers=admin).json()
    assert [u["email"] for u in body["items"]] == ["laura@correo.com"] and body["items"][0]["is_locked"] is True

    uid = user_id(db_session, "laura@correo.com")
    assert client.post(f"/api/admin/users/{uid}/unlock", headers=admin).status_code == 200
    login(client, "laura@correo.com")


def test_jobs_list_and_disable(client, db_session, admin):
    company, job, applicant = make_match(client, db_session)
    create_job(client, company, title="Analista QA", status="pausada")

    body = client.get("/api/admin/jobs", headers=admin).json()
    assert body["total"] == 2
    item = next(j for j in body["items"] if j["id"] == job["id"])
    assert item["company_name"] == "Talento Andino" and item["likes"] == 1 and item["matches"] == 1
    assert item["city"] == "Cali" and item["is_enabled"] is True
    assert [j["title"] for j in client.get("/api/admin/jobs", params={"status": "pausada"}, headers=admin).json()["items"]] == ["Analista QA"]
    assert client.get("/api/admin/jobs", params={"q": "backend"}, headers=admin).json()["total"] == 1

    r = client.patch(f"/api/admin/jobs/{job['id']}/enabled", json={"is_enabled": False}, headers=admin)
    assert r.status_code == 200
    assert client.get("/api/admin/jobs", params={"enabled": "false"}, headers=admin).json()["total"] == 1
    # Deja de verse para los aspirantes y la empresa no puede volver a publicarla
    assert client.get("/api/jobs/feed", headers=applicant).json()["items"] == []
    client.patch(f"/api/company/jobs/{job['id']}/status", json={"status": "pausada"}, headers=company)
    r = client.patch(f"/api/company/jobs/{job['id']}/status", json={"status": "activa"}, headers=company)
    assert r.status_code == 409

    assert client.patch(f"/api/admin/jobs/{job['id']}/enabled", json={"is_enabled": True}, headers=admin).status_code == 200
    assert client.patch("/api/admin/jobs/9999/enabled", json={"is_enabled": True}, headers=admin).status_code == 404


def test_matches_list(client, db_session, admin):
    make_match(client, db_session)
    body = client.get("/api/admin/matches", headers=admin).json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["applicant_name"] == "Laura Gómez" and item["company_name"] == "Talento Andino"
    assert item["job_title"] == "Desarrollador Backend Python" and item["applicant_email"] == "laura@correo.com"
    assert client.get("/api/admin/matches", params={"q": "nadie"}, headers=admin).json()["total"] == 0


def test_activity_log_has_no_secrets(client, db_session, admin):
    register_applicant(client, "laura@correo.com")
    login(client, "laura@correo.com")
    with db_session() as db:
        for log in db.query(m.AuditLog).all():
            text = str(log.details or "")
            assert PASSWORD not in text and "password" not in text.lower()
    actions = client.get("/api/admin/activity", headers=admin).json()["actions"]
    assert {"registro", "inicio_sesion", "administrador_creado"} <= set(actions)


# =====================================================================
# Eliminar mi cuenta
# =====================================================================
def delete_account(client, headers, password=PASSWORD):
    return client.request("DELETE", "/api/auth/account", json={"password": password}, headers=headers)


def test_applicant_deletes_account(client, db_session, admin, tmp_path):
    company = register_company(client)
    job = create_job(client, company)
    parsed = client.post("/api/auth/cv/parse", files={"file": ("CV.docx", make_docx(), "application/octet-stream")}).json()
    applicant = register_applicant(client, "laura@correo.com", cv_upload_id=parsed["cv_upload_id"])
    client.post("/api/swipes/jobs", json={"job_id": job["id"], "action": "like"}, headers=applicant)
    aid = applicant_id(db_session, "laura@correo.com")
    client.post("/api/swipes/candidates", headers=company, json={"job_id": job["id"], "applicant_id": aid, "action": "like"})
    with db_session() as db:
        cv_file = tmp_path / "uploads" / db.get(m.Applicant, aid).cv_path
    assert cv_file.is_file()

    assert delete_account(client, applicant, "Incorrecta1").status_code == 400
    r = delete_account(client, applicant)
    assert r.status_code == 200, r.text

    assert not cv_file.exists()
    assert client.get("/api/auth/me", headers=applicant).status_code == 401
    assert client.post("/api/auth/login", json={"email": "laura@correo.com", "password": PASSWORD}).status_code == 401
    assert client.get("/api/matches/company", headers=company).json() == []
    with db_session() as db:
        assert db.query(m.Applicant).count() == 0
        assert db.query(m.Match).count() == 0 and db.query(m.ApplicantSwipe).count() == 0
        assert db.query(m.CompanySwipe).count() == 0 and db.query(m.ApplicantSkill).count() == 0
        # La bitácora se conserva, pero sin enlazar a la persona
        uid_logs = db.query(m.AuditLog).filter(m.AuditLog.action == "cuenta_eliminada").one()
        assert uid_logs.user_id is None and uid_logs.details == {"rol": "aspirante"}
    # Se puede volver a registrar con el mismo correo
    register_applicant(client, "laura@correo.com")


def test_company_deletes_account_with_its_jobs(client, db_session, admin):
    company, job, applicant = make_match(client, db_session)
    create_job(client, company, title="Analista QA")
    assert delete_account(client, company).status_code == 200

    with db_session() as db:
        assert db.query(m.Company).count() == 0 and db.query(m.Job).count() == 0
        assert db.query(m.JobSkill).count() == 0 and db.query(m.Match).count() == 0
    assert client.get("/api/matches/applicant", headers=applicant).json()["matches"] == []
    stats = client.get("/api/admin/stats", headers=admin).json()
    assert stats["total_companies"] == 0 and stats["total_jobs"] == 0


def test_admin_cannot_delete_own_account(client, admin):
    assert delete_account(client, admin, ADMIN_PASSWORD).status_code == 403
    assert client.request("DELETE", "/api/auth/account", json={"password": PASSWORD}).status_code == 401
