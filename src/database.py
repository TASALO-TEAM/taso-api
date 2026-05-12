"""Database configuration and session management."""

import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, declared_attr
from sqlalchemy.engine import make_url


class Base(DeclarativeBase):
    """Clase base para todos los modelos."""

    # Generar nombres de tablas automáticamente en minúsculas
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()


# Engine and session factory (initialized by get_engine)
_engine = None
async_session_factory = None


def _parse_ssl_params(url: make_url) -> tuple[dict, make_url]:
    """Extrae parámetros SSL de la URL y los traduce a connect_args para asyncpg.

    asyncpg no acepta 'sslmode' como kwarg; usa 'ssl' (bool o SSLContext).
    Esta función traduce sslmode=require → ssl=True, etc.
    """
    query = dict(url.query)
    connect_args = {}

    if 'sslmode' in query:
        sslmode = query['sslmode']
        if sslmode == 'require':
            connect_args['ssl'] = True
        elif sslmode in ('verify-ca', 'verify-full'):
            # Para verify-ca/verify-full necesitamos un SSLContext
            ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            if 'sslrootcert' in query:
                ctx.load_verify_locations(cafile=query['sslrootcert'])
            ctx.check_hostname = (sslmode == 'verify-full')
            ctx.verify_mode = ssl.CERT_REQUIRED
            connect_args['ssl'] = ctx
        elif sslmode == 'disable':
            connect_args['ssl'] = False
        # Eliminar sslmode de la URL para que no se pase doble (ya via connect_args)
        url = url.difference_update_query(['sslmode'])

    return connect_args, url


def get_engine(database_url: str, echo: bool = False):
    """Crear engine de SQLAlchemy según el tipo de base de datos."""
    global _engine, async_session_factory

    url = make_url(database_url)
    connect_args = {}

    if url.drivername.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        _engine = create_async_engine(
            str(url),
            echo=echo,
            connect_args=connect_args,
        )
    else:
        # PostgreSQL/asyncpg — manejar SSL si está presente en la URL
        connect_args, url = _parse_ssl_params(url)
        _engine = create_async_engine(
            str(url),
            echo=echo,
            pool_pre_ping=True,
            connect_args=connect_args,
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
        # Lazy-load de configuración Pydantic (evita dependencia circular en importación)
        from src.config import get_settings
        settings = get_settings()
        get_engine(settings.database_url, echo=False)

    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
