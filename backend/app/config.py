"""Carga las variables del archivo .env en un objeto tipado."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Carpeta backend/ (el .env se busca ahí, sin importar desde dónde se ejecute el programa)
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str = "jobmatch"

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    MAX_LOGIN_ATTEMPTS: int = 3
    LOCK_MINUTES: int = 15

    # Orígenes permitidos cuando las páginas se abren con Live Server (puerto 5500).
    # Si las sirve el mismo backend no hace falta: página y API están en el mismo sitio.
    FRONTEND_ORIGINS: str = "http://127.0.0.1:5500,http://localhost:5500"
    # El backend también sirve las páginas de frontend/ (abrir http://127.0.0.1:8000)
    SERVE_FRONTEND: bool = True
    # Dirección donde se abren las páginas (para el enlace del correo de recuperación)
    FRONTEND_URL: str = "http://127.0.0.1:8000"
    RESET_TOKEN_MINUTES: int = 30

    # Correo (opcional). Si SMTP_HOST está vacío, el correo se imprime en la consola.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "Empléate Jobmatch <no-reply@empleate.local>"
    SMTP_USE_TLS: bool = True

    # Archivos subidos
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_CV_MB: int = 5

    # IA para leer hojas de vida: claude | openai | none (sin IA se usa el lector por reglas)
    AI_PROVIDER: str = "none"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-5-5"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    AI_TIMEOUT_SECONDS: int = 60

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]


settings = Settings()
