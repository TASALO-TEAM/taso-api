"""BCC web scraper for fetching official exchange rates from Banco Central de Cuba."""

import httpx
import json
import html
import urllib3
from bs4 import BeautifulSoup
from typing import Optional, Dict, List

# Deshabilitar advertencias de certificados SSL (común en sitios .cu)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BCC_URL = "https://www.bc.gob.cu"
DEFAULT_TIMEOUT = 5.0


async def fetch_bcc(
    url: str = BCC_URL,
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[Dict[str, float]]:
    """
    Obtiene las tasas de cambio oficiales del Banco Central de Cuba.
    Maneja la estructura serializada de Astro/Qwik.
    
    Args:
        url: URL del sitio del BCC
        timeout: Timeout en segundos

    Returns:
        Dict con moneda -> tasa o None si hay error
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(url, headers=headers, timeout=timeout)
            
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Buscar todos los componentes astro-island
            islands = soup.find_all('astro-island')
            data = None
            
            for island in islands:
                props_raw = island.get('props')
                if not props_raw:
                    continue
                    
                props_json = html.unescape(props_raw)
                try:
                    temp_data = json.loads(props_json)
                    # Verificamos que contenga 'tasas' y que NO sea solo un link en noticias
                    if 'tasas' in temp_data and isinstance(temp_data['tasas'], list):
                        data = temp_data
                        break  # Encontramos el correcto
                except Exception:
                    continue
            
            if not data:
                return None
        
            # 2. Navegar la estructura de serialización de Astro
            # Estructura observada: 
            # data['tasas'] -> [1, [ARRAY_DE_MONEDAS]]
            # ARRAY_DE_MONEDAS item -> [0, {DICCIONARIO_DE_ATRIBUTOS}]
            # ATRIBUTO -> [0, valor]
            
            if 'tasas' not in data or len(data['tasas']) < 2:
                return None

            lista_monedas = data['tasas'][1]
            
            tasas_finales = {}
            
            for item_wrapper in lista_monedas:
                # item_wrapper suele ser [0, {datos}]
                if len(item_wrapper) < 2:
                    continue
                    
                info = item_wrapper[1]
                
                # Extraer código de moneda (ej: USD) y tasa (ej: 410)
                # La estructura interna es "campo": [tipo, valor]
                
                # Obtener Código
                codigo_obj = info.get('codigoMoneda')
                if not codigo_obj or len(codigo_obj) < 2:
                    continue
                codigo = codigo_obj[1]
                
                # Obtener Tasa (Usamos 'tasaEspecial' que coincide con el 410.00 del ejemplo)
                tasa_obj = info.get('tasaEspecial')
                if not tasa_obj or len(tasa_obj) < 2:
                    continue
                valor = float(tasa_obj[1])
                
                # Filtramos solo las principales para no llenar el mensaje
                monedas_interes = ['USD', 'EUR', 'MLC', 'CAD', 'GBP', 'MXN', 'CHF', 'RUB', 'JPY', 'AUD']
                
                if codigo in monedas_interes:
                    tasas_finales[codigo] = valor

            return tasas_finales

    except httpx.HTTPStatusError:
        return None
    except httpx.ReadTimeout:
        return None
    except httpx.RequestError:
        return None
    except Exception:
        return None
