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

    # --- Security / JWT --------------------------------------------------
    SECRET_KEY: str = INSECURE_DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    @property
    def is_production(self) -> bool:
        """True when the app runs with production-like settings."""
        return self.ENVIRONMENT.strip().lower() in {"prod", "production"}

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
