"""API routers for taso-api."""

from src.routers.rates import router as rates_router
from src.routers.admin import router as admin_router

__all__ = ["rates_router", "admin_router"]
