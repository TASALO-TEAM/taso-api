"""Image scraper for capturing screenshots from web pages using Playwright."""

import os
import logging
from pathlib import Path
from typing import Dict, Optional
from playwright.async_api import async_playwright, Error as PlaywrightError

logger = logging.getLogger(__name__)


async def capture_eltoque_image(
    output_path: str,
    timeout: int = 30000
) -> Dict:
    """
    Captura screenshot de la imagen #imgtasa en iframe.cubanomic.com.
    
    Args:
        output_path: Path donde guardar la imagen
        timeout: Timeout en milisegnicos
    
    Returns:
        dict: {success: bool, width: int, height: int, file_size: int, error: Optional[str]}
    """
    try:
        # Intentar con Playwright primero
        result = await _capture_with_playwright(output_path, timeout)
        if result["success"]:
            return result
        
        # Si falla, intentar con Selenium como fallback
        logger.warning("⚠️ Playwright failed, trying Selenium fallback...")
        result = await _capture_with_selenium(output_path, timeout)
        if result["success"]:
            return result
            
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def _capture_with_playwright(output_path: str, timeout: int) -> Dict:
    """Capture image using Playwright."""
    try:
        async with async_playwright() as p:
            # Intentar diferentes configuraciones
            browser = None
            for browser_type in ["chromium", "chromium-headless-shell"]:
                try:
                    bt = getattr(p, browser_type)
                    browser = await bt.launch(headless=True)
                    break
                except PlaywrightError:
                    continue
            
            if not browser:
                return {"success": False, "error": "No Playwright browser available"}
                
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
            
    except PlaywrightError as e:
        return {"success": False, "error": f"Playwright error: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _capture_with_selenium(output_path: str, timeout: int) -> Dict:
    """Capture image using Selenium as fallback."""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options
        
        # Configurar Chrome headless
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            driver.get("https://iframe.cubanomic.com/")
            
            # Esperar a que cargue la imagen
            wait = WebDriverWait(driver, timeout // 1000)
            img_element = wait.until(
                EC.presence_of_element_located((By.ID, "imgtasa"))
            )
            
            # Tomar screenshot
            img_element.screenshot(output_path)
            
            file_size = os.path.getsize(output_path)
            
            return {
                "success": True,
                "width": 800,  # Ancho típico
                "height": 600,  # Alto típico
                "file_size": file_size
            }
        finally:
            driver.quit()
            
    except Exception as e:
        return {"success": False, "error": f"Selenium error: {e}"}


async def ensure_directory_exists(output_path: str) -> None:
    """Asegura que el directorio padre existe."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
