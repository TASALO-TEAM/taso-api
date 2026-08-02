"""Router admin para gestión de base de datos (backups + poda de tasas).

Protegido por require_auth (X-API-Key), igual que el resto de admin.py.
Deliberadamente NO expone restore — esa operación vive solo en la CLI
local del VPS (src/cli/db.py). Ver
docs/plans/2026-08-01-comando-db-gestion-retencion-tasas.md.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.middleware.auth import require_auth
from src.services import db_backup_service
from src.services.db_backup_service import BackupError
from src.services import retention_service
from src.services.alert_notifier import notify as notify_support_group
from src.schemas.db_admin import (
    BackupItem,
    BackupCreateResponse,
    BackupListResponse,
    PruneRatesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_auth)])


def _to_item(info) -> BackupItem:
    return BackupItem(
        filename=info.filename,
        size_bytes=info.size_bytes,
        created_at=info.created_at,
        checksum_sha256=info.checksum_sha256,
        engine=info.engine,
    )


@router.post("/db/backup", response_model=BackupCreateResponse)
async def create_backup() -> BackupCreateResponse:
    """Crea un backup manual de la base de datos y aplica la retención
    configurada (por defecto 2 backups)."""
    try:
        info = db_backup_service.create_backup()
    except BackupError as e:
        logger.error("❌ Error creando backup: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    remaining = len(db_backup_service.list_backups())
    await notify_support_group(
        f"💾 Backup manual de taso-api creado: {info.filename} "
        f"({info.size_bytes / 1024 / 1024:.1f} MB). Backups restantes: {remaining}."
    )

    return BackupCreateResponse(
        data=_to_item(info),
        backups_remaining=remaining,
    )


@router.get("/db/backups", response_model=BackupListResponse)
async def list_backups() -> BackupListResponse:
    """Lista los backups existentes, más reciente primero."""
    infos = db_backup_service.list_backups()
    return BackupListResponse(data=[_to_item(i) for i in infos])


@router.get("/db/backups/{filename}/download")
async def download_backup(filename: str) -> FileResponse:
    """Sirve un backup para que taso-bot lo reenvíe como documento de
    Telegram (mismo patrón que /log)."""
    try:
        path = db_backup_service.get_backup_path(filename)
    except BackupError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return FileResponse(path=path, filename=path.name, media_type="application/octet-stream")


@router.post("/db/prune-rates", response_model=PruneRatesResponse)
async def prune_rates(db: AsyncSession = Depends(get_db)) -> PruneRatesResponse:
    """Dispara on-demand la poda de tasas históricas (>1 año). El mismo
    trabajo corre automáticamente todos los días vía el scheduler."""
    result = await retention_service.prune_old_rates(db)

    await notify_support_group(
        f"🧹 Poda de tasas ejecutada (on-demand): "
        f"{result['rate_snapshots_deleted']} rate_snapshots, "
        f"{result['history_snapshots_deleted']} history_snapshots borrados "
        f"(> {result['days']} días)."
    )

    return PruneRatesResponse(
        rate_snapshots_deleted=result["rate_snapshots_deleted"],
        history_snapshots_deleted=result["history_snapshots_deleted"],
        cutoff_date=result["cutoff_date"],
        days=result["days"],
    )
