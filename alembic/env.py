"""Alembic env.py configured for async SQLAlchemy."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from src.database import Base, _parse_ssl_params
from src.models import RateSnapshot, SchedulerStatus, CubanomicRate
from src.config import get_settings
from sqlalchemy.engine import make_url

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Cargar URL de base de datos desde settings, parseando SSL
settings = get_settings()
parsed_url = make_url(settings.database_url)
if not parsed_url.drivername.startswith("sqlite"):
    _alembic_connect_args, clean_url = _parse_ssl_params(parsed_url)
    _alembic_connect_args.setdefault("statement_cache_size", 0)
    config.set_main_option("sqlalchemy.url", clean_url.render_as_string(hide_password=False))
else:
    _alembic_connect_args = {}
    config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transaction_per_migration=False,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        transaction_per_migration=True,
    )
    context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    engine_cfg = {
        "sqlalchemy.url": config.get_main_option("sqlalchemy.url"),
    }
    connectable = async_engine_from_config(
        engine_cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=_alembic_connect_args,
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
