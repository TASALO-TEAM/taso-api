"""Backups de la base de datos de taso-api.

Detecta el motor (SQLite vs Postgres) igual que src/database.py, crea
backups comprimidos con checksum, y aplica retención (por defecto 2 —
ver Settings.db_backup_retention): al crear uno nuevo, si ya hay más de
los permitidos, borra el/los más antiguos.

Restore NO vive aquí como operación remota — ver src/cli/db.py. Este
módulo solo expone create_backup()/list_backups() para que tanto la CLI
como los endpoints admin (src/routers/db_admin.py) reutilicen la misma
lógica.
"""

from __future__ import annotations

import gzip
import hashlib
import logging
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

from src.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class BackupInfo:
    filename: str
    path: Path
    size_bytes: int
    created_at: datetime
    checksum_sha256: str
    engine: str  # "postgres" | "sqlite"


class BackupError(Exception):
    """Error al crear, listar o verificar un backup."""


def _backup_dir() -> Path:
    settings = get_settings()
    d = Path(settings.db_backup_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _detect_engine(database_url: str) -> str:
    url = make_url(database_url)
    return "sqlite" if url.drivername.startswith("sqlite") else "postgres"


def _backup_postgres(database_url: str, dest_dir: Path, ts: str) -> Path:
    """pg_dump en formato custom (-Fc), ya comprimido por defecto."""
    url = make_url(database_url)
    # pg_dump no entiende el driver "+asyncpg" de SQLAlchemy — necesita el DSN plano
    pg_url = url.set(drivername="postgresql")
    filename = f"tasalo_{ts}.dump"
    dest = dest_dir / filename

    cmd = ["pg_dump", "-Fc", "-f", str(dest), pg_url.render_as_string(hide_password=False)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise BackupError(f"pg_dump falló (código {result.returncode}): {result.stderr[:500]}")
    return dest


def _backup_sqlite(database_url: str, dest_dir: Path, ts: str) -> Path:
    """Copia el archivo .db y lo comprime con gzip."""
    url = make_url(database_url)
    db_path = Path(url.database)
    if not db_path.exists():
        raise BackupError(f"No se encontró el archivo SQLite: {db_path}")

    filename = f"tasalo_{ts}.sqlite3.gz"
    dest = dest_dir / filename
    with open(db_path, "rb") as src, gzip.open(dest, "wb") as out:
        shutil.copyfileobj(src, out)
    return dest


def create_backup() -> BackupInfo:
    """Crea un backup nuevo y aplica la retención configurada.

    Returns:
        BackupInfo del backup recién creado.

    Raises:
        BackupError si pg_dump/la copia fallan.
    """
    settings = get_settings()
    engine = _detect_engine(settings.database_url)
    dest_dir = _backup_dir()
    ts = _timestamp()

    if engine == "postgres":
        dump_path = _backup_postgres(settings.database_url, dest_dir, ts)
    else:
        dump_path = _backup_sqlite(settings.database_url, dest_dir, ts)

    checksum = _sha256_of(dump_path)
    checksum_path = dump_path.with_suffix(dump_path.suffix + ".sha256")
    checksum_path.write_text(f"{checksum}  {dump_path.name}\n")

    size_bytes = dump_path.stat().st_size
    logger.info(
        "💾 Backup creado: %s (%s, %d bytes)", dump_path.name, engine, size_bytes
    )

    removed = _prune_old_backups(dest_dir, keep=settings.db_backup_retention)
    if removed:
        logger.info("🧹 Backups podados por retención: %s", ", ".join(removed))

    return BackupInfo(
        filename=dump_path.name,
        path=dump_path,
        size_bytes=size_bytes,
        created_at=datetime.now(timezone.utc),
        checksum_sha256=checksum,
        engine=engine,
    )


def _prune_old_backups(dest_dir: Path, keep: int) -> list[str]:
    """Si hay más de `keep` backups, borra los más antiguos (y su .sha256)."""
    dumps = sorted(
        [p for p in dest_dir.iterdir() if p.suffix in (".dump", ".gz")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    to_remove = dumps[keep:]
    removed_names = []
    for p in to_remove:
        checksum_path = p.with_suffix(p.suffix + ".sha256")
        try:
            p.unlink(missing_ok=True)
            checksum_path.unlink(missing_ok=True)
            removed_names.append(p.name)
        except OSError as e:
            logger.warning("⚠️ No se pudo borrar backup antiguo %s: %s", p.name, e)
    return removed_names


def list_backups() -> list[BackupInfo]:
    """Lista los backups existentes, más reciente primero."""
    dest_dir = _backup_dir()
    dumps = sorted(
        [p for p in dest_dir.iterdir() if p.suffix in (".dump", ".gz")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    infos = []
    for p in dumps:
        checksum_path = p.with_suffix(p.suffix + ".sha256")
        checksum = ""
        if checksum_path.exists():
            checksum = checksum_path.read_text().split()[0]
        stat = p.stat()
        infos.append(
            BackupInfo(
                filename=p.name,
                path=p,
                size_bytes=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                checksum_sha256=checksum,
                engine="postgres" if p.suffix == ".dump" else "sqlite",
            )
        )
    return infos


def get_backup_path(filename: str) -> Path:
    """Resuelve un filename a su ruta dentro de db_backup_dir, validando
    que no se escape del directorio (path traversal)."""
    dest_dir = _backup_dir()
    candidate = (dest_dir / filename).resolve()
    if dest_dir.resolve() not in candidate.parents and candidate != dest_dir.resolve():
        raise BackupError("Nombre de archivo inválido")
    if not candidate.exists():
        raise BackupError(f"Backup no encontrado: {filename}")
    return candidate
