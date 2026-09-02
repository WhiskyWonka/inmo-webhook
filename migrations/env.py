from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.config import Settings

import app.db  # noqa: F401 — register models with Base.metadata
from app.db.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve the database URL from application settings.

    The URL comes from the ``DATABASE_URL`` environment variable (via
    ``app.config.Settings``), never from ``alembic.ini``. This keeps the
    connection string out of version-controlled configuration and lets each
    environment (local, CI, Docker) supply its own. An empty default makes the
    failure mode explicit instead of silently connecting to a placeholder.
    """
    return Settings().database_url


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    url = _database_url()
    connectable = engine_from_config(
        {
            **config.get_section(config.config_ini_section, {}),
            "sqlalchemy.url": url,
        },
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
