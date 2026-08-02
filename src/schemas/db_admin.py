"""Pydantic schemas para los endpoints admin de gestión de DB (/admin/db/*).

Ver docs/plans/2026-08-01-comando-db-gestion-retencion-tasas.md.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class BackupItem(BaseModel):
    """Metadata de un backup individual."""

    filename: str = Field(..., description="Nombre del archivo de backup")
    size_bytes: int = Field(..., description="Tamaño en bytes")
    created_at: datetime = Field(..., description="Fecha de creación")
    checksum_sha256: str = Field("", description="Checksum SHA-256 del archivo")
    engine: str = Field(..., description="'postgres' o 'sqlite'")


class BackupCreateResponse(BaseModel):
    """Respuesta de POST /api/v1/admin/db/backup."""

    ok: bool = Field(True)
    data: BackupItem
    backups_remaining: int = Field(..., description="Cantidad de backups tras aplicar la retención")


class BackupListResponse(BaseModel):
    """Respuesta de GET /api/v1/admin/db/backups."""

    ok: bool = Field(True)
    data: list[BackupItem] = Field(default_factory=list)


class PruneRatesResponse(BaseModel):
    """Respuesta de POST /api/v1/admin/db/prune-rates."""

    ok: bool = Field(True)
    rate_snapshots_deleted: int
    history_snapshots_deleted: int
    cutoff_date: str
    days: int
