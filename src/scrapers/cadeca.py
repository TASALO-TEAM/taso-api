"""CADECA web scraper for fetching exchange rates from official website."""

import httpx
import urllib3
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

# Desactivar warnings de SSL inseguro (común en sitios .cu)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CADECA_URL = "https://www.cadeca.cu"
DEFAULT_TIMEOUT = 7.0


async def fetch_cadeca(
    url: str = CADECA_URL,
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[Dict[str, Dict[str, float]]]:
    """
    Obtiene las tasas de cambio del sitio web de CADECA.
    
    Args:
        url: URL del sitio de CADECA
        timeout: Timeout en segundos

    Returns:
        Dict con moneda -> {compra, venta} o None si hay error
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            contenedor_casas = soup.find('div', id='quicktabs-tabpage-m_dulo_tasa_de_cambio-0')

            if not contenedor_casas:
                return None

            tabla = contenedor_casas.find('table')
            if not tabla:
                return None

            resultados = {}
            filas = tabla.find('tbody').find_all('tr')

            for fila in filas:
                columnas = fila.find_all('td')
                if len(columnas) >= 4:
                    moneda = columnas[1].get_text(strip=True)
                    compra_txt = columnas[2].get_text(strip=True)
                    venta_txt = columnas[3].get_text(strip=True)

                    try:
                        compra_val = float(compra_txt)
                        venta_val = float(venta_txt)
                        resultados[moneda] = {'compra': compra_val, 'venta': venta_val}
                    except ValueError:
                        continue
            
            return resultados if resultados else None

    except httpx.HTTPStatusError:
        return None
    except httpx.ReadTimeout:
        return None
    except httpx.RequestError:
        return None
    except Exception:
        return None
