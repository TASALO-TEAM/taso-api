"""BCC web scraper for fetching official exchange rates from Banco Central de Cuba."""

import httpx
from html.parser import HTMLParser
from typing import Optional, Dict, List


BCC_URL = "https://www.bc.gob.cu"
DEFAULT_TIMEOUT = 10.0


class BCCTableParser(HTMLParser):
    """HTML parser for BCC exchange rate table."""

    def __init__(self):
        super().__init__()
        self.result: Dict[str, float] = {}
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
            if len(self.current_row) >= 2:
                try:
                    currency = self.current_row[0].strip()
                    rate_text = self.current_row[1].strip()
                    rate = float(rate_text.replace(",", ""))

                    if currency and rate > 0:
                        self.result[currency] = rate
                except (ValueError, IndexError):
                    pass
        elif tag == "td":
            self.current_row.append(self.current_data.strip())

    def handle_data(self, data: str):
        self.current_data += data


async def fetch_bcc(
    url: str = BCC_URL,
    timeout: float = DEFAULT_TIMEOUT
) -> Optional[Dict[str, float]]:
    """
    Obtiene las tasas de cambio oficiales del Banco Central de Cuba.
    
    Args:
        url: URL del sitio del BCC
        timeout: Timeout en segundos
        
    Returns:
        Dict con moneda -> tasa o None si hay error
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            html = response.text
            parser = BCCTableParser()
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
