"""CADECA web scraper for fetching exchange rates from official website."""

import httpx
from html.parser import HTMLParser
from typing import Optional, Dict, Any, List


CADECA_URL = "https://www.cadeca.cu"
DEFAULT_TIMEOUT = 8.0


class CadecaTableParser(HTMLParser):
    """HTML parser for CADECA exchange rate table."""
    
    def __init__(self):
        super().__init__()
        self.result: Dict[str, Dict[str, float]] = {}
        self.current_row: List[str] = []
        self.in_row = False
        self.current_data = ""
    
    def handle_starttag(self, tag: str, attrs: List[tuple]):
        if tag == "tr":
            self.in_row = True
            self.current_row = []
        elif tag == "td":
            self.current_data = ""
    
    def handle_endtag(self, tag: str):
        if tag == "tr":
            self.in_row = False
            if len(self.current_row) >= 3:
                try:
                    currency = self.current_row[0].strip()
                    compra_text = self.current_row[1].strip()
                    venta_text = self.current_row[2].strip()
                    
                    compra = float(compra_text.replace(",", ""))
                    venta = float(venta_text.replace(",", ""))
                    
                    if currency and compra > 0 and venta > 0:
                        self.result[currency] = {
                            "compra": compra,
                            "venta": venta
                        }
                except (ValueError, IndexError):
                    pass
        elif tag == "td":
            self.current_row.append(self.current_data.strip())
    
    def handle_data(self, data: str):
        self.current_data += data


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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            html = response.text
            parser = CadecaTableParser()
            parser.feed(html)
            
            return parser.result
            
    except httpx.HTTPStatusError:
        return None
    except httpx.ReadTimeout:
        return None
    except httpx.RequestError:
        return None
    except Exception:
        return None
