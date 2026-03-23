"""CADECA web scraper for fetching exchange rates from official website."""

import httpx
import urllib3
from bs4 import BeautifulSoup, Tag
from typing import Optional, Dict, Any

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CADECA_URL = "https://www.cadeca.cu"
DEFAULT_TIMEOUT = 7.0

CURRENCY_NAME_MAP = {
    "DOLAR NORTEAMERICANO": "USD",
    "DOLAR ESTADOUNIDENSE": "USD",
    "EURO": "EUR",
    "LIBRA ESTERLINA": "GBP",
    "DOLAR CANADIENSE": "CAD",
    "PESO MEXICANO": "MXN",
    "FRANCO SUIZO": "CHF",
    "RUBLO": "RUB",
    "DOLAR AUSTRALIANO": "AUD",
    "YEN": "JPY",
    "MLC": "MLC",
}


def _normalize_currency_name(name: str) -> str:
    """Normaliza nombre de moneda a codigo ISO."""
    name_clean = name.strip().upper()
    if len(name_clean) <= 4 and name_clean.isalpha():
        return name_clean
    return CURRENCY_NAME_MAP.get(name_clean, name_clean)


def _parse_table(soup: BeautifulSoup) -> Optional[Dict[str, Dict[str, float]]]:
    """Parsea tabla de tasas de CADECA desde un objeto BeautifulSoup.

    Estrategia A: Buscar tabla con headers que contengan Compra/Venta.
    Estrategia B: Buscar primera tabla con >= 4 filas en tbody.
    Estrategia C: Primera tabla con >= 4 filas totales.
    """
    tabla = None

    # Estrategia A: buscar tabla con headers Compra/Venta
    for t in soup.find_all("table"):
        header_row = t.find("thead") or t.find("tr")
        if header_row:
            header_text = header_row.get_text().upper()
            if any(kw in header_text for kw in ["COMPRA", "VENTA", "BUY", "SELL"]):
                tabla = t
                break

    # Estrategia B: primera tabla con >= 4 filas en tbody
    if not tabla:
        for t in soup.find_all("table"):
            tbody = t.find("tbody")
            if tbody and len(tbody.find_all("tr")) >= 4:
                tabla = t
                break

    # Estrategia C: primera tabla con >= 4 filas totales
    if not tabla:
        for t in soup.find_all("table"):
            if len(t.find_all("tr")) >= 4:
                tabla = t
                break

    if not tabla:
        return None

    # Parsear filas de la tabla
    tbody = tabla.find("tbody")
    if tbody:
        rows = tbody.find_all("tr")
    else:
        all_rows = tabla.find_all("tr")
        rows = all_rows[1:] if len(all_rows) > 1 else []

    resultados = {}
    for fila in rows:
        columnas = fila.find_all("td")
        if len(columnas) >= 3:
            moneda_raw = columnas[1].get_text(strip=True)
            compra_txt = columnas[2].get_text(strip=True)
            venta_txt = (
                columnas[3].get_text(strip=True) if len(columnas) > 3 else compra_txt
            )

            moneda = _normalize_currency_name(moneda_raw)

            try:
                compra_val = float(compra_txt.replace(",", "."))
                venta_val = float(venta_txt.replace(",", "."))
                resultados[moneda] = {"compra": compra_val, "venta": venta_val}
            except (ValueError, IndexError):
                continue

    return resultados if resultados else None


async def fetch_cadeca(
    url: str = CADECA_URL,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[Dict[str, Dict[str, float]]]:
    """Obtiene las tasas de cambio del sitio web de CADECA.

    Estrategia:
    1. GET simple -> parse tabla
    2. GET con query param ?qt-m_dulo_tasa_de_cambio=0 -> parse tabla
    3. Retornar None con logging
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(verify=False) as client:
            # Estrategia 1: GET simple
            response = await client.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            result = _parse_table(soup)
            if result:
                return result

            # Estrategia 2: GET con query param para trigger Quicktabs
            response2 = await client.get(
                f"{url}?qt-m_dulo_tasa_de_cambio=0",
                headers=headers,
                timeout=timeout,
            )
            soup2 = BeautifulSoup(response2.text, "html.parser")
            result2 = _parse_table(soup2)
            if result2:
                return result2

            return None

    except httpx.HTTPStatusError:
        return None
    except httpx.ReadTimeout:
        return None
    except httpx.RequestError:
        return None
    except Exception:
        return None
