"""Lectura de hojas de vida: extracción de texto y lector por reglas (sin IA)."""
import pytest

from app.services import cv_parser_service
from app.services.cv_parser_service import CVReadError, extract_text, heuristic_parse, normalize
from tests.cv_samples import CV_LINES, make_docx, make_pdf

CV_TEXT = "\n".join(CV_LINES)


@pytest.mark.parametrize("ext,maker", [(".docx", make_docx), (".pdf", make_pdf)])
def test_extract_text_from_files(ext, maker):
    text = extract_text(maker(), ext)
    assert "Soluciones Andinas" in text
    assert "laura.gomez@correo.com" in text


def test_extract_text_rejects_empty_document():
    with pytest.raises(CVReadError):
        extract_text(make_pdf(["Hola"]), ".pdf")


def test_heuristic_parse_extracts_key_data():
    data = heuristic_parse(CV_TEXT)
    assert data["first_name"] == "Laura Marcela"
    assert data["last_name"] == "Gómez Ríos"
    assert data["email"] == "laura.gomez@correo.com"
    assert "301" in data["phone"]
    assert data["summary"].startswith("Ingeniera de sistemas")

    first, second = data["experiences"][:2]
    assert first["position"] == "Desarrolladora Backend"
    assert first["company_name"] == "Soluciones Andinas S.A.S."
    assert first["start_date"] == "2022-01" and first["is_current"] is True
    assert second["company_name"] == "Tecnología del Pacífico"
    assert (second["start_date"], second["end_date"]) == ("2020-03", "2021-12")

    edu = data["educations"][0]
    assert edu["degree"] == "Ingeniería de Sistemas"
    assert edu["institution"] == "Universidad del Valle"
    assert edu["level"] == "pregrado"

    assert {"Python", "FastAPI", "MySQL"} <= set(data["skills"])
    assert {"name": "ingles", "proficiency": "intermedio"} in data["languages"]


def test_normalize_maps_catalog_ids(db_session):
    with db_session() as db:
        data = normalize(db, heuristic_parse(CV_TEXT))
    assert data["city_id"] == 1  # Cali
    assert data["educations"][0]["education_level_id"] == 4  # Pregrado
    assert {"language_id": 2, "proficiency": "intermedio"} in data["languages"]
    assert data["experiences"][0]["start_date"] == "2022-01-01"


def test_ai_failure_falls_back_to_rules(db_session, monkeypatch):
    class BrokenAI:
        name = "falla"

        def complete_json(self, system, user):
            raise cv_parser_service.AIError("sin conexión")

    monkeypatch.setattr(cv_parser_service, "get_ai_provider", lambda: BrokenAI())
    with db_session() as db:
        data, source = cv_parser_service.parse_cv(db, CV_TEXT)
    assert source == "basico"
    assert data["email"] == "laura.gomez@correo.com"


def test_claude_provider_used_when_configured(db_session, monkeypatch):
    """Con AI_PROVIDER=claude se llama al SDK (simulado aquí) y se normaliza su JSON."""
    from types import SimpleNamespace

    from app.config import settings
    from app.services.ai.claude_provider import ClaudeProvider

    monkeypatch.setattr(settings, "AI_PROVIDER", "claude")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "clave-de-prueba")
    reply = (
        '{"first_name": "Laura", "last_name": "Gómez", "email": "laura@correo.com", "phone": null,'
        ' "city": "Bogotá", "desired_position": "Backend", "summary": null, "skills": ["Python"],'
        ' "experiences": [], "languages": [],'
        ' "educations": [{"institution": "Univalle", "degree": "Ingeniería", "field_of_study": null,'
        ' "level": "Pregrado", "start_date": "2014-02", "end_date": "2019-12"}]}'
    )
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=reply)])

    monkeypatch.setattr(ClaudeProvider, "__init__", lambda self: setattr(self, "model", "m") or setattr(
        self, "client", SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=fake_create)))))

    with db_session() as db:
        data, source = cv_parser_service.parse_cv(db, CV_TEXT)
    assert source == "ia" and calls
    assert data["city_id"] == 2 and data["educations"][0]["education_level_id"] == 4
    assert data["educations"][0]["start_date"] == "2014-02-01"
