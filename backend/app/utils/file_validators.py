"""Validación de archivos subidos (extensión, tamaño y contenido real)."""
from pathlib import Path

from app.config import settings
from app.core.exceptions import api_error

# Firma de los primeros bytes de cada formato: evita archivos renombrados
CV_SIGNATURES = {
    ".pdf": b"%PDF",
    ".docx": b"PK\x03\x04",  # un .docx es un archivo ZIP
    ".odt": b"PK\x03\x04",  # OpenDocument (LibreOffice / Google Docs) también es ZIP
    ".rtf": b"{\\rtf",
}
CV_EXTENSIONS = (*CV_SIGNATURES, ".txt")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif", ".bmp")
ACCEPTED_TEXT = "PDF, Word (.docx), OpenDocument (.odt), RTF o texto (.txt)"


def validate_cv(filename: str | None, content: bytes) -> str:
    """Devuelve la extensión o lanza un error 400/413 con un mensaje claro."""
    ext = Path(filename or "").suffix.lower()
    if ext == ".doc":
        raise api_error(400, "El formato .doc (Word 97-2003) no es compatible. Guárdalo como .docx o PDF.")
    if ext in IMAGE_EXTENSIONS:
        raise api_error(400, "Subiste una imagen. Sube la hoja de vida en PDF o Word para poder leer su texto.")
    if ext not in CV_EXTENSIONS:
        raise api_error(400, f"La hoja de vida debe ser un archivo {ACCEPTED_TEXT}.")
    if not content:
        raise api_error(400, "El archivo está vacío.")
    if len(content) > settings.MAX_CV_MB * 1024 * 1024:
        raise api_error(413, f"El archivo supera el tamaño máximo de {settings.MAX_CV_MB} MB.")
    if ext == ".txt":
        if b"\x00" in content[:4096]:
            raise api_error(400, "El archivo .txt no es texto. Revisa que sea la hoja de vida correcta.")
    elif not content.startswith(CV_SIGNATURES[ext]):
        raise api_error(400, "El archivo está dañado o no corresponde a su extensión.")
    return ext
