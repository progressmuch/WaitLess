"""SQLAlchemy models.

Every model module is imported here so that `Base.metadata` is complete.
Alembic (`alembic/env.py`) relies on this to detect schema changes.
"""

from app.models.user import User, UserRole

__all__ = ["User", "UserRole"]
