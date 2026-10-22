"""El backend también sirve las páginas del frontend (una sola dirección: http://127.0.0.1:8000)."""


def test_serves_frontend_pages(client):
    home = client.get("/")
    assert home.status_code == 200 and "text/html" in home.headers["content-type"]
    assert "Empléate" in home.text

    for path in ("/pages/auth/login.html", "/pages/applicant/profile.html", "/pages/company/jobs.html",
                 "/pages/legal/terminos.html", "/assets/js/config.js", "/assets/css/main.css"):
        assert client.get(path).status_code == 200, path

    assert client.get("/pages/no-existe.html").status_code == 404


def test_api_keeps_priority_and_json_errors(client):
    assert client.get("/api/catalogs/cities").json()[0]["name"]
    missing = client.get("/api/no-existe")
    assert missing.status_code == 404 and missing.json() == {"detail": {"message": "Ruta no encontrada."}}
    assert client.post("/api/otra/ruta").status_code == 404


def test_backend_files_are_not_exposed(client):
    # Solo se publica la carpeta frontend/: nada del backend (.env, código, hojas de vida)
    for path in ("/../backend/.env", "/backend/.env", "/main.py", "/uploads/cvs/x.pdf", "/%2e%2e/backend/.env"):
        assert client.get(path).status_code == 404, path
