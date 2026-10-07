"""Shared pytest fixtures.

Test database strategy
----------------------
Tests run against a real PostgreSQL database, not SQLite, because Phase 1
depends on PostgreSQL-specific behaviour (native UUID columns, timezone-aware
timestamps, server defaults and CHECK constraints). SQLite would silently pass
tests that break in production.

The test database name defaults to `waitless_test`
(`settings.TEST_DATABASE_NAME`), or to the database in `TEST_DATABASE_URL`
when that variable is set. It is created automatically if missing and is never
the development database.

Isolation
---------
Every test runs inside a transaction that is rolled back afterwards, so tests
cannot see each other's rows and the database is left clean.
"""

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

# Importing the models package registers all tables on Base.metadata before
# `create_all` runs.
import app.models  # noqa: F401  isort:skip
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.user import User, UserRole

# Password used for every user created by a test fixture.
TEST_PASSWORD = "Password123!"


def _resolve_test_database_url() -> URL:
    """Work out which PostgreSQL database the tests should use."""
    if settings.TEST_DATABASE_URL:
        return make_url(settings.TEST_DATABASE_URL)

    # Same server/credentials as the app, different database name.
    return make_url(settings.DATABASE_URL).set(database=settings.TEST_DATABASE_NAME)


@pytest.fixture(scope="session")
def engine() -> Iterator[Any]:
    """Create the test database if needed and build the schema once per run."""
    url = _resolve_test_database_url()

    # Connect to the maintenance database to create the test database.
    admin_engine = create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    with admin_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": url.database},
        ).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin_engine.dispose()

    test_engine = create_engine(url, poolclass=NullPool)
    Base.metadata.create_all(test_engine)

    yield test_engine

    # Remove the schema again; the empty database itself is kept.
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def db_session(engine: Any) -> Iterator[Session]:
    """Provide a session whose changes are rolled back at the end of the test.

    `join_transaction_mode="create_savepoint"` makes a `session.commit()`
    inside the application code release a SAVEPOINT instead of committing the
    outer transaction. That way the service layer can commit normally while
    the test still rolls everything back.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """TestClient wired to the transactional test session."""
    # Endpoints depend on `get_db`; point it at the test session instead of
    # the application's real database.
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_password() -> str:
    """Plaintext password that fixture-created users know."""
    return TEST_PASSWORD


@pytest.fixture
def user_factory(db_session: Session):
    """Insert users directly, bypassing the API, to set up test state.

    Usage: `user_factory(role=UserRole.OPERATOR, email="op@example.com")`
    """

    def _create_user(
        role: UserRole = UserRole.COMMUTER,
        *,
        is_active: bool = True,
        password: str = TEST_PASSWORD,
        email: str | None = None,
        full_name: str | None = None,
    ) -> User:
        user = User(
            full_name=full_name or f"Test {role.value.title()}",
            email=email or f"{role.value.lower()}-{uuid4().hex[:8]}@example.com",
            phone=None,
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def auth_headers(db_session: Session):
    """Build an Authorization header for a given user or role.

    Usage:
        headers = auth_headers(role=UserRole.MANAGEMENT)
        headers = auth_headers(user=some_user)
        headers = auth_headers(token=some_raw_jwt)
    """

    def _auth_headers(
        user: User | None = None,
        *,
        role: UserRole | None = None,
        token: str | None = None,
    ) -> dict[str, str]:
        if token is None:
            if user is None:
                assert role is not None, "provide a user, a role or a token"
                user = create_user_for_role(db_session, role)
            token = create_access_token(user.id)
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers


def create_user_for_role(db: Session, role: UserRole) -> User:
    """Convenience helper: create a user with the given role."""
    user = User(
        full_name=f"Test {role.value.title()}",
        email=f"{role.value.lower()}-{uuid4().hex[:8]}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def api_url() -> str:
    """Base path for all versioned endpoints."""
    return settings.API_V1_STR