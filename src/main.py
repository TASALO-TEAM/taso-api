"""TASALO API - Aplicación principal FastAPI."""

import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.config import get_settings
from src.database import get_engine, get_session_maker
from src.routers import rates as rates_router
from src.routers import admin as admin_router
from src.services.scheduler import create_scheduler

settings = get_settings()

# Configurar logging estructurado
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle de FastAPI:
    - Startup: Iniciar scheduler y DB
    - Shutdown: Detener scheduler graceful y DB
    """
    # Startup
    logger.info("🚀 [Startup] Iniciando TASALO-API...")

    # Iniciar scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info(f"⏰ [Startup] Scheduler iniciado (intervalo: {settings.refresh_interval_minutes} min)")

    app.state.scheduler = scheduler

    # Iniciar DB
    app.state.engine = get_engine(settings.database_url, echo=False)
    app.state.db = get_session_maker(app.state.engine)

    # Verificar conexión a la base de datos
    try:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        app.state.db_connected = True
        logger.info("✅ [Startup] Base de datos conectada")
    except Exception as e:
        app.state.db_connected = False
        logger.error(f"❌ [Startup] Error conectando a la base de datos: {e}")

    yield

    # Shutdown
    logger.info("🛑 [Shutdown] Deteniendo scheduler...")
    scheduler.shutdown(wait=False)
    logger.info("✅ [Shutdown] Scheduler detenido")

    await app.state.engine.dispose()
    logger.info("✅ [Shutdown] Base de datos desconectada")


app = FastAPI(
    title="TASALO API",
    description="API para tasas de cambio en Cuba. Agrega datos de ElToque, CADECA, BCC y Binance.",
    version="1.5.0",
    lifespan=lifespan,
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(rates_router.router, prefix="/api/v1/tasas", tags=["Tasas"])
app.include_router(admin_router.router, prefix="/api/v1/admin", tags=["Admin"])


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """
    Verificar estado de la aplicación y conexión a la base de datos.

    Returns:
        dict: Estado de la aplicación con versión y estado de la DB.
    """
    return {
        "ok": True,
        "version": "1.5.0",
        "db": "connected" if app.state.db_connected else "disconnected",
        "database_url": settings.database_url.split("://")[0],  # Solo el tipo
    }


# =============================================================================
# Exception Handlers Globales
# =============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Manejar excepciones HTTP de FastAPI (4xx, 5xx).

    Logs el error y retorna una respuesta JSON consistente.
    """
    logger.warning(
        f"HTTP {exc.status_code} | {request.method} {request.url.path} | {exc.detail}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "path": request.url.path,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Manejar errores de validación de requests (422).

    Logs los detalles de validación y retorna errores legibles.
    """
    errors = exc.errors()
    logger.warning(
        f"Validation Error | {request.method} {request.url.path} | {len(errors)} errores"
    )

    # Formatear errores para respuesta más legible
    formatted_errors = []
    for error in errors:
        formatted_errors.append(
            {
                "field": ".".join(str(x) for x in error.get("loc", [])),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            }
        )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "ok": False,
            "error": {
                "code": 422,
                "message": "Error de validación",
                "details": formatted_errors,
            },
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Manejar excepciones no controladas (500 Internal Server Error).

    Logs el error completo para debugging y retorna respuesta genérica al cliente.
    """
    logger.error(
        f"Internal Error | {request.method} {request.url.path} | {type(exc).__name__}: {exc}",
        exc_info=True,  # Incluye stack trace en el log
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "ok": False,
            "error": {
                "code": 500,
                "message": "Error interno del servidor",
                "path": request.url.path,
            },
        },
    )
