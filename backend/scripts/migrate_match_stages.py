"""Agrega la etapa del proceso después del match a la tabla `matches`.

Columnas:
  - stage: match | en_revision | entrevista | seleccionado | descartado (los matches existentes quedan en "match")
  - stage_updated_at: cuándo la empresa cambió la etapa por última vez

Si `stage` ya existe pero con otro tipo (por ejemplo, creada a mano o por un intento anterior que falló), la corrige.

Ejecutar desde backend/ con el entorno virtual activo (se puede repetir sin problema):
    python -m scripts.migrate_match_stages

En producción, ejecútalo contra la base de Railway ANTES de subir el código que usa estas columnas.
"""
from sqlalchemy import inspect, text

from app.database import engine

STAGE_TYPE = "ENUM('match','en_revision','entrevista','seleccionado','descartado') NOT NULL DEFAULT 'match'"
EXPECTED = "enum('match','en_revision','entrevista','seleccionado','descartado')"


def _stage_type(conn) -> str | None:
    """Tipo actual de matches.stage, tal como lo describe MySQL, o None si no existe."""
    return conn.execute(text(
        "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'matches' AND COLUMN_NAME = 'stage'"
    )).scalar()


def main() -> None:
    existing = {c["name"] for c in inspect(engine).get_columns("matches")}
    with engine.begin() as conn:
        if "stage" not in existing:
            conn.execute(text(f"ALTER TABLE matches ADD COLUMN stage {STAGE_TYPE}"))
            print("+ matches.stage")
        else:
            current = _stage_type(conn)
            if (current or "").replace(" ", "").lower() == EXPECTED:
                print("= matches.stage ya existe con el tipo correcto")
            else:
                print(f"! matches.stage tenía el tipo: {current}")
                # Las filas con un valor que no sea una etapa válida quedan en "match" antes de cambiar el tipo
                conn.execute(text(
                    "UPDATE matches SET stage = 'match' WHERE stage IS NULL OR stage NOT IN "
                    "('match','en_revision','entrevista','seleccionado','descartado')"
                ))
                conn.execute(text(f"ALTER TABLE matches MODIFY COLUMN stage {STAGE_TYPE}"))
                print(f"~ matches.stage corregida a: {_stage_type(conn)}")

        if "stage_updated_at" not in existing:
            conn.execute(text("ALTER TABLE matches ADD COLUMN stage_updated_at DATETIME NULL"))
            print("+ matches.stage_updated_at")
        else:
            print("= matches.stage_updated_at ya existe")
    print("Listo.")


if __name__ == "__main__":
    main()
