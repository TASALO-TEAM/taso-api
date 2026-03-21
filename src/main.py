"""TASALO API - Aplicación principal FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.config import get_settings
from src.database import get_engine, get_session_maker
from src.services.scheduler import create_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle de FastAPI:
    - Startup: Iniciar scheduler y DB
    - Shutdown: Detener scheduler graceful y DB
    """
    # Startup
    print("🚀 [Startup] Iniciando TASALO-API...")

    # Iniciar scheduler
    scheduler = create_scheduler()
    scheduler.start()
    print(f"⏰ [Startup] Scheduler iniciado (intervalo: {settings.refresh_interval_minutes} min)")

    app.state.scheduler = scheduler

    # Iniciar DB
    app.state.engine = get_engine(settings.database_url, echo=False)
    app.state.db = get_session_maker(app.state.engine)

    # Verificar conexión a la base de datos
    try:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        app.state.db_connected = True
    except Exception:
        app.state.db_connected = False

    yield

    # Shutdown
    print("🛑 [Shutdown] Deteniendo scheduler...")
    scheduler.shutdown(wait=False)
    print("✅ [Shutdown] Scheduler detenido")

    await app.state.engine.dispose()


app = FastAPI(
    title="TASALO API",
    description="API para tasas de cambio en Cuba. Agrega datos de ElToque, CADECA, BCC y Binance.",
    version="1.2.0",
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


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """
    Verificar estado de la aplicación y conexión a la base de datos.

    Returns:
        dict: Estado de la aplicación con versión y estado de la DB.
    """
    return {
        "ok": True,
        "version": "1.2.0",
        "db": "connected" if app.state.db_connected else "disconnected",
        "database_url": settings.database_url.split("://")[0],  # Solo el tipo
    }
