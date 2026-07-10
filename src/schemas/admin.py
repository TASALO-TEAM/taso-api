"""Pydantic schemas for admin API responses."""

from datetime import datetime
from pydantic import BaseModel, Field


class SchedulerJobInfo(BaseModel):
    """Estado de un job individual del scheduler (APScheduler)."""

    id: str = Field(..., description="Id del job (ej. 'refresh_all', 'cubanomic_daily')")
    name: str = Field(..., description="Nombre descriptivo del job")
    next_run_at: datetime | None = Field(None, description="Próxima ejecución programada (None si está pausado)")
    # Los siguientes 4 campos solo se llenan para jobs con tracking persistido
    # en scheduler_status (hoy: solo "refresh_all"). El resto de los jobs
    # de APScheduler no tienen historial en DB — ver scheduler.py.
    last_run_at: datetime | None = Field(None, description="Última ejecución (solo si hay tracking persistido)")
    last_success_at: datetime | None = Field(None, description="Último éxito (solo si hay tracking persistido)")
    error_count: int = Field(0, description="Errores consecutivos (solo si hay tracking persistido)")
    last_error: str | None = Field(None, description="Último error (solo si hay tracking persistido)")


class AdminStatusResponse(BaseModel):
    """Respuesta para GET /api/v1/admin/status.

    Lista TODOS los jobs registrados en el APScheduler del proceso, no
    solo "refresh_all" (comportamiento anterior). Ver
    docs/plans/2026-07-08-status-command-v2.md (Fase 2).
    """

    ok: bool = Field(True, description="Estado de la respuesta")
    is_scheduler_running: bool = Field(..., description="Si el scheduler global está corriendo")
    jobs: list[SchedulerJobInfo] = Field(default_factory=list, description="Todos los jobs registrados")
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
