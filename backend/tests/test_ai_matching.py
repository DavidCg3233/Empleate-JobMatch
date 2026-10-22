"""Emparejamiento con IA: afinidad semántica (embeddings), caché, análisis de cada pareja, permisos y privacidad.
Se usa un proveedor de IA simulado: estas pruebas no llaman a OpenAI ni gastan dinero."""
import json
from datetime import datetime

import httpx
import pytest

from app import models as m
from app.config import settings
from app.services import ai_matching_service
from app.services.ai.base import AIError, AIProvider
from app.services.ai.openai_provider import OpenAIProvider
from app.services.matching_service import semantic_points

PASSWORD = "Clave1234"
TOPICS = ["software", "python", "programacion", "cocina", "panaderia", "alimentos"]


class FakeAI(AIProvider):
    """Vectores según los temas que menciona el texto; análisis fijo. Cuenta las llamadas."""

    name = "fake"
    model = "fake-chat"
    embedding_model = "fake-embed"
    supports_embeddings = True

    def __init__(self):
        self.embedded: list[str] = []
        self.prompts: list[str] = []
        self.fail_embed = False
        self.fail_chat = False
        self.reply = {
            "score": 87,
            "aspirante": {"resumen": "Encajas por tu experiencia en Python.", "fortalezas": ["Python", "APIs"],
                          "brechas": ["Docker"], "consejo": "Haz un curso corto de Docker."},
            "empresa": {"resumen": "Encaja por su experiencia en Python.", "fortalezas": ["Python"],
                        "brechas": ["Docker"], "preguntas": ["¿Ha usado contenedores?", "¿Qué APIs ha construido?"]},
        }

    def embed(self, texts):
        if self.fail_embed:
            raise AIError("sin conexión")
        self.embedded.extend(texts)
        vectors = []
        for text in texts:
            low = text.lower().replace("ó", "o").replace("í", "i")
            vectors.append([0.05 + low.count(topic) for topic in TOPICS])
        return vectors

    def _complete(self, system, user, max_tokens):
        if self.fail_chat:
            raise AIError("sin conexión")
        self.prompts.append(user)
        return json.dumps(self.reply)


@pytest.fixture()
def ai(monkeypatch):
    fake = FakeAI()
    monkeypatch.setattr(ai_matching_service, "get_ai_provider", lambda: fake)
    monkeypatch.setattr(settings, "AI_MATCHING_ENABLED", True)
    return fake


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def register_company(client, email="rrhh@andino.com", tax_id="900123456-7"):
    r = client.post("/api/auth/register/company", json={
        "name": "Andino", "tax_id": tax_id, "industry_id": 1, "size": "11-50", "city_id": 1,
        "contact_name": "Ana", "email": email, "password": PASSWORD, "accept_terms": True,
    })
    return auth(r.json()["access_token"])


def create_job(client, headers, title, description, **extra):
    payload = {"title": title, "description": description, "modality": "presencial", "city_id": 1,
               "contract_type_id": 1, "skills": [], **extra}
    r = client.post("/api/company/jobs", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def register_applicant(client, email="laura@correo.com", **extra):
    payload = {"first_name": "Laura", "last_name": "Gómez", "email": email, "password": PASSWORD,
               "accept_terms": True, "city_id": 1, "phone": "300 123 4567",
               "summary": "Me apasiona el desarrollo de software con Python y la programación de APIs.", **extra}
    r = client.post("/api/auth/register/applicant", json=payload)
    assert r.status_code == 201, r.text
    return auth(r.json()["access_token"])


@pytest.fixture()
def world(client, db_session):
    company = register_company(client)
    software = create_job(client, company, "Desarrollador de software",
                          "Buscamos persona para desarrollo de software y programación en Python para nuestros clientes.")
    cocina = create_job(client, company, "Auxiliar de cocina",
                        "Apoyo en cocina, panadería y manipulación de alimentos en nuestro restaurante principal.")
    applicant = register_applicant(client)
    with db_session() as db:
        applicant_id = db.query(m.Applicant).one().id
    return {"company": company, "applicant": applicant, "software": software, "cocina": cocina, "applicant_id": applicant_id}


# =====================================================================
# Estado
# =====================================================================
def test_status_without_ai(client):
    assert client.get("/api/matching/status").json() == {"provider": None, "semantic": False, "analysis": False}


def test_status_with_ai(client, ai):
    assert client.get("/api/matching/status").json() == {"provider": "fake", "semantic": True, "analysis": True}


def test_ai_can_be_turned_off(client, ai, monkeypatch):
    monkeypatch.setattr(settings, "AI_MATCHING_ENABLED", False)
    assert client.get("/api/matching/status").json()["analysis"] is False


# =====================================================================
# Capa 1: afinidad semántica
# =====================================================================
def test_semantic_affinity_changes_ranking(client, world, ai):
    first = {j["id"]: j for j in client.get("/api/jobs/feed", headers=world["applicant"]).json()["items"]}
    items = client.get("/api/jobs/feed", headers=world["applicant"]).json()["items"]
    assert [j["id"] for j in items][0] == world["software"]["id"]
    software = next(j for j in items if j["id"] == world["software"]["id"])
    cocina = next(j for j in items if j["id"] == world["cocina"]["id"])
    assert software["score"] > cocina["score"]
    assert software["score_reasons"][0] == "Tu perfil es muy afín a lo que describe la vacante"
    assert cocina["score_gaps"][0] == "La vacante tiene poca relación con tu perfil"
    assert first == {j["id"]: j for j in items}  # el resultado es estable entre peticiones (sale de la caché)


def test_rules_only_when_ai_is_off(client, world):
    items = client.get("/api/jobs/feed", headers=world["applicant"]).json()["items"]
    scores = {j["id"]: j["score"] for j in items}
    # Sin habilidades en las vacantes ni en el perfil, las reglas les dan el mismo puntaje
    assert scores[world["software"]["id"]] == scores[world["cocina"]["id"]]


def test_vectors_are_cached_and_recalculated_when_profile_changes(client, world, ai, db_session):
    client.get("/api/jobs/feed", headers=world["applicant"])
    first = len(ai.embedded)
    assert first == 3  # 1 perfil + 2 vacantes
    with db_session() as db:
        assert db.query(m.ApplicantEmbedding).count() == 1 and db.query(m.JobEmbedding).count() == 2

    client.get("/api/jobs/feed", headers=world["applicant"])
    client.get("/api/jobs/search", headers=world["applicant"])
    assert len(ai.embedded) == first  # todo salió de la caché

    profile = client.get("/api/applicant/profile", headers=world["applicant"]).json()
    profile["summary"] = "Cocinero con experiencia en panadería y alimentos."
    client.put("/api/applicant/profile", json={k: profile[k] for k in (
        "first_name", "last_name", "phone", "city_id", "desired_position", "summary", "search_status",
        "desired_salary_min", "desired_modality", "willing_to_relocate", "experiences", "educations", "skills", "languages",
    )}, headers=world["applicant"])
    items = client.get("/api/jobs/feed", headers=world["applicant"]).json()["items"]
    assert len(ai.embedded) == first + 1  # solo se recalculó el perfil
    assert items[0]["id"] == world["cocina"]["id"]  # ahora la más afín es la de cocina


def test_job_vector_recalculated_when_job_changes(client, world, ai):
    client.get("/api/jobs/feed", headers=world["applicant"])
    before = len(ai.embedded)
    job = world["cocina"]
    client.put(f"/api/company/jobs/{job['id']}", headers=world["company"], json={
        "title": job["title"], "description": "Ahora es desarrollo de software en Python para la cocina digital.",
        "modality": "presencial", "city_id": 1, "contract_type_id": 1, "skills": [],
    })
    client.get("/api/jobs/feed", headers=world["applicant"])
    assert len(ai.embedded) == before + 1


def test_company_candidates_use_semantic_affinity(client, world, ai):
    register_applicant(client, "chef@correo.com", summary="Cocinero con experiencia en panadería y alimentos.")
    items = client.get(f"/api/company/jobs/{world['software']['id']}/candidates", headers=world["company"]).json()["items"]
    assert items[0]["applicant_id"] == world["applicant_id"]
    assert items[0]["score"] > items[1]["score"]
    assert items[0]["score_reasons"][0] == "Su perfil es muy afín a lo que describe la vacante"


def test_ai_failure_falls_back_to_rules_and_pauses(client, world, ai):
    ai.fail_embed = True
    r = client.get("/api/jobs/feed", headers=world["applicant"])
    assert r.status_code == 200 and len(r.json()["items"]) == 2  # sigue funcionando con reglas
    ai.fail_embed = False
    client.get("/api/jobs/feed", headers=world["applicant"])
    assert ai.embedded == []  # en pausa: no vuelve a intentar enseguida
    ai_matching_service.reset_pauses()
    client.get("/api/jobs/feed", headers=world["applicant"])
    assert len(ai.embedded) == 3


def test_semantic_points_scale():
    assert semantic_points(0.1) == 0 and semantic_points(0.95) == 100
    assert semantic_points(0.45) == pytest.approx(50)


# =====================================================================
# Capa 2: análisis de la pareja
# =====================================================================
def test_applicant_analysis_is_cached(client, world, ai, db_session):
    url = f"/api/matching/jobs/{world['software']['id']}/analysis"
    first = client.get(url, headers=world["applicant"])
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["score"] == 87 and body["summary"] == "Encajas por tu experiencia en Python."
    assert body["advice"] == "Haz un curso corto de Docker." and body["interview_questions"] == []
    assert body["cached"] is False and body["model"] == "fake:fake-chat"

    second = client.get(url, headers=world["applicant"]).json()
    assert second["cached"] is True and len(ai.prompts) == 1  # no se volvió a pagar

    with db_session() as db:
        row = db.query(m.MatchScore).one()
        assert row.score == 87 and row.semantic_similarity is not None and row.content_hash

    # La empresa ve el mismo análisis, redactado para ella, sin otra llamada
    company = client.get(f"/api/matching/jobs/{world['software']['id']}/candidates/{world['applicant_id']}/analysis",
                         headers=world["company"]).json()
    assert company["summary"] == "Encaja por su experiencia en Python."
    assert company["interview_questions"] == ["¿Ha usado contenedores?", "¿Qué APIs ha construido?"]
    assert company["advice"] is None and company["cached"] is True and len(ai.prompts) == 1


def test_analysis_recalculated_when_job_changes(client, world, ai):
    url = f"/api/matching/jobs/{world['software']['id']}/analysis"
    client.get(url, headers=world["applicant"])
    job = world["software"]
    client.put(f"/api/company/jobs/{job['id']}", headers=world["company"], json={
        "title": job["title"], "description": job["description"] + " Se valora experiencia con Docker.",
        "modality": "presencial", "city_id": 1, "contract_type_id": 1, "skills": [],
    })
    assert client.get(url, headers=world["applicant"]).json()["cached"] is False
    assert len(ai.prompts) == 2


def test_analysis_sends_only_professional_data(client, world, ai):
    client.get(f"/api/matching/jobs/{world['software']['id']}/analysis", headers=world["applicant"])
    sent = ai.prompts[0] + "".join(ai.embedded)
    for private in ("Laura", "Gómez", "laura@correo.com", "300 123 4567"):
        assert private not in sent, private
    assert "desarrollo de software" in sent


def test_analysis_validates_ai_output(client, world, ai):
    ai.reply = {"score": "mucho", "aspirante": {}, "empresa": {}}
    r = client.get(f"/api/matching/jobs/{world['software']['id']}/analysis", headers=world["applicant"])
    assert r.status_code == 502
    ai_matching_service.reset_pauses()
    ai.reply = {"score": 250, "aspirante": {"resumen": "Bien " * 300, "fortalezas": ["a", "b", "c", "d"], "brechas": "no es lista"},
                "empresa": {"resumen": "Bien", "preguntas": [1, None, "¿Por qué?"]}}
    body = client.get(f"/api/matching/jobs/{world['software']['id']}/analysis", headers=world["applicant"]).json()
    assert body["score"] == 100 and len(body["summary"]) <= 500
    assert body["strengths"] == ["a", "b", "c"] and body["gaps"] == []


def test_analysis_unavailable_without_ai(client, world):
    r = client.get(f"/api/matching/jobs/{world['software']['id']}/analysis", headers=world["applicant"])
    assert r.status_code == 503


def test_analysis_ai_error(client, world, ai):
    ai.fail_chat = True
    r = client.get(f"/api/matching/jobs/{world['software']['id']}/analysis", headers=world["applicant"])
    assert r.status_code == 502


def test_analysis_permissions(client, world, ai, db_session):
    software = world["software"]["id"]
    # Aspirante: no puede analizar una vacante cerrada que nunca marcó
    client.patch(f"/api/company/jobs/{world['cocina']['id']}/status", json={"status": "cerrada"}, headers=world["company"])
    assert client.get(f"/api/matching/jobs/{world['cocina']['id']}/analysis", headers=world["applicant"]).status_code == 404
    assert client.get("/api/matching/jobs/9999/analysis", headers=world["applicant"]).status_code == 404
    # Roles
    assert client.get(f"/api/matching/jobs/{software}/analysis", headers=world["company"]).status_code == 403
    assert client.get(f"/api/matching/jobs/{software}/analysis").status_code == 401

    url = f"/api/matching/jobs/{software}/candidates/{world['applicant_id']}/analysis"
    other = register_company(client, "rrhh@otra.com", "800111222-3")
    assert client.get(url, headers=other).status_code == 404  # vacante de otra empresa

    # Si el aspirante descartó la vacante, la empresa no puede analizarlo
    client.post("/api/swipes/jobs", json={"job_id": software, "action": "dislike"}, headers=world["applicant"])
    assert client.get(url, headers=world["company"]).status_code == 404
    # Con match sí
    client.post("/api/swipes/jobs", json={"job_id": software, "action": "like"}, headers=world["applicant"])
    client.post("/api/swipes/candidates", json={"job_id": software, "applicant_id": world["applicant_id"], "action": "like"},
                headers=world["company"])
    assert client.get(url, headers=world["company"]).status_code == 200
    # Aspirante desactivado
    with db_session() as db:
        user = db.query(m.User).filter_by(email="laura@correo.com").one()
        user.is_active = False
        db.commit()
    assert client.get(url, headers=world["company"]).status_code == 404


# =====================================================================
# Llamadas reales a OpenAI (formato), con la red simulada
# =====================================================================
class FakeResponse:
    def __init__(self, status, data):
        self.status_code, self._data = status, data
        self.text = json.dumps(data)

    def json(self):
        return self._data


def test_openai_provider_requests(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-prueba-secreta")
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json))
        if url.endswith("/embeddings"):
            # OpenAI puede devolver los vectores en otro orden: se ordenan por "index"
            return FakeResponse(200, {"data": [{"index": 1, "embedding": [0.2]}, {"index": 0, "embedding": [0.1]}]})
        return FakeResponse(200, {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true}'}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    provider = OpenAIProvider()
    assert provider.embed(["a", "b"]) == [[0.1], [0.2]]
    assert provider.complete_json("sistema", "usuario", max_tokens=100) == {"ok": True}

    embed_call, chat_call = calls
    assert embed_call[0] == "https://api.openai.com/v1/embeddings"
    assert embed_call[2] == {"model": "text-embedding-3-small", "input": ["a", "b"]}
    assert embed_call[1]["Authorization"] == "Bearer sk-prueba-secreta"
    assert chat_call[2]["response_format"] == {"type": "json_object"}
    assert chat_call[2]["max_completion_tokens"] == 100 and chat_call[2]["model"] == "gpt-4o-mini"


def test_openai_provider_errors_do_not_leak_the_key(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-prueba-secreta")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(401, {"error": {"message": "Incorrect API key"}}))
    with pytest.raises(AIError) as exc:
        OpenAIProvider().embed(["a"])
    assert "401" in str(exc.value) and "sk-prueba-secreta" not in str(exc.value)

    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(200, {"choices": [{"finish_reason": "length", "message": {"content": "{"}}]}))
    with pytest.raises(AIError):
        OpenAIProvider().complete_json("s", "u")


def test_missing_library_disables_ai_instead_of_breaking(client, world, monkeypatch):
    """Si el servidor se arranca sin el entorno virtual (falta httpx), la app sigue funcionando con reglas."""
    import builtins

    from app.services.ai import base

    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-prueba")
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "app.services.ai.openai_provider" or name == "httpx":
            raise ModuleNotFoundError("No module named 'httpx'", name="httpx")
        return real_import(name, *args, **kwargs)

    import sys
    monkeypatch.delitem(sys.modules, "app.services.ai.openai_provider", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert base.get_ai_provider() is None
    assert client.get("/api/matching/status").json()["analysis"] is False
    assert client.get("/api/jobs/feed", headers=world["applicant"]).status_code == 200
