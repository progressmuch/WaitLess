from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from app.core.config import settings
from app.db.base import Base

# Import the model package so that every table is registered on
# Base.metadata. Without this, autogenerate would not see any model and would
# generate empty migrations.
import app.models  # noqa: F401,E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ConfigParser treats "%" as an interpolation marker, so a database password
# containing "%" would break every `alembic` command. Escape it here.
config.set_main_option(
    "sqlalchemy.url", settings.database_url.replace("%", "%%")
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine_kwargs = {
        "prefix": "sqlalchemy.",
        "poolclass": pool.NullPool,
        "pool_pre_ping": True,
    }
    if not settings.database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {
            "connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS,
        }

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        **engine_kwargs,
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
