"""Role-based authorization tests.

Verifies docs/07-testing-strategy.md section 5: "Commuter cannot access
management endpoints". `POST /auth/users` is the MANAGEMENT-only endpoint used
as the authorization probe.
"""

from sqlalchemy.orm import Session

from app.models.user import User, UserRole


def _payload(email: str, role: str = UserRole.OPERATOR.value) -> dict:
    return {
        "full_name": "Staff Member",
        "email": email,
        "password": "Password123!",
        "role": role,
    }


# --- Happy path -------------------------------------------------------------

def test_management_can_create_operator_user(
    client, auth_headers, db_session: Session, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    response = client.post(
        f"{api_url}/auth/users",
        headers=headers,
        json=_payload("new-operator@example.com"),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["role"] == "OPERATOR"
    assert data["email"] == "new-operator@example.com"

    created = db_session.query(User).filter_by(email="new-operator@example.com").one()
    assert created.role is UserRole.OPERATOR


def test_management_can_create_management_user(
    client, auth_headers, db_session: Session, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    response = client.post(
        f"{api_url}/auth/users",
        headers=headers,
        json=_payload("new-manager@example.com", UserRole.MANAGEMENT.value),
    )

    assert response.status_code == 201
    assert response.json()["data"]["role"] == "MANAGEMENT"


def test_created_user_can_log_in(
    client, auth_headers, api_url: str
):
    """The whole flow: management creates an operator, operator logs in."""
    client.post(
        f"{api_url}/auth/users",
        headers=auth_headers(role=UserRole.MANAGEMENT),
        json=_payload("operator-login@example.com"),
    )

    response = client.post(
        f"{api_url}/auth/login",
        json={
            "email": "operator-login@example.com",
            "password": "Password123!",
        },
    )

    assert response.status_code == 200
    token = response.json()["data"]["access_token"]
    me = client.get(
        f"{api_url}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.json()["data"]["role"] == "OPERATOR"


# --- Denied: wrong role -----------------------------------------------------

def test_commuter_cannot_create_users(
    client, auth_headers, db_session: Session, api_url: str
):
    headers = auth_headers(role=UserRole.COMMUTER)

    response = client.post(
        f"{api_url}/auth/users",
        headers=headers,
        json=_payload("commuter-made-this@example.com"),
    )

    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()
    # Nothing was written.
    assert (
        db_session.query(User)
        .filter_by(email="commuter-made-this@example.com")
        .count()
        == 0
    )


def test_operator_cannot_create_users(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.OPERATOR)

    response = client.post(
        f"{api_url}/auth/users",
        headers=headers,
        json=_payload("operator-made-this@example.com"),
    )

    assert response.status_code == 403


def test_anonymous_cannot_create_users(client, api_url: str):
    response = client.post(
        f"{api_url}/auth/users",
        json=_payload("anonymous-made-this@example.com"),
    )

    assert response.status_code == 401


# --- Denied: bad credentials and validation --------------------------------

def test_management_endpoint_rejects_invalid_token(client, api_url: str):
    response = client.post(
        f"{api_url}/auth/users",
        headers={"Authorization": "Bearer garbage"},
        json=_payload("garbage-token@example.com"),
    )

    assert response.status_code == 401


def test_create_user_rejects_unknown_role(
    client, auth_headers, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    response = client.post(
        f"{api_url}/auth/users",
        headers=headers,
        json=_payload("bad-role@example.com", "SUPERADMIN"),
    )

    assert response.status_code == 422


def test_create_user_rejects_duplicate_email(
    client, auth_headers, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    payload = _payload("duplicate-staff@example.com")

    first = client.post(f"{api_url}/auth/users", headers=headers, json=payload)
    assert first.status_code == 201

    second = client.post(f"{api_url}/auth/users", headers=headers, json=payload)

    assert second.status_code == 409


def test_create_user_rejects_weak_password(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    response = client.post(
        f"{api_url}/auth/users",
        headers=headers,
        json={**_payload("weak-staff@example.com"), "password": "abc"},
    )

    assert response.status_code == 422


# --- All authenticated roles can read their own profile ---------------------

def test_every_role_can_access_me(client, auth_headers, api_url: str):
    for role in UserRole:
        response = client.get(
            f"{api_url}/auth/me",
            headers=auth_headers(role=role),
        )

        assert response.status_code == 200, role
        assert response.json()["data"]["role"] == role.value


def test_role_comes_from_database_not_token(
    client, auth_headers, user_factory, db_session: Session, api_url: str
):
    """A token minted while a user was an operator stops working for staff-only
    endpoints once the role is changed in the database."""
    user = user_factory(role=UserRole.OPERATOR, email="promoted@example.com")
    headers = auth_headers(user)

    assert (
        client.post(
            f"{api_url}/auth/users",
            headers=headers,
            json=_payload("should-not-work@example.com"),
        ).status_code
        == 403
    )

    user.role = UserRole.MANAGEMENT
    db_session.commit()

    assert (
        client.post(
            f"{api_url}/auth/users",
            headers=headers,
            json=_payload("now-allowed@example.com"),
        ).status_code
        == 201
    )