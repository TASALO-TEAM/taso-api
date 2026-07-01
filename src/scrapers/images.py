"""Scraper de la imagen del post de iframe.cubanomic.com.

Enfoque (2026-06-30): en vez de hacer screenshot de un elemento del DOM
(#imgtasa, frágil por timing de render de la SPA Vue), se intercepta el
evento de descarga que dispara el botón "Guardar POST". Ese botón genera
la imagen real del post (vía canvas -> Blob) y el navegador emite un
evento de descarga que Playwright puede capturar directamente con
page.expect_download(), sin importar si es un <a download> o un Blob
generado por JS.

Ejecución: solo bajo petición (nunca en loop), resultado sobrescribe
siempre el mismo archivo canónico en disco.
"""

import os
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

TARGET_URL = "https://iframe.cubanomic.com/"
BUTTON_TEXT = "Guardar POST"

# Timeout esperando que el botón esté visible (ms)
BUTTON_WAIT_MS = 15000
# Timeout esperando que se dispare el evento de descarga tras el clic (ms)
DOWNLOAD_WAIT_MS = 20000


async def download_eltoque_post_image(
    output_path: str,
    timeout: int = 30000,
) -> Dict:
    """Descarga la imagen real del post haciendo clic en 'Guardar POST'.

    Intercepta el evento de descarga del navegador con page.expect_download(),
    que funciona tanto si el botón genera un <a download> como si dispara un
    Blob (típico de apps que generan la imagen final vía canvas.toBlob()).

    Args:
        output_path: Path absoluto donde guardar la imagen (se sobrescribe
            si ya existe).
        timeout: Timeout total en milisegundos para navegación + descarga.

    Returns:
        dict con success, file_size, error
    """
    try:
        from playwright.async_api import async_playwright, Error as PlaywrightError
    except ImportError:
        return {"success": False, "error": "Playwright no instalado"}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            try:
                page = await browser.new_page(
                    viewport={"width": 1280, "height": 900},
                    accept_downloads=True,
                )

                logger.debug("🌐 [download] Navegando a %s", TARGET_URL)
                await page.goto(TARGET_URL, wait_until="networkidle", timeout=timeout)

                button = page.get_by_role("button", name=BUTTON_TEXT)
                try:
                    await button.wait_for(state="visible", timeout=BUTTON_WAIT_MS)
                except PlaywrightError:
                    return {
                        "success": False,
                        "error": f"Botón '{BUTTON_TEXT}' no visible tras {BUTTON_WAIT_MS}ms",
                    }

                logger.debug("🖱️ [download] Click en '%s', esperando descarga...", BUTTON_TEXT)
                try:
                    async with page.expect_download(timeout=DOWNLOAD_WAIT_MS) as download_info:
                        await button.click()
                    download = await download_info.value
                except PlaywrightError as e:
                    return {
                        "success": False,
                        "error": f"No se disparó descarga tras el clic: {e}",
                    }

                await download.save_as(output_path)
                file_size = os.path.getsize(output_path)

                logger.info(
                    "✅ [download] Imagen descargada: %s (%d bytes)",
                    output_path, file_size,
                )
                return {"success": True, "file_size": file_size}

            finally:
                await browser.close()

    except PlaywrightError as e:
        return {"success": False, "error": f"Playwright error: {e}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def ensure_directory_exists(output_path: str) -> None:
    """Asegura que el directorio padre existe."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
