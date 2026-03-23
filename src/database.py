"""Database configuration and session management."""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """Clase base para todos los modelos."""

    # Generar nombres de tablas automáticamente en minúsculas
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()


# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./tasalo.db")

# Engine and session factory (global fallback)
_engine = None
async_session_factory = None


def get_engine(database_url: str, echo: bool = False):
    """Crear engine de SQLAlchemy según el tipo de base de datos."""
    global _engine, async_session_factory
    
    if database_url.startswith("sqlite"):
        # SQLite necesita connect_args para async
        _engine = create_async_engine(
            database_url,
            echo=echo,
            connect_args={"check_same_thread": False},
        )
    else:
        # PostgreSQL
        _engine = create_async_engine(
            database_url,
            echo=echo,
            pool_pre_ping=True,  # Verificar conexiones antes de usar
        )
    
    async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    return _engine


def get_session_maker(engine):
    """Crear factory de sesiones."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_db():
    """
    Dependency provider para FastAPI.
    Yield una sesión de base de datos asíncrona.

    Usage:
        @app.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    # Inicializar engine si no existe
    global async_session_factory
    if async_session_factory is None:
        get_engine(DATABASE_URL, echo=False)
    
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
