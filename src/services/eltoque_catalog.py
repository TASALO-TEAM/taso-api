"""Catalogo de monedas de ElToque para los clientes: nombre, grupo, orden y calidad.

La API manda esto junto a cada tasa para que miniapp, Android y extensiones no tengan que
conocer cada moneda ni repetir el orden (mismo patron que `qvapay_meta`).

- group: "main" (principales), "crypto" o "other".
- tier: "reference" si Cubanomic la publica con 0 ofertas reales (valor fijo, no mercado);
  "market" en cualquier otro caso (API oficial u ofertas >= 1).
- order: posicion dentro del grupo; las monedas sin posicion van al final por codigo.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.schemas.rates import ElToqueRate

GROUP_RANK = {"main": 0, "crypto": 1, "other": 2}

# codigo -> (nombre, grupo, orden dentro del grupo)
_CATALOG: dict[str, tuple[str, str, int | None]] = {
    "EUR": ("Euro", "main", 1),
    "USD": ("Dólar", "main", 2),
    "ZELLE": ("Zelle", "main", 3),
    "MLC": ("USD en saldo de cuenta bancaria", "main", 4),
    "CLA": ("Tarjeta Clásica", "main", 5),
    "BTC": ("Bitcoin", "crypto", 1),
    "TRX": ("Tron", "crypto", 2),
    "USDT": ("Tether (TRC20)", "crypto", 3),
    "BNB": ("BNB", "crypto", 4),
    "LTC": ("Litecoin", "crypto", 5),
    "USDT_ERC20": ("Tether (ERC20)", "crypto", 6),
    "CAD": ("Dólar canadiense", "other", 1),
    "MXN": ("Peso mexicano", "other", 2),
    "GBP": ("Libra esterlina", "other", 3),
    "AUD": ("Dólar australiano", "other", 4),
    "BRL": ("Real brasileño", "other", 5),
    "JMD": ("Dólar jamaicano", "other", None),
    "RUR": ("Rublo ruso", "other", None),
    "SVC": ("Colón salvadoreño", "other", None),
    "UYP": ("Peso uruguayo", "other", None),
}

_NO_ORDER = 999


def eltoque_meta(code: str, offers: int | None) -> dict[str, Any]:
    """{name, group, tier, offers, order} de una moneda de ElToque (`offers` None = API oficial)."""
    name, group, order = _CATALOG.get(code, (None, "other", None))
    return {
        "name": name,
        "group": group,
        "tier": "reference" if offers == 0 else "market",
        "offers": offers,
        "order": order if order is not None else _NO_ORDER,
    }


def eltoque_sort_key(code: str) -> tuple[int, int, str]:
    """Clave de orden: grupo, posicion en el grupo, codigo."""
    _, group, order = _CATALOG.get(code, (None, "other", None))
    return (GROUP_RANK[group], order if order is not None else _NO_ORDER, code)


def build_eltoque_rates(rates: dict[str, dict]) -> dict[str, "ElToqueRate"]:
    """Convierte las tasas crudas del servicio en ElToqueRate, ordenadas por grupo y posicion."""
    from src.schemas.rates import ElToqueRate

    return {
        code: ElToqueRate(
            rate=info.get("rate", 0) or 0,
            change=info.get("change", "neutral"),
            prev_rate=info.get("prev_rate"),
            **eltoque_meta(code, info.get("offers")),
        )
        for code, info in sorted(rates.items(), key=lambda kv: eltoque_sort_key(kv[0]))
    }
