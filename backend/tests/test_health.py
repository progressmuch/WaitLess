import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_health_check(client: TestClient):
    """Phase 0 smoke test: the service is up.

    Uses the shared `client` fixture so the app is exercised through the same
    TestClient setup as the rest of the suite.
    """
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_schema_is_served(client: TestClient, api_url: str):
    """The versioned OpenAPI document must list the auth endpoints."""
    response = client.get(f"{api_url}/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert f"{api_url}/auth/register" in paths
    assert f"{api_url}/auth/login" in paths
    assert f"{api_url}/auth/me" in paths
    assert f"{api_url}/auth/users" in paths