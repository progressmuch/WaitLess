"""API tests for registration, login and /auth/me.

Covers docs/07-testing-strategy.md sections 3 and 5.
"""

from datetime import timedelta
from uuid import uuid4

from jose import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User


# --- Registration -----------------------------------------------------------

def test_register_creates_commuter(
    client, db_session: Session, api_url: str
):
    payload = {
        "full_name": "Alice Commuter",
        "email": "Alice@Example.COM",
        "phone": "+263771234567",
        "password": "Password123!",
    }

    response = client.post(f"{api_url}/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["message"] == "Registration successful"
    user_data = body["data"]
    assert user_data["full_name"] == "Alice Commuter"
    # Email is normalised to lower case for consistent uniqueness.
    assert user_data["email"] == "alice@example.com"
    assert user_data["role"] == "COMMUTER"
    assert user_data["is_active"] is True
    assert user_data["id"]

    # And the row really exists in the database.
    stored = db_session.query(User).filter_by(email="alice@example.com").one()
    assert stored.full_name == "Alice Commuter"
    assert stored.role.value == "COMMUTER"


def test_register_never_returns_password_or_hash(client, api_url: str):
    response = client.post(
        f"{api_url}/auth/register",
        json={
            "full_name": "Alice",
            "email": "alice@example.com",
            "password": "Password123!",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert "password" not in data
    assert "password_hash" not in data


def test_register_rejects_duplicate_email(client, api_url: str):
    payload = {
        "full_name": "Alice",
        "email": "duplicate@example.com",
        "password": "Password123!",
    }
    first = client.post(f"{api_url}/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post(
        f"{api_url}/auth/register",
        json={**payload, "full_name": "Another Alice"},
    )

    assert second.status_code == 409
    assert "already registered" in second.json()["detail"]


def test_register_rejects_duplicate_email_case_insensitively(client, api_url: str):
    client.post(
        f"{api_url}/auth/register",
        json={
            "full_name": "Alice",
            "email": "dup@example.com",
            "password": "Password123!",
        },
    )

    response = client.post(
        f"{api_url}/auth/register",
        json={
            "full_name": "Alice Again",
            "email": "DUP@example.com",
            "password": "Password123!",
        },
    )

    assert response.status_code == 409


def test_register_rejects_invalid_email(client, api_url: str):
    response = client.post(
        f"{api_url}/auth/register",
        json={
            "full_name": "Alice",
            "email": "not-an-email",
            "password": "Password123!",
        },
    )

    assert response.status_code == 422


def test_register_rejects_short_password(client, api_url: str):
    response = client.post(
        f"{api_url}/auth/register",
        json={
            "full_name": "Alice",
            "email": "alice@example.com",
            "password": "short",
        },
    )

    assert response.status_code == 422


def test_register_cannot_self_assign_a_role(client, api_url: str):
    """Public registration must not be able to grant itself a staff role."""
    for role in ("OPERATOR", "MANAGEMENT"):
        response = client.post(
            f"{api_url}/auth/register",
            json={
                "full_name": "Sneaky",
                "email": f"sneaky-{role.lower()}@example.com",
                "password": "Password123!",
                "role": role,
            },
        )

        assert response.status_code == 422, response.text


def test_register_requires_all_fields(client, api_url: str):
    response = client.post(
        f"{api_url}/auth/register", json={"email": "alice@example.com"}
    )

    assert response.status_code == 422


# --- Login ------------------------------------------------------------------

def test_login_success(client, user_factory, test_password: str, api_url: str):
    user = user_factory(email="login@example.com")

    response = client.post(
        f"{api_url}/auth/login",
        json={"email": "login@example.com", "password": test_password},
    )

    assert response.status_code == 200
    token_data = response.json()["data"]
    assert token_data["token_type"] == "bearer"
    assert token_data["access_token"]
    # 30 minutes by default (ACCESS_TOKEN_EXPIRE_MINUTES).
    assert token_data["expires_in"] == 30 * 60

    # The returned token really belongs to this user.
    me = client.get(
        f"{api_url}/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["id"] == str(user.id)


def test_login_accepts_mixed_case_email(
    client, user_factory, test_password: str, api_url: str
):
    user_factory(email="caseless@example.com")

    response = client.post(
        f"{api_url}/auth/login",
        json={"email": "CaseLess@Example.com", "password": test_password},
    )

    assert response.status_code == 200


def test_login_rejects_wrong_password(client, user_factory, api_url: str):
    user_factory(email="wrongpw@example.com")

    response = client.post(
        f"{api_url}/auth/login",
        json={"email": "wrongpw@example.com", "password": "WrongPassword123!"},
    )

    assert response.status_code == 401


def test_login_unknown_email_returns_same_response_as_wrong_password(
    client, user_factory, test_password: str, api_url: str
):
    """Identical responses prevent user enumeration."""
    user_factory(email="real@example.com")

    wrong_password = client.post(
        f"{api_url}/auth/login",
        json={"email": "real@example.com", "password": "WrongPassword123!"},
    )
    unknown_email = client.post(
        f"{api_url}/auth/login",
        json={"email": "nobody@example.com", "password": test_password},
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_login_rejects_deactivated_account(
    client, user_factory, test_password: str, api_url: str
):
    user_factory(email="disabled@example.com", is_active=False)

    response = client.post(
        f"{api_url}/auth/login",
        json={"email": "disabled@example.com", "password": test_password},
    )

    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"]


def test_login_requires_email_and_password(client, api_url: str):
    assert client.post(f"{api_url}/auth/login", json={}).status_code == 422


# --- Current user -----------------------------------------------------------

def test_me_returns_authenticated_profile(
    client, user_factory, auth_headers, api_url: str
):
    user = user_factory(full_name="Bob Rider")

    response = client.get(f"{api_url}/auth/me", headers=auth_headers(user))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == str(user.id)
    assert data["full_name"] == "Bob Rider"
    assert data["email"] == user.email
    assert data["role"] == "COMMUTER"
    assert "password_hash" not in data


def test_me_rejects_missing_token(client, api_url: str):
    response = client.get(f"{api_url}/auth/me")

    assert response.status_code == 401


def test_me_rejects_malformed_token(client, api_url: str):
    response = client.get(
        f"{api_url}/auth/me",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_me_rejects_token_signed_with_wrong_secret(client, api_url: str):
    forged = jwt.encode(
        {"sub": str(uuid4()), "type": "access", "exp": 9999999999},
        "some-other-secret",
        algorithm=settings.ALGORITHM,
    )

    response = client.get(
        f"{api_url}/auth/me",
        headers={"Authorization": f"Bearer {forged}"},
    )

    assert response.status_code == 401


def test_me_rejects_expired_token(client, user_factory, api_url: str):
    user = user_factory()
    expired = create_access_token(user.id, expires_delta=timedelta(seconds=-1))

    response = client.get(
        f"{api_url}/auth/me",
        headers={"Authorization": f"Bearer {expired}"},
    )

    assert response.status_code == 401


def test_me_rejects_token_for_deleted_user(client, api_url: str):
    """A valid token for a user that no longer exists must not be accepted."""
    response = client.get(
        f"{api_url}/auth/me",
        headers={"Authorization": f"Bearer {create_access_token(uuid4())}"},
    )

    assert response.status_code == 401


def test_me_rejects_token_after_deactivation(
    client, user_factory, test_password: str, db_session: Session, api_url: str
):
    """Deactivating an account must invalidate its already-issued tokens."""
    user = user_factory(email="deactivate-me@example.com")

    login = client.post(
        f"{api_url}/auth/login",
        json={"email": "deactivate-me@example.com", "password": test_password},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    assert client.get(f"{api_url}/auth/me", headers=headers).status_code == 200

    # Deactivate directly in the database, as management would later.
    user.is_active = False
    db_session.commit()

    response = client.get(f"{api_url}/auth/me", headers=headers)

    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"]