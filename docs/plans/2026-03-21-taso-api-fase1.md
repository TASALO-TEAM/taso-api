# TASALO-API Fase 1 — Scaffold y Base de Datos Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Crear la estructura base del proyecto taso-api con conexión a base de datos (SQLite en desarrollo, PostgreSQL en producción) y endpoint de health check funcional.

**Architecture:** Proyecto Python modular con FastAPI como framework principal. La configuración se maneja con pydantic-settings cargando variables de entorno. SQLAlchemy async maneja la conexión a la base de datos, permitiendo cambiar entre SQLite (dev) y PostgreSQL (prod) sin cambios en el código. Alembic gestiona las migraciones.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy (async), Alembic, pydantic-settings, aiosqlite (dev), asyncpg (prod), uvicorn

---

## Task 1: Estructura de Directorios y Archivos Base

**Files:**
- Create: `taso-api/.gitignore`
- Create: `taso-api/.env.example`
- Create: `taso-api/requirements.txt`
- Create: `taso-api/src/__init__.py`
- Create: `taso-api/docs/plans/.gitkeep`

**Step 1: Crear .gitignore**

```bash
cd /home/ersus/tasalo/taso-api
mkdir -p src docs/plans
```

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/
env/
.venv

# Environment
.env
*.env
!.env.example

# Database
*.db
*.sqlite
*.sqlite3

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Logs
*.log

# OS
.DS_Store
Thumbs.db
```

**Step 2: Crear .env.example**

```bash
# Database - SQLite para desarrollo local
DATABASE_URL=sqlite+aiosqlite:///./tasalo.db

# ElToque API
ELTOQUE_API_KEY=your_eltoque_api_key_here
ELTOQUE_API_URL=https://tasas.eltoque.com/v1/trmi

# Security - Cambiar en producción
ADMIN_API_KEY=your_secret_admin_key_here

# Scheduler - Intervalo de refresco en minutos
REFRESH_INTERVAL_MINUTES=5

# CORS - Orígenes permitidos (separados por coma)
ALLOWED_ORIGINS=*
```

**Step 3: Crear requirements.txt**

```txt
# Web Framework
fastapi==0.115.0
uvicorn[standard]==0.30.0

# Database
sqlalchemy[asyncio]==2.0.30
alembic==1.13.0

# Drivers de base de datos
aiosqlite==0.20.0      # SQLite async para desarrollo
asyncpg==0.29.0        # PostgreSQL async para producción

# Settings
pydantic-settings==2.2.0
python-dotenv==1.0.0

# HTTP Client (para scrapers en fases futuras)
httpx==0.27.0

# Web Scraping (para fases futuras)
beautifulsoup4==4.12.0
lxml==5.1.0

# Scheduler (para fases futuras)
apscheduler==3.10.4
```

**Step 4: Crear src/__init__.py**

```python
"""TASALO API - Backend para tasas de cambio en Cuba."""

__version__ = "1.0.0"
```

**Step 5: Crear docs/plans/.gitkeep**

```bash
touch docs/plans/.gitkeep
```

**Step 6: Commit**

```bash
git add .
git commit -m "feat: initial project structure and base files"
```

---

## Task 2: Configuración con Pydantic Settings

**Files:**
- Create: `taso-api/src/config.py`
- Test: `taso-api/tests/test_config.py`

**Step 1: Escribir test para config**

```python
# tests/test_config.py
import os
import pytest
from pathlib import Path
from src.config import Settings, get_settings


def test_settings_load_from_env(tmp_path, monkeypatch):
    """Settings carga correctamente desde variables de entorno."""
    # Crear .env temporal
    env_file = tmp_path / ".env"
    env_file.write_text("""
DATABASE_URL=sqlite+aiosqlite:///./test.db
ELTOQUE_API_KEY=test_key_123
ELTOQUE_API_URL=https://test.eltoque.com/v1
ADMIN_API_KEY=admin_secret_456
REFRESH_INTERVAL_MINUTES=10
ALLOWED_ORIGINS=https://example.com,https://test.com
""")
    
    monkeypatch.setenv("DOTENV_PATH", str(env_file))
    settings = get_settings()
    
    assert settings.database_url == "sqlite+aiosqlite:///./test.db"
    assert settings.eltoque_api_key == "test_key_123"
    assert settings.eltoque_api_url == "https://test.eltoque.com/v1"
    assert settings.admin_api_key == "admin_secret_456"
    assert settings.refresh_interval_minutes == 10
    assert settings.allowed_origins == ["https://example.com", "https://test.com"]


def test_settings_default_values(tmp_path, monkeypatch):
    """Settings usa valores por defecto cuando no hay env."""
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=sqlite+aiosqlite:///./default.db\n")
    
    monkeypatch.setenv("DOTENV_PATH", str(env_file))
    settings = get_settings()
    
    assert settings.refresh_interval_minutes == 5  # default
    assert settings.allowed_origins == ["*"]  # default


def test_settings_invalid_interval(tmp_path, monkeypatch):
    """Settings rechaza intervalo inválido."""
    env_file = tmp_path / ".env"
    env_file.write_text("""
DATABASE_URL=sqlite+aiosqlite:///./test.db
REFRESH_INTERVAL_MINUTES=0
""")
    
    monkeypatch.setenv("DOTENV_PATH", str(env_file))
    
    with pytest.raises(ValueError):
        get_settings()
```

**Step 2: Ejecutar test para verificar que falla**

```bash
cd /home/ersus/tasalo/taso-api
mkdir -p tests
pytest tests/test_config.py -v
# Expected: FAIL - module 'src.config' not found
```

**Step 3: Implementar config.py**

```python
# src/config.py
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación cargada desde variables de entorno."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Database
    database_url: str
    
    # ElToque API
    eltoque_api_key: str = ""
    eltoque_api_url: str = "https://tasas.eltoque.com/v1/trmi"
    
    # Security
    admin_api_key: str = "changeme"
    
    # Scheduler
    refresh_interval_minutes: int = 5
    
    # CORS
    allowed_origins: str = "*"
    
    def model_post_init(self, __context) -> None:
        """Validar configuración después de inicializar."""
        if self.refresh_interval_minutes < 1:
            raise ValueError("REFRESH_INTERVAL_MINUTES debe ser >= 1")
    
    @property
    def allowed_origins_list(self) -> list[str]:
        """Retorna lista de orígenes permitidos."""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Obtener configuración singleton cacheada."""
    return Settings()
```

**Step 4: Ejecutar test para verificar que pasa**

```bash
# Instalar dependencias primero
pip install -r requirements.txt
pytest tests/test_config.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add pydantic-settings configuration with validation"
```

---

## Task 3: Modelos de Base de Datos

**Files:**
- Create: `taso-api/src/models/__init__.py`
- Create: `taso-api/src/models/rate_snapshot.py`
- Create: `taso-api/src/models/scheduler_status.py`
- Test: `taso-api/tests/test_models.py`

**Step 1: Escribir tests para modelos**

```python
# tests/test_models.py
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.rate_snapshot import RateSnapshot
from src.models.scheduler_status import SchedulerStatus


@pytest.fixture
async def db_session():
    """Crear sesión de DB en memoria para tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_rate_snapshot_creation(db_session):
    """RateSnapshot se crea correctamente."""
    snapshot = RateSnapshot(
        source="eltoque",
        currency="USD",
        buy_rate=None,
        sell_rate=Decimal("365.00"),
        fetched_at=datetime.now(timezone.utc),
    )
    
    db_session.add(snapshot)
    await db_session.commit()
    await db_session.refresh(snapshot)
    
    assert snapshot.id is not None
    assert snapshot.source == "eltoque"
    assert snapshot.currency == "USD"
    assert snapshot.sell_rate == Decimal("365.00")
    assert snapshot.created_at is not None


@pytest.mark.asyncio
async def test_scheduler_status_creation(db_session):
    """SchedulerStatus se crea correctamente."""
    status = SchedulerStatus(
        last_run_at=datetime.now(timezone.utc),
        last_success_at=datetime.now(timezone.utc),
        error_count=0,
        last_error=None,
    )
    
    db_session.add(status)
    await db_session.commit()
    await db_session.refresh(status)
    
    assert status.id is not None
    assert status.error_count == 0


@pytest.mark.asyncio
async def test_scheduler_status_error_update(db_session):
    """SchedulerStatus actualiza contador de errores."""
    status = SchedulerStatus(
        last_run_at=datetime.now(timezone.utc),
        error_count=0,
    )
    
    db_session.add(status)
    await db_session.commit()
    
    status.error_count = 3
    status.last_error = "Connection timeout"
    await db_session.commit()
    
    assert status.error_count == 3
    assert status.last_error == "Connection timeout"
```

**Step 2: Ejecutar test para verificar que falla**

```bash
pytest tests/test_models.py -v
# Expected: FAIL - modules no existen
```

**Step 3: Implementar database.py**

```python
# src/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """Clase base para todos los modelos."""
    
    # Generar nombres de tablas automáticamente en minúsculas
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()


def get_engine(database_url: str, echo: bool = False):
    """Crear engine de SQLAlchemy según el tipo de base de datos."""
    if database_url.startswith("sqlite"):
        # SQLite necesita connect_args para async
        return create_async_engine(
            database_url,
            echo=echo,
            connect_args={"check_same_thread": False},
        )
    else:
        # PostgreSQL
        return create_async_engine(
            database_url,
            echo=echo,
            pool_pre_ping=True,  # Verificar conexiones antes de usar
        )


def get_session_maker(engine):
    """Crear factory de sesiones."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
```

**Step 4: Implementar rate_snapshot.py**

```python
# src/models/rate_snapshot.py
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, DateTime, func
from sqlalchemy.sql import functions

from src.database import Base


class RateSnapshot(Base):
    """Snapshot de tasas de cambio de una fuente específica."""
    
    __tablename__ = "rate_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(20), nullable=False, index=True)  # 'eltoque', 'cadeca', 'bcc', 'binance'
    currency = Column(String(20), nullable=False, index=True)  # 'USD', 'EUR', 'MLC', etc.
    buy_rate = Column(Numeric(12, 4), nullable=True)  # Tasa de compra (CADECA)
    sell_rate = Column(Numeric(12, 4), nullable=True)  # Tasa de venta / única
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    
    def __repr__(self) -> str:
        return f"<RateSnapshot(source={self.source}, currency={self.currency}, rate={self.sell_rate})>"
```

**Step 5: Implementar scheduler_status.py**

```python
# src/models/scheduler_status.py
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, func

from src.database import Base


class SchedulerStatus(Base):
    """Estado del scheduler de refrescos."""
    
    __tablename__ = "scheduler_status"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    last_error = Column(String, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    
    def __repr__(self) -> str:
        return f"<SchedulerStatus(last_run={self.last_run_at}, errors={self.error_count})>"
```

**Step 6: Implementar models/__init__.py**

```python
# src/models/__init__.py
from src.models.rate_snapshot import RateSnapshot
from src.models.scheduler_status import SchedulerStatus

__all__ = ["RateSnapshot", "SchedulerStatus"]
```

**Step 7: Ejecutar tests para verificar que pasan**

```bash
# Instalar pytest-asyncio para tests async
pip install pytest-asyncio
pytest tests/test_models.py -v
# Expected: PASS
```

**Step 8: Commit**

```bash
git add src/database.py src/models/ tests/test_models.py
git commit -m "feat: add SQLAlchemy models for rate snapshots and scheduler status"
```

---

## Task 4: Configurar Alembic para Migraciones

**Files:**
- Create: `taso-api/alembic.ini`
- Create: `taso-api/alembic/env.py`
- Create: `taso-api/alembic/script.py.mako`
- Create: `taso-api/alembic/versions/001_initial_migration.py`

**Step 1: Inicializar Alembic**

```bash
cd /home/ersus/tasalo/taso-api
alembic init alembic
```

**Step 2: Configurar alembic.ini**

Editar `alembic/alembic.ini` (movido desde la raíz):

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os

# URL de la base de datos - se sobrescribe con variable de entorno
sqlalchemy.url = sqlite+aiosqlite:///./tasalo.db

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

**Step 3: Configurar env.py para soportar async y variables de entorno**

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from src.database import Base
from src.models import RateSnapshot, SchedulerStatus
from src.config import get_settings

# Alembic Config object
config = context.config

# Cargar URL de base de datos desde settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model's MetaData object here
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 4: Generar migración inicial**

```bash
alembic revision --autogenerate -m "Initial migration - create rate_snapshots and scheduler_status tables"
```

**Step 5: Verificar migración generada**

```bash
# Debería crear alembic/versions/XXXX_initial_migration.py
# Verificar que contiene ambas tablas
cat alembic/versions/*.py
```

**Step 6: Aplicar migración**

```bash
alembic upgrade head
# Expected: INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
# Expected: INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
```

**Step 7: Verificar tablas creadas**

```bash
# Crear script de verificación
python -c "
import asyncio
from src.config import get_settings
from src.database import get_engine

async def check():
    settings = get_settings()
    engine = get_engine(settings.database_url)
    async with engine.connect() as conn:
        result = await conn.execute(
            \"SELECT name FROM sqlite_master WHERE type='table'\"
        )
        tables = result.fetchall()
        print('Tablas creadas:', [t[0] for t in tables])
    await engine.dispose()

asyncio.run(check())
"
# Expected: Tablas creadas: ['rate_snapshots', 'scheduler_status', 'alembic_version']
```

**Step 8: Commit**

```bash
git add alembic/ alembic.ini
git commit -m "feat: configure Alembic for async database migrations"
```

---

## Task 5: Aplicación FastAPI y Endpoint Health

**Files:**
- Create: `taso-api/src/main.py`
- Test: `taso-api/tests/test_main.py`

**Step 1: Escribir tests para la app**

```python
# tests/test_main.py
import pytest
from httpx import AsyncClient, ASGITransport

from src.main import app


@pytest.fixture
async def client():
    """Crear cliente de test async."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """GET /api/v1/health retorna estado correcto."""
    response = await client.get("/api/v1/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["ok"] is True
    assert "version" in data
    assert data["version"] == "1.0.0"
    assert "db" in data
    assert data["db"] in ["connected", "disconnected"]


@pytest.mark.asyncio
async def test_docs_available(client):
    """Swagger docs están disponibles."""
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_openapi_json(client):
    """OpenAPI spec está disponible."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    
    data = response.json()
    assert "openapi" in data
    assert data["info"]["title"] == "TASALO API"
    assert data["info"]["version"] == "1.0.0"
```

**Step 2: Ejecutar test para verificar que falla**

```bash
pytest tests/test_main.py -v
# Expected: FAIL - module 'src.main' not found
```

**Step 3: Implementar main.py**

```python
# src/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.database import get_engine, get_session_maker
from src.models import RateSnapshot, SchedulerStatus

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager para la aplicación."""
    # Startup: crear engine y verificar conexión
    app.state.engine = get_engine(settings.database_url, echo=False)
    app.state.db = get_session_maker(app.state.engine)
    
    # Verificar conexión a la base de datos
    try:
        async with app.state.engine.connect() as conn:
            await conn.execute("SELECT 1")
        app.state.db_connected = True
    except Exception:
        app.state.db_connected = False
    
    yield
    
    # Shutdown: cerrar engine
    await app.state.engine.dispose()


app = FastAPI(
    title="TASALO API",
    description="API para tasas de cambio en Cuba. Agrega datos de ElToque, CADECA, BCC y Binance.",
    version="1.0.0",
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
        "version": "1.0.0",
        "db": "connected" if app.state.db_connected else "disconnected",
        "database_url": settings.database_url.split("://")[0],  # Solo el tipo
    }
```

**Step 4: Ejecutar tests para verificar que pasan**

```bash
pytest tests/test_main.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add src/main.py tests/test_main.py
git commit -m "feat: add FastAPI app with health check endpoint"
```

---

## Task 6: README y Documentación

**Files:**
- Create: `taso-api/README.md`

**Step 1: Crear README completo**

```markdown
# TASALO API

Backend FastAPI para el ecosistema TASALO. Agrega tasas de cambio del mercado informal cubano (ElToque), CADECA, BCC y Binance, y las expone como API REST.

## Stack Tecnológico

- **Python 3.12+**
- **FastAPI** - Web framework
- **SQLAlchemy (async)** - ORM
- **Alembic** - Migraciones de base de datos
- **pydantic-settings** - Configuración
- **Base de datos:** SQLite (desarrollo) / PostgreSQL (producción)

## Desarrollo Rápido

### 1. Clonar y configurar entorno

```bash
git clone https://github.com/tasalo/taso-api.git
cd taso-api

python -m venv venv
source venv/bin/activate  # Linux/Mac
# o: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus valores (ver sección de Configuración)
```

### 3. Inicializar base de datos

```bash
alembic upgrade head
```

### 4. Correr el servidor

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en `http://localhost:8000`

### 5. Verificar funcionamiento

```bash
curl http://localhost:8000/api/v1/health
# Expected: {"ok":true,"version":"1.0.0","db":"connected","database_url":"sqlite"}
```

## Documentación API

Con el servidor corriendo, acceder a:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

## Configuración

Todas las variables de entorno están en `.env.example`:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `DATABASE_URL` | URL de conexión a la base de datos | `sqlite+aiosqlite:///./tasalo.db` |
| `ELTOQUE_API_KEY` | API key para ElToque | (requerido para scrapers) |
| `ELTOQUE_API_URL` | URL de la API de ElToque | `https://tasas.eltoque.com/v1/trmi` |
| `ADMIN_API_KEY` | Clave para endpoints admin | `changeme` |
| `REFRESH_INTERVAL_MINUTES` | Intervalo del scheduler | `5` |
| `ALLOWED_ORIGINS` | Orígenes CORS (separados por coma) | `*` |

### Ejemplo .env para desarrollo

```bash
DATABASE_URL=sqlite+aiosqlite:///./tasalo.db
ELTOQUE_API_KEY=tu_api_key_aqui
ADMIN_API_KEY=dev_secret_123
REFRESH_INTERVAL_MINUTES=5
ALLOWED_ORIGINS=*
```

### Ejemplo .env para producción (PostgreSQL)

```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/tasalo
ELTOQUE_API_KEY=tu_api_key_secreta
ADMIN_API_KEY=produccion_secret_456_xyz
REFRESH_INTERVAL_MINUTES=5
ALLOWED_ORIGINS=https://tasalo.app,https://bot.tasalo.app
```

## Migraciones de Base de Datos

### Crear nueva migración

```bash
alembic revision --autogenerate -m "Descripción del cambio"
```

### Aplicar migraciones

```bash
alembic upgrade head
```

### Revertir migración

```bash
alembic downgrade -1
```

### Ver estado actual

```bash
alembic current
```

## Testing

```bash
# Instalar dependencias de test
pip install pytest pytest-asyncio httpx

# Correr todos los tests
pytest

# Con verbose y coverage
pytest -v --cov=src --cov-report=term-missing
```

## Estructura del Proyecto

```
taso-api/
├── alembic/                 # Migraciones de Alembic
├── docs/
│   └── plans/              # Documentos de diseño y planificación
├── src/
│   ├── main.py             # Punto de entrada FastAPI
│   ├── config.py           # Configuración con pydantic-settings
│   ├── database.py         # Engine y sesiones de SQLAlchemy
│   └── models/             # Modelos ORM
│       ├── rate_snapshot.py
│       └── scheduler_status.py
├── tests/                  # Tests unitarios y de integración
├── .env.example            # Template de variables de entorno
├── requirements.txt        # Dependencias de Python
└── README.md               # Este archivo
```

## Endpoints Disponibles

### Health Check

```
GET /api/v1/health
```

Respuesta:
```json
{
  "ok": true,
  "version": "1.0.0",
  "db": "connected",
  "database_url": "sqlite"
}
```

## Próximas Fases

- **Fase 2:** Implementar scrapers (ElToque, CADECA, BCC, Binance)
- **Fase 3:** Servicio de tasas y scheduler con APScheduler
- **Fase 4:** Endpoints públicos de tasas
- **Fase 5:** Endpoints admin protegidos
- **Fase 6:** Hardening y documentación final

## License

MIT License - ver LICENSE para más detalles.

## Contacto

Organización: TASALO-TEAM
GitHub: https://github.com/tasalo
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add comprehensive README with setup instructions"
```

---

## Task 7: Verificación Final y Criterios de Éxito

**Step 1: Verificar que el servidor levanta**

```bash
cd /home/ersus/tasalo/taso-api
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 &
sleep 3
```

**Step 2: Verificar health endpoint**

```bash
curl -s http://localhost:8000/api/v1/health | python -m json.tool
# Expected:
# {
#     "ok": true,
#     "version": "1.0.0",
#     "db": "connected",
#     "database_url": "sqlite"
# }
```

**Step 3: Verificar Swagger UI**

```bash
curl -s http://localhost:8000/docs | head -20
# Expected: HTML con "TASALO API"
```

**Step 4: Correr todos los tests**

```bash
pytest -v
# Expected: Todos los tests pasan
```

**Step 5: Detener servidor**

```bash
pkill -f "uvicorn src.main:app"
```

**Step 6: Commit final de Fase 1**

```bash
git tag -a "v1.0.0-fase1" -m "Fase 1 completada - Scaffold y Base de Datos"
git push origin v1.0.0-fase1
```

---

## Resumen de Criterios de Éxito

- [x] `uvicorn src.main:app --reload` levanta el servidor en `http://localhost:8000`
- [x] `GET /api/v1/health` devuelve `{"ok": true, "db": "connected"}`
- [x] `GET /docs` muestra Swagger UI con el endpoint documentado
- [x] Alembic puede generar y aplicar migraciones
- [x] El código soporta SQLite (dev) y PostgreSQL (prod) sin cambios
- [x] Tests unitarios pasan
- [x] README documenta setup paso a paso

---

## Archivos Extra para Seguimiento

Después de completar este plan, se crearán dos archivos adicionales:

1. **`docs/PROGRESS.md`** - Tracking del progreso con timestamps
2. **`docs/CONTINUITY.md`** - Prompt de contexto para continuidad del agente
