"""Guardado de archivos en disco (backend/uploads/).

Flujo de la hoja de vida en el registro:
  1. El aspirante sube el CV -> se guarda en uploads/tmp/ con un id temporal.
  2. Al terminar el registro -> el archivo pasa a uploads/cvs/ y queda ligado a su perfil.
Los temporales que nadie usó se borran después de 24 horas.
"""
import json
import re
import shutil
import time
import uuid
from pathlib import Path

from app.config import settings

TMP_MAX_AGE_SECONDS = 24 * 60 * 60
_UPLOAD_ID_RE = re.compile(r"^[a-f0-9]{32}$")


def _dir(name: str) -> Path:
    path = Path(settings.UPLOAD_DIR) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_upload_dirs() -> None:
    for name in ("tmp", "cvs", "logos"):
        _dir(name)


def is_valid_upload_id(upload_id: str) -> bool:
    return bool(_UPLOAD_ID_RE.match(upload_id or ""))


def save_temp_cv(content: bytes, ext: str, original_name: str, text: str) -> str:
    """Guarda el CV temporalmente y devuelve su id."""
    cleanup_temp()
    upload_id = uuid.uuid4().hex
    tmp = _dir("tmp")
    (tmp / f"{upload_id}{ext}").write_bytes(content)
    meta = {"ext": ext, "original_name": original_name[:255], "text": text}
    (tmp / f"{upload_id}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return upload_id


def load_temp_cv(upload_id: str) -> dict | None:
    """Devuelve los datos del CV temporal (ext, original_name, text) o None si no existe."""
    if not is_valid_upload_id(upload_id):
        return None
    meta_file = _dir("tmp") / f"{upload_id}.json"
    if not meta_file.exists():
        return None
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    if not (_dir("tmp") / f"{upload_id}{meta['ext']}").exists():
        return None
    return meta


def promote_temp_cv(upload_id: str) -> str:
    """Mueve el CV de tmp/ a cvs/ y devuelve la ruta relativa que se guarda en la BD."""
    meta = load_temp_cv(upload_id)
    if meta is None:
        raise FileNotFoundError(upload_id)
    tmp = _dir("tmp")
    final_name = f"{upload_id}{meta['ext']}"
    shutil.move(str(tmp / final_name), str(_dir("cvs") / final_name))
    (tmp / f"{upload_id}.json").unlink(missing_ok=True)
    return f"cvs/{final_name}"


def cleanup_temp() -> None:
    """Borra los archivos temporales con más de 24 horas."""
    limit = time.time() - TMP_MAX_AGE_SECONDS
    for file in _dir("tmp").iterdir():
        try:
            if file.is_file() and file.stat().st_mtime < limit:
                file.unlink()
        except OSError:
            pass  # si no se puede borrar ahora, se intentará la próxima vez


# ---------------- Hoja de vida definitiva (perfil del aspirante) ----------------
def save_cv(content: bytes, ext: str) -> str:
    """Guarda una hoja de vida en cvs/ y devuelve la ruta relativa que se guarda en la BD."""
    name = f"{uuid.uuid4().hex}{ext}"
    (_dir("cvs") / name).write_bytes(content)
    return f"cvs/{name}"


def resolve_upload(relative_path: str | None) -> Path | None:
    """Ruta absoluta de un archivo subido, solo si existe y está dentro de uploads/ (evita rutas maliciosas)."""
    if not relative_path:
        return None
    base = Path(settings.UPLOAD_DIR).resolve()
    path = (base / relative_path).resolve()
    if base not in path.parents or not path.is_file():
        return None
    return path


def delete_upload(relative_path: str | None) -> None:
    path = resolve_upload(relative_path)
    if path is not None:
        try:
            path.unlink()
        except OSError:
            pass  # si no se puede borrar ahora (archivo en uso), no afecta al usuario
