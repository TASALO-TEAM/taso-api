"""Configuración de la aplicación cargada desde variables de entorno."""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Configuración de la aplicación cargada desde variables de entorno."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Database
    database_url: str
    
    # ElToque API
    eltoque_api_key: str = ""
    eltoque_api_url: str = "https://tasas.eltoque.com/v1/trmi"
    
    # Security
    admin_api_key: str = "changeme"
    
    # Scheduler
    refresh_interval_minutes: int = 5
    
    # CORS
    allowed_origins: str = "*"

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for caching"
    )
    redis_ttl_cubanomic: int = Field(
        default=86400,  # 24 hours in seconds
        description="TTL for Cubanomic cache in seconds"
    )

    def model_post_init(self, __context) -> None:
        """Validar configuración después de inicializar."""
        if self.refresh_interval_minutes < 1:
            raise ValueError("REFRESH_INTERVAL_MINUTES debe ser >= 1")
    
    @property
    def allowed_origins_list(self) -> list[str]:
        """Retorna lista de orígenes permitidos."""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Obtener configuración singleton cacheada."""
    return Settings()
