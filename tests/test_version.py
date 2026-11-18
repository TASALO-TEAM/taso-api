"""La version que anuncia la API (aviso de Telegram, /health) sale de pyproject.toml, no de una constante a mano."""

import tomllib
from pathlib import Path

from src.version import VERSION

ROOT = Path(__file__).resolve().parent.parent


def test_version_sale_de_pyproject():
    esperado = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    assert VERSION == esperado


def test_main_anuncia_la_misma_version():
    from src import main

    assert main.API_VERSION == VERSION
