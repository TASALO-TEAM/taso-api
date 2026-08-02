"""Comandos de gestión de base de datos: backup, list, restore, prune-rates.

Uso:
    python -m src.cli.db backup
    python -m src.cli.db list
    python -m src.cli.db restore tasalo_20260801_031000.dump --confirm=RESTORE
    python -m src.cli.db prune-rates [--days 365]

`restore` es la ÚNICA vía de restauración en todo el sistema — no existe
como endpoint HTTP ni como comando de Telegram. Ver
docs/plans/2026-08-01-comando-db-gestion-retencion-tasas.md.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import typer
from sqlalchemy.engine import make_url

from src.config import get_settings
from src.services import db_backup_service
from src.services.db_backup_service import BackupError

app = typer.Typer(help="Gestión de la base de datos de taso-api")


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


@app.command()
def backup():
    """Crea un backup manual y aplica la retención configurada."""
    try:
        info = db_backup_service.create_backup()
    except BackupError as e:
        typer.secho(f"❌ Error creando backup: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    remaining = len(db_backup_service.list_backups())
    typer.secho(
        f"✅ Backup creado: {info.filename} ({_fmt_size(info.size_bytes)}, {info.engine})",
        fg=typer.colors.GREEN,
    )
    typer.echo(f"   sha256: {info.checksum_sha256}")
    typer.echo(f"   Backups restantes tras retención: {remaining}")


@app.command(name="list")
def list_backups_cmd():
    """Lista los backups existentes."""
    infos = db_backup_service.list_backups()
    if not infos:
        typer.echo("No hay backups todavía.")
        return
    for info in infos:
        typer.echo(
            f"{info.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}  "
            f"{info.filename}  {_fmt_size(info.size_bytes)}  ({info.engine})"
        )


@app.command()
def restore(
    filename: str = typer.Argument(..., help="Nombre del archivo de backup a restaurar"),
    confirm: str = typer.Option(
        "", "--confirm", help="Debe ser exactamente 'RESTORE' para proceder"
    ),
):
    """Restaura la base de datos desde un backup. DESTRUCTIVO.

    Antes de restaurar, crea automáticamente un backup de seguridad del
    estado actual. Requiere --confirm=RESTORE explícito.
    """
    if confirm != "RESTORE":
        typer.secho(
            "❌ Operación destructiva. Vuelve a ejecutar con --confirm=RESTORE "
            "para confirmar que entiendes que esto reemplaza los datos actuales.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    try:
        backup_path = db_backup_service.get_backup_path(filename)
    except BackupError as e:
        typer.secho(f"❌ {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("⚠️  Creando backup de seguridad del estado actual antes de restaurar...", fg=typer.colors.YELLOW)
    try:
        safety = db_backup_service.create_backup()
        typer.echo(f"   Backup de seguridad: {safety.filename}")
    except BackupError as e:
        typer.secho(f"❌ No se pudo crear el backup de seguridad, abortando restore: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    settings = get_settings()
    engine = db_backup_service._detect_engine(settings.database_url)

    if engine == "postgres":
        _restore_postgres(settings.database_url, backup_path)
    else:
        _restore_sqlite(settings.database_url, backup_path)

    typer.secho(f"✅ Restauración completada desde {filename}.", fg=typer.colors.GREEN)


def _restore_postgres(database_url: str, backup_path: Path) -> None:
    url = make_url(database_url)
    pg_url = url.set(drivername="postgresql")
    cmd = [
        "pg_restore", "--clean", "--if-exists", "--no-owner",
        "-d", pg_url.render_as_string(hide_password=False),
        str(backup_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    if result.returncode != 0:
        typer.secho(f"❌ pg_restore falló: {result.stderr[:1000]}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


def _restore_sqlite(database_url: str, backup_path: Path) -> None:
    import gzip
    import shutil

    url = make_url(database_url)
    db_path = Path(url.database)
    with gzip.open(backup_path, "rb") as src, open(db_path, "wb") as out:
        shutil.copyfileobj(src, out)


@app.command(name="prune-rates")
def prune_rates(
    days: int = typer.Option(None, help="Días de retención (default: RATES_RETENTION_DAYS, 365)"),
):
    """Borra rate_snapshots/history_snapshots más viejos que el umbral."""
    from src.services import retention_service
    from src import database
    from src.database import get_engine

    async def _run():
        settings = get_settings()
        get_engine(settings.database_url, echo=False)
        async with database.async_session_factory() as db:
            return await retention_service.prune_old_rates(db, days=days)

    result = asyncio.run(_run())
    typer.secho(
        f"✅ Poda completada: {result['rate_snapshots_deleted']} rate_snapshots, "
        f"{result['history_snapshots_deleted']} history_snapshots borrados "
        f"(> {result['days']} días, cutoff {result['cutoff_date']})",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":
    app()
