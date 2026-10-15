"""Validación de archivos subidos (extensión, tamaño y contenido real)."""
from pathlib import Path

from app.config import settings
from app.core.exceptions import api_error

# Firma de los primeros bytes de cada formato: evita archivos renombrados
CV_SIGNATURES = {
    ".pdf": b"%PDF",
    ".docx": b"PK\x03\x04",  # un .docx es un archivo ZIP
}


def validate_cv(filename: str | None, content: bytes) -> str:
    """Devuelve la extensión (.pdf / .docx) o lanza un error 400/413."""
    ext = Path(filename or "").suffix.lower()
    if ext == ".doc":
        raise api_error(400, "El formato .doc (Word 97-2003) no es compatible. Guárdalo como .docx o PDF.")
    if ext not in CV_SIGNATURES:
        raise api_error(400, "La hoja de vida debe ser un archivo PDF o Word (.docx).")
    if not content:
        raise api_error(400, "El archivo está vacío.")
    if len(content) > settings.MAX_CV_MB * 1024 * 1024:
        raise api_error(413, f"El archivo supera el tamaño máximo de {settings.MAX_CV_MB} MB.")
    if not content.startswith(CV_SIGNATURES[ext]):
        raise api_error(400, "El archivo está dañado o no corresponde a su extensión.")
    return ext
