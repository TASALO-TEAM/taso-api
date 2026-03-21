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

# Engine and session factory
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


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
