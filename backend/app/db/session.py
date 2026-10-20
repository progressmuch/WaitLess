from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings


def _engine_options() -> dict:
    """Build the keyword arguments used to create the SQLAlchemy engine.

    `pool_pre_ping` makes SQLAlchemy validate a connection before handing it
    out. This matters against Supabase because the connection pooler closes
    idle sessions, and a stale connection would otherwise surface as a
    `OperationalError` on the first request after a quiet period.

    The SSL mode is only injected when `DATABASE_URL` does not already
    contain an `sslmode` query parameter, so an explicit value in the
    connection string always wins.
    """
    url = make_url(settings.database_url)
    options: dict = {"pool_pre_ping": True}

    # SQLite (used by a few local experiments) does not support pooling
    # arguments or psycopg2 connect options.
    if url.drivername.startswith("sqlite"):
        return options

    options.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    )

    connect_args: dict = {
        "connect_timeout": settings.DB_CONNECT_TIMEOUT_SECONDS,
    }
    if "sslmode" not in url.query:
        connect_args["sslmode"] = settings.DATABASE_SSL_MODE

    options["connect_args"] = connect_args
    return options


engine = create_engine(settings.database_url, **_engine_options())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
