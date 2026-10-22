"""Convierte la tabla `skills` en el catálogo de habilidades y herramientas.

  1. Agrega las columnas `category` (tecnica | herramienta | blanda) e `is_curated` si no existen.
  2. Carga (o actualiza) el catálogo curado de app/data/skills_catalog.py.

Ejecutar desde backend/ con el entorno virtual activo (se puede repetir sin problema):
    python -m scripts.migrate_skills_catalog
"""
from sqlalchemy import inspect, text

import app.models  # noqa: F401  (registra todas las tablas)
from app.database import SessionLocal, engine
from app.services.skill_service import seed_curated_skills


def add_columns() -> None:
    columns = {c["name"] for c in inspect(engine).get_columns("skills")}
    with engine.begin() as conn:
        if "category" not in columns:
            conn.execute(text(
                "ALTER TABLE skills ADD COLUMN category ENUM('tecnica','herramienta','blanda') NULL AFTER name"
            ))
            print("+ columna skills.category")
        if "is_curated" not in columns:
            conn.execute(text("ALTER TABLE skills ADD COLUMN is_curated TINYINT(1) NOT NULL DEFAULT 0 AFTER category"))
            conn.execute(text("ALTER TABLE skills ADD KEY idx_skills_curated (is_curated)"))
            print("+ columna skills.is_curated")


def main() -> None:
    add_columns()
    with SessionLocal() as db:
        created, updated = seed_curated_skills(db)
        db.commit()
    print(f"Catálogo listo: {created} habilidades nuevas, {updated} existentes actualizadas.")


if __name__ == "__main__":
    main()
