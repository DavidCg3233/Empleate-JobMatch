"""Prueba rápida de la conexión con MySQL.
Ejecutar:  python test_db.py   (con el entorno virtual activado)
Funciona desde backend/ o desde backend/tests/.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE if (HERE / "app").exists() else HERE.parent
sys.path.insert(0, str(BACKEND))

try:
    from sqlalchemy import text

    from app.database import engine

    with engine.connect() as conn:
        version = conn.execute(text("SELECT VERSION()")).scalar()
        tables = conn.execute(text("SHOW TABLES")).fetchall()
    print("Conexión OK")
    print("Versión de MySQL:", version)
    print("Tablas y vistas encontradas:", len(tables), "(esperado: 27)")
except Exception as exc:  # noqa: BLE001
    print("FALLÓ la conexión:", type(exc).__name__)
    print(exc)
    sys.exit(1)