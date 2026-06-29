"""Generador de imagen de tasas de ElToque con Pillow.

Genera una imagen PNG con las tasas del mercado informal cubano,
usando los datos de tasas.eltoque.com/v1/trmi (ya autenticados en taso-api).

Diseño inspirado en el estilo visual de iframe.cubanomic.com:
- Fondo oscuro azul marino
- Tasas principales destacadas (USD, EUR, MLC)
- Fecha y fuente en el footer
- Sin navegador, sin JS, sin Selenium/Playwright
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

CUBA_TZ = ZoneInfo("America/Havana")

# Paleta de colores (estilo ElToque)
COLOR_BG = (14, 24, 48)           # azul marino oscuro
COLOR_HEADER_BG = (10, 18, 38)    # más oscuro para header
COLOR_ACCENT = (30, 180, 100)      # verde ElToque
COLOR_WHITE = (255, 255, 255)
COLOR_GRAY = (160, 170, 195)
COLOR_YELLOW = (255, 210, 80)      # destacar valor
COLOR_RED = (220, 80, 80)
COLOR_UP = (60, 200, 120)
COLOR_DOWN = (220, 80, 80)
COLOR_DIVIDER = (40, 55, 90)
COLOR_CARD_BG = (20, 35, 70)

# Monedas a mostrar (en orden)
CURRENCY_ORDER = ["USD", "EUR", "MLC", "ECU", "CAD", "GBP", "CHF"]
CURRENCY_FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "MLC": "💳",
    "ECU": "🇪🇺", "CAD": "🇨🇦", "GBP": "🇬🇧", "CHF": "🇨🇭",
}
CURRENCY_NAMES = {
    "USD": "Dólar", "EUR": "Euro", "MLC": "MLC",
    "ECU": "Euro", "CAD": "Dólar CAD", "GBP": "Libra", "CHF": "Franco",
}


def generate_toque_image(
    rates_data: dict[str, Any],
    width: int = 800,
) -> Optional[bytes]:
    """Genera imagen PNG con las tasas de ElToque.

    Args:
        rates_data: Dict con tasas {currency: rate} de tasas.eltoque.com/v1/trmi
                    Puede ser el dict crudo {"tasas": {...}} o ya normalizado {"USD": 365.0}
        width: Ancho de la imagen en píxeles

    Returns:
        Bytes del PNG generado, o None si falla.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error("❌ Pillow no instalado. Ejecutar: pip install Pillow")
        return None

    try:
        # Normalizar datos de entrada
        if "tasas" in rates_data:
            tasas = rates_data["tasas"]
        else:
            tasas = rates_data

        # Filtrar solo las monedas que tenemos datos
        items = []
        for cur in CURRENCY_ORDER:
            rate = tasas.get(cur)
            if rate is not None:
                items.append((cur, float(rate)))

        if not items:
            logger.error("❌ Sin tasas para generar imagen")
            return None

        # Layout
        PADDING = 32
        HEADER_H = 110
        ROW_H = 72
        FOOTER_H = 56
        total_h = HEADER_H + (ROW_H * len(items)) + FOOTER_H + PADDING

        img = Image.new("RGB", (width, total_h), COLOR_BG)
        draw = ImageDraw.Draw(img)

        # ── Cargar fuentes ────────────────────────────────────────────────────
        fonts = _load_fonts()

        # ── Header ───────────────────────────────────────────────────────────
        _draw_header(draw, img, width, HEADER_H, fonts)

        # ── Filas de tasas ────────────────────────────────────────────────────
        y = HEADER_H
        for i, (cur, rate) in enumerate(items):
            _draw_rate_row(draw, width, y, ROW_H, cur, rate, i, fonts, PADDING)
            y += ROW_H

        # ── Footer ────────────────────────────────────────────────────────────
        _draw_footer(draw, width, y, FOOTER_H, fonts)

        # Serializar a bytes
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        result = buf.read()
        logger.info("✅ Imagen generada: %dx%d px, %d bytes", width, total_h, len(result))
        return result

    except Exception as e:
        logger.error("❌ Error generando imagen: %s", e, exc_info=True)
        return None


def _load_fonts() -> dict:
    """Carga fuentes del sistema. Fallback a default si no están disponibles."""
    try:
        from PIL import ImageFont
        # Intentar fuentes del sistema Linux (VPS Debian)
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        font_paths_regular = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        ]

        def load_best(paths, size):
            for p in paths:
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
            return ImageFont.load_default()

        return {
            "title": load_best(font_paths, 28),
            "subtitle": load_best(font_paths_regular, 15),
            "currency": load_best(font_paths, 22),
            "rate_big": load_best(font_paths, 36),
            "rate_small": load_best(font_paths_regular, 18),
            "footer": load_best(font_paths_regular, 13),
            "label": load_best(font_paths_regular, 14),
        }
    except Exception:
        from PIL import ImageFont
        default = ImageFont.load_default()
        return {k: default for k in ("title", "subtitle", "currency", "rate_big", "rate_small", "footer", "label")}


def _draw_header(draw, img, width: int, header_h: int, fonts: dict) -> None:
    """Dibuja el header con título y fecha."""
    from PIL import Image, ImageDraw

    # Barra de acento verde en la parte superior
    draw.rectangle([0, 0, width, 5], fill=COLOR_ACCENT)

    # Fondo del header ligeramente más oscuro
    draw.rectangle([0, 5, width, header_h], fill=COLOR_HEADER_BG)

    # Título
    now_cuba = datetime.now(CUBA_TZ)
    fecha = now_cuba.strftime("%-d de %B de %Y").capitalize()

    title = "TASA DEL MERCADO INFORMAL"
    draw.text((32, 22), title, font=fonts["title"], fill=COLOR_WHITE)

    subtitle = f"Datos de elToque · {fecha}"
    draw.text((32, 60), subtitle, font=fonts["subtitle"], fill=COLOR_GRAY)

    # Logo/marca derecha
    draw.text((width - 150, 22), "elTOQUE", font=fonts["title"], fill=COLOR_ACCENT)
    draw.text((width - 150, 58), "eltoque.com", font=fonts["label"], fill=COLOR_GRAY)

    # Línea separadora
    draw.rectangle([0, header_h - 1, width, header_h], fill=COLOR_DIVIDER)


def _draw_rate_row(
    draw, width: int, y: int, row_h: int,
    currency: str, rate: float,
    index: int, fonts: dict, padding: int,
) -> None:
    """Dibuja una fila de tasa."""
    # Fondo alternado
    bg = COLOR_CARD_BG if index % 2 == 0 else COLOR_BG
    draw.rectangle([0, y, width, y + row_h], fill=bg)

    # Línea inferior fina
    draw.rectangle([padding, y + row_h - 1, width - padding, y + row_h], fill=COLOR_DIVIDER)

    center_y = y + row_h // 2

    # Nombre de la moneda
    name = CURRENCY_NAMES.get(currency, currency)
    flag = CURRENCY_FLAGS.get(currency, "")
    label = f"{flag}  {currency}" if flag else currency
    draw.text((padding, center_y - 22), label, font=fonts["currency"], fill=COLOR_WHITE)
    draw.text((padding, center_y + 4), name, font=fonts["label"], fill=COLOR_GRAY)

    # Tasa (derecha)
    rate_str = f"{rate:,.0f}"
    unit_str = "CUP"

    # Calcular posición desde la derecha
    try:
        rate_bbox = draw.textbbox((0, 0), rate_str, font=fonts["rate_big"])
        rate_w = rate_bbox[2] - rate_bbox[0]
    except Exception:
        rate_w = len(rate_str) * 22

    rate_x = width - padding - rate_w
    draw.text((rate_x, center_y - 22), rate_str, font=fonts["rate_big"], fill=COLOR_YELLOW)
    draw.text((rate_x, center_y + 16), unit_str, font=fonts["label"], fill=COLOR_GRAY)


def _draw_footer(draw, width: int, y: int, footer_h: int, fonts: dict) -> None:
    """Dibuja el footer con fuente y timestamp."""
    draw.rectangle([0, y, width, y + footer_h], fill=COLOR_HEADER_BG)
    draw.rectangle([0, y, width, y + 1], fill=COLOR_DIVIDER)
    draw.rectangle([0, y, 5, y + footer_h], fill=COLOR_ACCENT)

    now_utc = datetime.now(timezone.utc)
    now_cuba = now_utc.astimezone(CUBA_TZ)
    ts = now_cuba.strftime("%d/%m/%Y %H:%M") + " (Cuba)"

    draw.text(
        (20, y + footer_h // 2 - 8),
        f"Fuente: tasas.eltoque.com  ·  Generado: {ts}",
        font=fonts["footer"],
        fill=COLOR_GRAY,
    )
