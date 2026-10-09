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

    FRONTEND_ORIGINS: str = "http://127.0.0.1:5500,http://localhost:5500"

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]


settings = Settings()