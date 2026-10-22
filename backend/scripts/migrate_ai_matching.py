"""Prepara las tablas de caché de la IA para el emparejamiento.

Agrega la columna `content_hash` (huella del contenido con que se calculó) a:
applicant_embeddings, job_embeddings y match_scores.

Ejecutar desde backend/ con el entorno virtual activo (se puede repetir sin problema):
    python -m scripts.migrate_ai_matching
"""
from sqlalchemy import inspect, text

from app.database import engine

TABLES = ("applicant_embeddings", "job_embeddings", "match_scores")


def main() -> None:
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in TABLES:
            columns = {c["name"] for c in inspector.get_columns(table)}
            if "content_hash" in columns:
                print(f"= {table}.content_hash ya existe")
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN content_hash CHAR(64) NULL"))
            print(f"+ {table}.content_hash")
    print("Listo.")


if __name__ == "__main__":
    main()
