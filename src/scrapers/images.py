"""Image scraper for capturing screenshots from web pages using Playwright."""

import os
from pathlib import Path
from typing import Dict
from playwright.async_api import async_playwright


async def capture_eltoque_image(
    output_path: str,
    timeout: int = 30000
) -> Dict:
    """
    Captura screenshot de la imagen #imgtasa en iframe.cubanomic.com.
    
    Args:
        output_path: Path donde guardar la imagen
        timeout: Timeout en milisegundos
    
    Returns:
        dict: {success: bool, width: int, height: int, file_size: int, error: Optional[str]}
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            # Navegar a la página
            await page.goto(
                "https://iframe.cubanomic.com/",
                wait_until="networkidle",
                timeout=timeout
            )
            
            # Esperar que la imagen esté visible
            await page.wait_for_selector("#imgtasa", state="visible", timeout=5000)
            
            # Capturar solo la imagen
            img_element = await page.query_selector("#imgtasa")
            if not img_element:
                return {
                    "success": False,
                    "error": "Image element #imgtasa not found"
                }
            
            # Tomar screenshot
            await img_element.screenshot(path=output_path)
            
            # Obtener metadata
            box = await img_element.bounding_box()
            file_size = os.path.getsize(output_path)
            
            await browser.close()
            
            return {
                "success": True,
                "width": int(box["width"]),
                "height": int(box["height"]),
                "file_size": file_size
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def ensure_directory_exists(output_path: str) -> None:
    """Asegura que el directorio padre existe."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
