"""Cubanomic API client for fetching USD/EUR/MLC exchange rates."""

import httpx
from typing import Dict, Any, Optional
from datetime import datetime

from src.config import get_settings


# Constants
CUBANOMIC_API_URL = "https://iframe.cubanomic.com/api/chart"
DEFAULT_DAYS = 30
CUBANOMIC_CURRENCIES = ["USD", "EUR", "MLC"]
MIN_DAYS = 7
MAX_DAYS = 730


async def fetch_cubanomic(
    days: int = DEFAULT_DAYS,
    timeout: int = 15
) -> Dict[str, Any]:
    """
    Fetch exchange rates from Cubanomic API.
    
    Args:
        days: Number of days of historical data (7-730). Defaults to 30.
        timeout: Timeout in seconds for the request. Defaults to 15.
    
    Returns:
        Standardized response dict with format:
        {
            "ok": True,
            "data": {
                "USD": {"rate": 517.26, "change": "up", "prev_rate": 516.04},
                "EUR": {"rate": 582.36, "change": "up", "prev_rate": 582.18},
                "MLC": {"rate": 394.82, "change": "up", "prev_rate": 392.78}
            },
            "history": [...],
            "updated_at": "2026-03-28T00:00:00.083Z"
        }
        Or error response:
        {
            "ok": False,
            "error": {
                "code": 500,
                "message": "Error message",
                "path": "/api/v1/tasas/cubanomic"
            }
        }
    """
    # Validate days range
    if days < MIN_DAYS or days > MAX_DAYS:
        return {
            "ok": False,
            "error": {
                "code": 400,
                "message": f"Días inválidos. Debe estar entre {MIN_DAYS} y {MAX_DAYS}",
                "path": "/api/v1/tasas/cubanomic"
            }
        }
    
    params = {"days": days}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                CUBANOMIC_API_URL,
                params=params,
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            
            parsed = _parse_cubanomic_response(data)
            if parsed is None:
                return {
                    "ok": False,
                    "error": {
                        "code": 500,
                        "message": "Error al procesar respuesta de Cubanomic",
                        "path": "/api/v1/tasas/cubanomic"
                    }
                }
            
            return parsed
            
    except httpx.HTTPStatusError as e:
        return {
            "ok": False,
            "error": {
                "code": e.response.status_code,
                "message": f"Error HTTP {e.response.status_code}: {str(e)}",
                "path": "/api/v1/tasas/cubanomic"
            }
        }
    except httpx.ReadTimeout:
        return {
            "ok": False,
            "error": {
                "code": 504,
                "message": "Timeout al conectar con Cubanomic",
                "path": "/api/v1/tasas/cubanomic"
            }
        }
    except httpx.RequestError as e:
        return {
            "ok": False,
            "error": {
                "code": 503,
                "message": f"Error de conexión: {str(e)}",
                "path": "/api/v1/tasas/cubanomic"
            }
        }
    except (KeyError, ValueError, TypeError) as e:
        return {
            "ok": False,
            "error": {
                "code": 500,
                "message": f"Error al procesar datos: {str(e)}",
                "path": "/api/v1/tasas/cubanomic"
            }
        }


def _parse_cubanomic_response(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parse nested JSON structure from Cubanomic API.
    
    Args:
        data: Raw response dict from Cubanomic API
    
    Returns:
        Parsed dict with standardized format or None if parsing fails
    
    Expected Cubanomic structure:
    {
        "data": {
            "datasets": [
                {
                    "label": "USD",
                    "data": [
                        {"x": "2026-03-27", "y": 516.04},
                        {"x": "2026-03-28", "y": 517.26}
                    ]
                },
                {
                    "label": "EUR",
                    "data": [...]
                },
                {
                    "label": "MLC",
                    "data": [...]
                }
            ]
        },
        "updated_at": "2026-03-28T00:00:00.083Z"
    }
    """
    try:
        # Extract datasets from nested structure
        if "data" not in data or "datasets" not in data["data"]:
            return None
        
        datasets = data["data"]["datasets"]
        if not datasets:
            return None
        
        # Build currency data
        currency_data: Dict[str, Dict[str, Any]] = {}
        history: list[Dict[str, Any]] = []
        
        for dataset in datasets:
            label = dataset.get("label")
            if label not in CUBANOMIC_CURRENCIES:
                continue
            
            points = dataset.get("data", [])
            if not points:
                continue
            
            # Sort by date to ensure correct order
            sorted_points = sorted(points, key=lambda p: p.get("x", ""))
            
            # Get current and previous rates
            current_rate = sorted_points[-1]["y"] if sorted_points else None
            prev_rate = sorted_points[-2]["y"] if len(sorted_points) > 1 else current_rate
            
            if current_rate is None:
                continue
            
            # Calculate change indicator
            change = _calculate_change(current_rate, prev_rate)
            
            currency_data[label] = {
                "rate": current_rate,
                "change": change,
                "prev_rate": prev_rate if prev_rate else current_rate
            }
            
            # Add to history
            for point in sorted_points:
                history.append({
                    "date": point.get("x"),
                    "currency": label,
                    "rate": point.get("y")
                })
        
        if not currency_data:
            return None
        
        # Get updated_at or use current time
        updated_at = data.get("updated_at", datetime.utcnow().isoformat() + "Z")
        
        return {
            "ok": True,
            "data": currency_data,
            "history": history,
            "updated_at": updated_at
        }
        
    except (KeyError, IndexError, TypeError):
        return None


def _calculate_change(current: float, previous: Optional[float]) -> str:
    """
    Calculate change indicator between two rates.
    
    Args:
        current: Current rate
        previous: Previous rate
    
    Returns:
        "up" if current > previous, "down" if current < previous, "neutral" otherwise
    """
    if previous is None:
        return "neutral"
    
    if current > previous:
        return "up"
    elif current < previous:
        return "down"
    else:
        return "neutral"
