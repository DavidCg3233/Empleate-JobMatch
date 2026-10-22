"""Punto de entrada. Ejecutar (desde backend/):  uvicorn main:app --reload
Luego abrir http://127.0.0.1:8000  (el backend sirve la API en /api y las páginas de frontend/)."""
from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import BASE_DIR, settings
from app.controllers import (
    applicant_controller,
    auth_controller,
    catalog_controller,
    company_controller,
    job_controller,
    match_controller,
    matching_controller,
    swipe_controller,
)
from app.database import get_db

app = FastAPI(title="Empléate Jobmatch API", version="0.7.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # el navegador necesita leer el nombre del archivo al descargar la hoja de vida
)

app.include_router(auth_controller.router)
app.include_router(catalog_controller.router)
app.include_router(applicant_controller.router)
app.include_router(job_controller.router)
app.include_router(company_controller.router)
app.include_router(job_controller.company_router)
app.include_router(swipe_controller.router)
app.include_router(match_controller.router)
app.include_router(matching_controller.router)


@app.get("/api/health", tags=["Sistema"])
def health(db: Session = Depends(get_db)):
    """Prueba rápida de la conexión con MySQL."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def api_not_found(path: str):
    """Una ruta /api/... que no existe responde en JSON (y no con la página 404 del frontend)."""
    raise HTTPException(404, detail={"message": "Ruta no encontrada."})


# ---------------- Páginas del frontend ----------------
# Se monta al final: las rutas /api/... de arriba tienen prioridad.
FRONTEND_DIR = BASE_DIR.parent / "frontend"
if settings.SERVE_FRONTEND and FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
