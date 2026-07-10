"""Pydantic schemas para estadísticas del bot."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BotUserStats(BaseModel):
    """Estadísticas de usuarios del bot."""

    total: int = Field(..., description="Total de usuarios únicos")
    new_7d: int = Field(..., description="Usuarios nuevos en los últimos 7 días")
    active_24h: int = Field(..., description="Usuarios activos en las últimas 24 horas")
    active_recent: int = Field(0, description="Usuarios activos en los últimos 15 minutos")


class CommandUsageItem(BaseModel):
    """Uso de un comando específico."""

    command: str = Field(..., description="Nombre del comando")
    count: int = Field(..., description="Cantidad de veces usado")


class CommandUsageStats(BaseModel):
    """Estadísticas de uso de comandos."""

    commands_24h: list[CommandUsageItem] = Field(default_factory=list, description="Comandos usados en 24h")
    commands_7d: list[CommandUsageItem] = Field(default_factory=list, description="Comandos usados en 7d")
    commands_30d: list[CommandUsageItem] = Field(default_factory=list, description="Comandos usados en 30d")


class TopUserItem(BaseModel):
    """Usuario top en el ranking."""

    username: Optional[str] = Field(None, description="Nombre de usuario")
    user_id: int = Field(..., description="ID del usuario")
    total_commands: int = Field(..., description="Total de comandos ejecutados")


class TopUserStats(BaseModel):
    """Ranking de usuarios top."""

    top_users: list[TopUserItem] = Field(default_factory=list, description="Top 10 usuarios")


class ApiPerformanceStats(BaseModel):
    """Estadísticas de rendimiento de la API.

    Nota: total_requests_24h/success_rate siguen calculándose a partir de
    bot_command_stats (uso por comandos del bot). avg_response_ms ahora
    sale de api_request_log (todas las requests HTTP reales, no solo las
    reportadas por el bot) — ver get_api_performance_stats.
    """

    success_rate: float = Field(..., description="Porcentaje de éxito (0-100)")
    avg_response_ms: float = Field(..., description="Tiempo promedio de respuesta en ms (últimas 24h, todas las fuentes)")
    total_requests_24h: int = Field(..., description="Total de requests en 24h")


class ApiUsageByClient(BaseModel):
    """Uso de la API desglosado por cliente (bot/app/ext/extmf/web/unknown)."""

    client_id: str = Field(..., description="Identificador del cliente (header X-Client-Id o inferido)")
    requests: int = Field(..., description="Total de requests en la ventana")
    errors: int = Field(..., description="Requests con status_code >= 400")
    avg_duration_ms: float = Field(..., description="Duración promedio en ms")


class ApiUsageByEndpoint(BaseModel):
    """Uso de la API desglosado por endpoint (path)."""

    path: str = Field(..., description="Path del endpoint")
    requests: int = Field(..., description="Total de requests en la ventana")
    errors: int = Field(..., description="Requests con status_code >= 400")
    avg_duration_ms: float = Field(..., description="Duración promedio en ms")


class ApiUsageStats(BaseModel):
    """Resumen de uso de la API pública (todas las fuentes), para /status."""

    ok: bool = Field(True, description="Estado de la respuesta")
    window: str = Field(..., description="Ventana consultada: 24h | 7d | 30d")
    total_requests: int = Field(..., description="Total de requests en la ventana")
    total_errors: int = Field(..., description="Total de requests con status_code >= 400")
    error_rate: float = Field(..., description="Porcentaje de error (0-100)")
    avg_duration_ms: float = Field(..., description="Duración promedio en ms")
    by_client: list[ApiUsageByClient] = Field(default_factory=list, description="Desglose por cliente")
    by_endpoint: list[ApiUsageByEndpoint] = Field(default_factory=list, description="Top endpoints por volumen")
    updated_at: datetime = Field(..., description="Cuándo se generaron las estadísticas")


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


class UserIdsResponse(BaseModel):
    """Lista de todos los user_id registrados en bot_users.

    Endpoint admin-only (require_auth vía X-API-Key, ver src/routers/stats.py).
    Usado por taso-bot para el comando /ms (broadcast a todos los usuarios).
    No exponer nunca sin autenticación: es información de usuarios reales.
    """

    ok: bool = Field(True, description="Estado de la respuesta")
    data: list[int] = Field(default_factory=list, description="Lista de user_id (Telegram)")


class UserLookupData(BaseModel):
    """Resultado de la búsqueda de un usuario por username."""

    user_id: int = Field(..., description="ID del usuario (Telegram)")


class UserLookupResponse(BaseModel):
    """Resultado de GET /users/lookup?username=....

    Endpoint admin-only (ver src/routers/stats.py). Usado por taso-bot
    para el comando /ms <@usuario> (mensaje a un único usuario).
    `data` es None si el username no está registrado en bot_users.
    """

    ok: bool = Field(True, description="Estado de la respuesta")
    data: Optional[UserLookupData] = Field(None, description="Datos del usuario encontrado, o None")
