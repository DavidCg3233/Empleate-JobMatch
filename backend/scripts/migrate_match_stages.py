"""Agrega la etapa del proceso después del match a la tabla `matches`.

Columnas nuevas:
  - stage: match | en_revision | entrevista | seleccionado | descartado (los matches existentes quedan en "match")
  - stage_updated_at: cuándo la empresa cambió la etapa por última vez

Ejecutar desde backend/ con el entorno virtual activo (se puede repetir sin problema):
    python -m scripts.migrate_match_stages

En producción, ejecútalo contra la base de Railway ANTES de subir el código que usa estas columnas.
"""
from sqlalchemy import inspect, text

from app.database import engine

COLUMNS = {
    "stage": (
        "ALTER TABLE matches ADD COLUMN stage "
        "ENUM('match','en_revision','entrevista','seleccionado','descartado') NOT NULL DEFAULT 'match'"
    ),
    "stage_updated_at": "ALTER TABLE matches ADD COLUMN stage_updated_at DATETIME NULL",
}


def main() -> None:
    existing = {c["name"] for c in inspect(engine).get_columns("matches")}
    with engine.begin() as conn:
        for name, ddl in COLUMNS.items():
            if name in existing:
                print(f"= matches.{name} ya existe")
                continue
            conn.execute(text(ddl))
            print(f"+ matches.{name}")
    print("Listo.")


if __name__ == "__main__":
    main()
