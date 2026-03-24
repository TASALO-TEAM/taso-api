"""Pydantic schemas for admin API responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class SchedulerStatusResponse(BaseModel):
    """Estado del scheduler para respuesta de admin/status."""

    is_running: bool = Field(False, description="Si el scheduler está corriendo actualmente")
    last_run_at: datetime | None = Field(None, description="Última vez que se ejecutó el scheduler")
    last_success_at: datetime | None = Field(None, description="Última vez que se ejecutó con éxito")
    error_count: int = Field(0, description="Cantidad de errores consecutivos")
    last_error: str | None = Field(None, description="Último error ocurrido")
    updated_at: datetime = Field(..., description="Cuándo se actualizó este registro")


class AdminStatusResponse(BaseModel):
    """Respuesta para GET /api/v1/admin/status."""

    ok: bool = Field(True, description="Estado de la respuesta")
    scheduler: SchedulerStatusResponse = Field(..., description="Estado del scheduler")
    updated_at: datetime = Field(..., description="Cuándo se consultó el estado")


class RefreshResult(BaseModel):
    """Resultado del refresh para una fuente."""

    source: str = Field(..., description="Nombre de la fuente")
    success: bool = Field(..., description="Si el refresh fue exitoso")
    currencies_count: int = Field(0, description="Cantidad de monedas obtenidas")
    error: str | None = Field(None, description="Error si ocurrió")


class RefreshData(BaseModel):
    """Datos combinados del refresh."""

    results: list[RefreshResult] = Field(default_factory=list, description="Resultados por fuente")
    total_success: int = Field(0, description="Cantidad de fuentes exitosas")
    total_failed: int = Field(0, description="Cantidad de fuentes fallidas")


class RefreshResponse(BaseModel):
    """Respuesta para POST /api/v1/admin/refresh."""

    ok: bool = Field(True, description="Estado de la respuesta")
    data: RefreshData = Field(..., description="Resultados del refresh")
    completed_at: datetime = Field(..., description="Cuándo se completó el refresh")
