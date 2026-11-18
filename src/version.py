"""Version de la API: se lee de pyproject.toml, que sube el hook de pre-commit en cada commit.

Antes `main.py` tenia una constante a mano ("1.6.0") que nadie actualizaba, y el aviso de Telegram
anunciaba siempre la misma version sin importar los cambios ni los reinicios.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read_version() -> str:
    try:
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        return str(data["project"]["version"])
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"


VERSION = _read_version()
