"""TASALO API - Aplicación principal FastAPI."""

import asyncio
import logging
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.config import get_settings
from src import database
from src.database import get_engine
from src.routers import rates as rates_router
from src.routers import admin as admin_router
from src.routers import stats as stats_router
from src.routers import images as images_router
from src.services.scheduler import create_scheduler, init_scheduler_status, init_cubanomic_scheduler, init_image_capture_scheduler, init_year_scheduler
from src.routers import year as year_router
from src.routers import alerts as alerts_router
from src.routers import ads as ads_router
from src.routers import tickets as tickets_router
from src.logging_config import setup_logging

settings = get_settings()

# Configurar logging estructurado (consola + archivo rotado con archivado por
# fecha, ver src/logging_config.py). No crea archivos cuando corre bajo pytest.
setup_logging(level=logging.INFO)

logger = logging.getLogger(__name__)

API_VERSION = "1.5.0"


def _get_git_build_info() -> dict[str, str]:
    """Lee commit corto + fecha del último commit una sola vez al arrancar.

    Usado por /health y por /status (taso-bot) para mostrar qué versión
    está corriendo en el VPS sin depender de recordar hacer un bump
    manual. Fallback a "unknown" si no hay .git (ej. tarball) o falla git.
    """
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3, check=True,
        ).stdout.strip()
        commit_date = subprocess.run(
            ["git", "log", "-1", "--format=%cd", "--date=short"],
            capture_output=True, text=True, timeout=3, check=True,
        ).stdout.strip()
        return {"commit": commit or "unknown", "commit_date": commit_date or "unknown"}
    except Exception as e:
        logger.warning("⚠️ No se pudo leer info de git (%s) — usando 'unknown'", e)
        return {"commit": "unknown", "commit_date": "unknown"}


_GIT_BUILD_INFO = _get_git_build_info()


# Clientes conocidos por substring de User-Agent, para inferir client_id
# cuando la request no manda el header X-Client-Id explícito. taso-bot ya
# manda su propio UA ("taso-bot/x.y.z") — ver api_client.py.
_UA_CLIENT_HINTS: dict[str, str] = {
    "taso-bot": "bot",
    "taso-app": "app",
    "taso-ext": "ext",
    "taso-extmf": "extmf",
}


def _guess_client(user_agent: str) -> str:
    """Infiere client_id desde el User-Agent cuando no viene X-Client-Id."""
    ua_lower = (user_agent or "").lower()
    for hint, client_id in _UA_CLIENT_HINTS.items():
        if hint in ua_lower:
            return client_id
    return "unknown"


# Paths excluidos del tracking de api_request_log (ruido, no aportan a las
# estadísticas de uso público — ver docs/plans/2026-07-08-status-command-v2.md)
_TRACKING_EXCLUDED_PATHS = {"/api/v1/health", "/docs", "/openapi.json", "/redoc"}
_TRACKING_EXCLUDED_PREFIXES = ("/api/v1/admin/stats",)


async def _log_request(method: str, path: str, status_code: int, duration_ms: int, client_id: str) -> None:
    """Persiste una entrada de api_request_log. Fire-and-forget desde el middleware."""
    from src.services import stats_service

    try:
        async with database.async_session_factory() as session:
            await stats_service.log_api_request(
                session, method=method, path=path,
                status_code=status_code, duration_ms=duration_ms, client_id=client_id,
            )
    except Exception as e:
        logger.debug("⚠️ No se pudo registrar api_request_log para %s %s: %s", method, path, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle de FastAPI:
    - Startup: Iniciar scheduler y DB
    - Shutdown: Detener scheduler graceful y DB
    """
    # Startup
    logger.info("🚀 [Startup] Iniciando TASALO-API...")

    # Iniciar DB primero (necesaria para init_scheduler_status)
    # get_engine() ya inicializa el global async_session_factory en el módulo database
    app.state.engine = get_engine(settings.database_url, echo=False)
    app.state.db = database.async_session_factory

    # Verificar conexión a la base de datos
    try:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        app.state.db_connected = True
        logger.info("✅ [Startup] Base de datos conectada")
    except Exception as e:
        app.state.db_connected = False
        logger.error(f"❌ [Startup] Error conectando a la base de datos: {e}")

    # Inicializar estado del scheduler en DB (requiere DB inicializada)
    # Usar database.async_session_factory que fue inicializado por get_engine()
    await init_scheduler_status(database.async_session_factory)

    # Iniciar scheduler
    scheduler = create_scheduler(database.async_session_factory)
    
    # Inicializar job de Cubanomic
    await init_cubanomic_scheduler(scheduler, database.async_session_factory)

    # Captura diaria de imagen ElToque (7:05 Cuba) — no-fatal si falla,
    # el endpoint on-demand de /toqueimg sigue funcionando igual
    try:
        await init_image_capture_scheduler(scheduler, database.async_session_factory)
        logger.info("✅ [Startup] ElToque image capture scheduler initialized")
    except Exception as e:
        logger.warning("⚠️ ElToque image capture scheduler init failed: %s", e)

    # Year daily alert scheduler
    try:
        await init_year_scheduler(scheduler, database.async_session_factory)
        logger.info("✅ [Startup] Year daily alert scheduler initialized")
    except ImportError:
        logger.warning("⚠️ Year scheduler not yet available — taso-api changes pending")
    except Exception as e:
        logger.warning("⚠️ Year scheduler init failed: %s", e)

    # Seed year quotes from JSON if table is empty
    from src.services import year_service
    try:
        async with app.state.db() as _seed_db:
            _seed_result = await year_service.seed_quotes_if_empty(_seed_db)
            logger.info("🌱 Year quotes seed: %s", _seed_result)
            _migrate_result = await year_service.migrate_legacy_subs(_seed_db)
            logger.info("📋 Legacy subs migrated: %s", _migrate_result)
    except Exception as _e:
        logger.warning("⚠️ Year DB init failed (non-fatal): %s", _e)

    scheduler.start()
    logger.info(f"⏰ [Startup] Scheduler iniciado (intervalo: {settings.refresh_interval_minutes} min)")

    app.state.scheduler = scheduler

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
    version=API_VERSION,
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


@app.middleware("http")
async def track_requests(request: Request, call_next):
    """Registra toda request HTTP en api_request_log (fire-and-forget).

    Da visibilidad real sobre el uso de la API pública más allá de lo
    que taso-bot reporta manualmente — incluye taso-app, taso-ext,
    taso-extmf y cualquier otro consumidor. Ver
    docs/plans/2026-07-08-status-command-v2.md (Fase 1).
    """
    start = time.time()
    response = await call_next(request)
    duration_ms = int((time.time() - start) * 1000)

    path = request.url.path
    if path not in _TRACKING_EXCLUDED_PATHS and not path.startswith(_TRACKING_EXCLUDED_PREFIXES):
        client_id = request.headers.get("X-Client-Id") or _guess_client(request.headers.get("user-agent", ""))
        asyncio.create_task(
            _log_request(request.method, path, response.status_code, duration_ms, client_id)
        )

    return response

# Registrar routers
app.include_router(rates_router.router, prefix="/api/v1/tasas", tags=["Tasas"])
app.include_router(admin_router.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(stats_router.router, prefix="/api/v1/admin/stats", tags=["Admin Stats"])
app.include_router(images_router.router, tags=["Images"])
app.include_router(year_router.router, prefix="/api/v1/year", tags=["Year"])
app.include_router(year_router.admin_router, prefix="/api/v1/year", tags=["Year Admin"])
app.include_router(alerts_router.router, tags=["Price Alerts"])
app.include_router(ads_router.router, prefix="/api/v1/ads", tags=["Ads"])
app.include_router(ads_router.admin_router, prefix="/api/v1/ads", tags=["Ads Admin"])
app.include_router(tickets_router.router, prefix="/api/v1/tickets", tags=["Tickets"])


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """
    Verificar estado de la aplicación y conexión a la base de datos.

    Returns:
        dict: Estado de la aplicación con versión y estado de la DB.
    """
    return {
        "ok": True,
        "version": API_VERSION,
        "git_commit": _GIT_BUILD_INFO["commit"],
        "git_commit_date": _GIT_BUILD_INFO["commit_date"],
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
