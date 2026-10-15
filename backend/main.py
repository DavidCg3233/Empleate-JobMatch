"""Punto de entrada. Ejecutar:  uvicorn main:app --reload"""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.controllers import auth_controller, catalog_controller
from app.database import get_db

app = FastAPI(title="Empléate Jobmatch API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_controller.router)
app.include_router(catalog_controller.router)


@app.get("/api/health", tags=["Sistema"])
def health(db: Session = Depends(get_db)):
    """Prueba rápida de la conexión con MySQL."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}