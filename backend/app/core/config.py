"""Application configuration.

Values are read from environment variables and from a local `.env` file.
Phase 0 created this module with plain defaults; Phase 1 keeps every existing
setting and adds the JWT/database test settings that authentication needs.
"""

from typing import Any, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder secret that must never be used outside local development.
INSECURE_DEFAULT_SECRET_KEY = "change-me-in-production"


class Settings(BaseSettings):
    """Central settings object, instantiated once at import time."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application -----------------------------------------------------
    APP_NAME: str = "WaitLess"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # --- Database --------------------------------------------------------
    # Main application database.
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/waitless"
    # Optional dedicated database used by the automated test suite.
    # Falls back to DATABASE_URL with the database name replaced by
    # `TEST_DATABASE_NAME` when it is not set.
    TEST_DATABASE_URL: Optional[str] = None
    TEST_DATABASE_NAME: str = "waitless_test"
    # SSL mode used for database connections. Only applied when the
    # connection string does not carry an explicit `sslmode` query parameter.
    # Supabase requires "require" (or stricter) because it terminates TLS
    # at the pooler.
    DATABASE_SSL_MODE: str = "prefer"
    # Connection pool tuning. Supabase's connection pooler limits how many
    # backend sessions a client may hold open, so keep these small.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    # Recycle connections before the server or pooler closes them.
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_CONNECT_TIMEOUT_SECONDS: int = 10

    # --- Security / JWT --------------------------------------------------
    SECRET_KEY: str = INSECURE_DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @property
    def is_production(self) -> bool:
        """True when the app runs with production-like settings."""
        return self.ENVIRONMENT.strip().lower() in {"prod", "production"}

    @property
    def database_url(self) -> str:
        """The connection string with an explicitly pinned driver.

        SQLAlchemy 2.1 maps a bare `postgresql://` URL to the psycopg 3
        dialect, but the choice is invisible in the connection string and
        changes the package that must be installed. Pinning `+psycopg` here
        keeps the application, Alembic and the test suite on the same driver
        no matter what else happens to be installed, and turns a confusing
        "No module named 'psycopg'" failure into an obvious one.

        Only the scheme is rewritten; the rest of the URL (including an
        already URL-encoded password) is left byte-for-byte intact. A URL
        that names a driver explicitly is never touched.
        """
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def test_database_url(self) -> str:
        """The connection string the test suite should use.

        Reuses `TEST_DATABASE_URL` when it is set, otherwise falls back to
        `DATABASE_URL`. The driver is pinned the same way as in
        `database_url`. The database *name* is swapped for
        `TEST_DATABASE_NAME` by the test fixtures, not here.
        """
        url = self.TEST_DATABASE_URL or self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    def model_post_init(self, context: Any) -> None:
        """Fail fast on unsafe configuration instead of silently running.

        A default/placeholder SECRET_KEY is acceptable for local development
        but would allow anyone to forge access tokens in production.
        """
        if self.is_production and self.SECRET_KEY == INSECURE_DEFAULT_SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY must be set to a unique value when ENVIRONMENT is "
                "production. Generate one with: openssl rand -hex 32"
            )


settings = Settings()
