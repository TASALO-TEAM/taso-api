"""Scrapers y clientes para fuentes de tasas de cambio."""

from .eltoque import fetch_eltoque
from .binance import fetch_binance
from .cadeca import fetch_cadeca
from .bcc import fetch_bcc

__all__ = ["fetch_eltoque", "fetch_binance", "fetch_cadeca", "fetch_bcc"]
