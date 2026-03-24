"""Pydantic schemas para estadísticas del bot."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BotUserStats(BaseModel):
    """Estadísticas de usuarios del bot."""

    total: int = Field(..., description="Total de usuarios únicos")
    new_7d: int = Field(..., description="Usuarios nuevos en los últimos 7 días")
    active_24h: int = Field(..., description="Usuarios activos en las últimas 24 horas")


class CommandUsageItem(BaseModel):
    """Uso de un comando específico."""

    command: str = Field(..., description="Nombre del comando")
    count: int = Field(..., description="Cantidad de veces usado")


class CommandUsageStats(BaseModel):
    """Estadísticas de uso de comandos."""

    commands_24h: list[CommandUsageItem] = Field(default_factory=list, description="Comandos usados en 24h")
    commands_7d: list[CommandUsageItem] = Field(default_factory=list, description="Comandos usados en 7d")


class TopUserItem(BaseModel):
    """Usuario top en el ranking."""

    username: Optional[str] = Field(None, description="Nombre de usuario")
    user_id: int = Field(..., description="ID del usuario")
    total_commands: int = Field(..., description="Total de comandos ejecutados")


class TopUserStats(BaseModel):
    """Ranking de usuarios top."""

    top_users: list[TopUserItem] = Field(default_factory=list, description="Top 10 usuarios")


class ApiPerformanceStats(BaseModel):
    """Estadísticas de rendimiento de la API."""

    success_rate: float = Field(..., description="Porcentaje de éxito (0-100)")
    avg_response_ms: float = Field(..., description="Tiempo promedio de respuesta en ms")
    total_requests_24h: int = Field(..., description="Total de requests en 24h")


class BotStatsSummary(BaseModel):
    """Resumen completo de estadísticas del bot."""

    ok: bool = Field(True, description="Estado de la respuesta")
    users: BotUserStats = Field(..., description="Estadísticas de usuarios")
    commands: CommandUsageStats = Field(..., description="Estadísticas de comandos")
    top_users: TopUserStats = Field(..., description="Usuarios top")
    performance: ApiPerformanceStats = Field(..., description="Rendimiento de API")
    updated_at: datetime = Field(..., description="Cuándo se generaron las estadísticas")


class TrackCommandRequest(BaseModel):
    """Request para trackear un comando."""

    command: str = Field(..., description="Nombre del comando ejecutado")
    user_id: int = Field(..., description="ID del usuario")
    username: Optional[str] = Field(None, description="Username del usuario")
    source: Optional[str] = Field(None, description="Fuente consultada si aplica")
    success: bool = Field(True, description="Si el comando se ejecutó con éxito")


class TrackCommandResponse(BaseModel):
    """Respuesta para trackeo de comando."""

    ok: bool = Field(True, description="Estado de la respuesta")
    message: str = Field("Comando trackeado", description="Mensaje de confirmación")
