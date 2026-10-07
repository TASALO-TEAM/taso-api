"""Scrapers y clientes para fuentes de tasas de cambio."""

from .eltoque import fetch_eltoque
from .binance import fetch_binance
from .cadeca import fetch_cadeca
from .bcc import fetch_bcc
from .qvapay import fetch_qvapay

__all__ = ["fetch_eltoque", "fetch_binance", "fetch_cadeca", "fetch_bcc", "fetch_qvapay"]
