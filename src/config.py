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

    # Avisos de arranque/apagado/errores al grupo de soporte (mismo grupo
    # que ya usan taso-gcg y taso-bot). taso-api no tiene bot de Telegram
    # propio, así que LOG_BOT_TOKEN reutiliza el token de taso-gcg (ya es
    # admin de ese grupo) solo para mandar estos avisos vía sendMessage.
    # Si cualquiera de las dos queda vacía, no se manda nada — el resto de
    # la app sigue funcionando igual.
    log_chat_id: str = Field(
        default="",
        description="Chat ID de Telegram donde se mandan avisos de arranque/errores",
    )
    log_bot_token: str = Field(
        default="",
        description="Token del bot (reutiliza el de taso-gcg) usado solo para mandar estos avisos",
    )

    # Gestión de base de datos (comando /db en taso-bot) — ver
    # docs/plans/2026-08-01-comando-db-gestion-retencion-tasas.md
    db_backup_dir: str = Field(
        default="/var/backups/tasalo",
        description="Directorio (fuera del repo) donde se guardan los backups de la DB",
    )
    db_backup_retention: int = Field(
        default=2,
        description="Cantidad de backups a conservar; al crear uno nuevo se borra el más antiguo si se excede",
    )
    rates_retention_days: int = Field(
        default=365,
        description="Días de retención para rate_snapshots/history_snapshots antes de podarlos",
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
