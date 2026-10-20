"""Tests for the operator assignment endpoints (docs/05 section 6).

An operator gets exactly one active bus, a bus gets exactly one active driver,
the target user must be an OPERATOR, and assignments are ended rather than
deleted.
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.operator_assignment import OperatorAssignment
from app.models.user import UserRole


def _create_route(client, headers, api_url: str, code: str = "RTE-1") -> str:
    """Publish a two-stop route and return its id."""
    stop_ids = []
    for name in ("Alpha", "Bravo"):
        response = client.post(
            f"{api_url}/stops",
            headers=headers,
            json={"name": name, "latitude": -17.8252, "longitude": 31.0335},
        )
        assert response.status_code == 201, response.text
        stop_ids.append(response.json()["data"]["id"])

    response = client.post(
        f"{api_url}/routes",
        headers=headers,
        json={
            "name": "Operator Route",
            "code": code,
            "stops": [{"stop_id": stop_id} for stop_id in stop_ids],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _create_bus(
    client,
    headers,
    api_url: str,
    *,
    fleet_number: str = "BUS-01",
    registration_number: str = "ABC 1001",
    route_id: str | None = None,
) -> dict:
    payload = {
        "registration_number": registration_number,
        "fleet_number": fleet_number,
        "capacity": 40,
    }
    if route_id is not None:
        payload["route_id"] = route_id
    response = client.post(f"{api_url}/buses", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _assign(client, headers, api_url: str, operator_email, bus_id: str):
    return client.post(
        f"{api_url}/operators/{operator_email}/assignments",
        headers=headers,
        json={"bus_id": bus_id},
    )


# --- Happy path -------------------------------------------------------------


def test_assignment_returns_the_bus_and_its_route(
    client, auth_headers, user_factory, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    operator = user_factory(role=UserRole.OPERATOR)
    route_id = _create_route(client, headers, api_url)
    bus = _create_bus(client, headers, api_url, route_id=route_id)

    response = _assign(client, headers, api_url, operator.email, bus["id"])

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["operator_id"] == str(operator.id)
    assert data["bus_id"] == bus["id"]
    assert data["is_active"] is True
    assert data["ended_at"] is None
    assert data["bus"]["registration_number"] == "ABC 1001"
    assert data["bus"]["route"]["id"] == route_id
    assert data["bus"]["route"]["code"] == "RTE-1"


def test_assignment_without_a_route_returns_null_route(
    client, auth_headers, user_factory, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    operator = user_factory(role=UserRole.OPERATOR)
    bus = _create_bus(client, headers, api_url)

    response = _assign(client, headers, api_url, operator.email, bus["id"])

    assert response.status_code == 201, response.text
    assert response.json()["data"]["bus"]["route"] is None


def test_get_my_assignment_returns_bus_and_route(
    client, auth_headers, user_factory, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    operator = user_factory(role=UserRole.OPERATOR)
    route_id = _create_route(client, headers, api_url)
    bus = _create_bus(client, headers, api_url, route_id=route_id)
    _assign(client, headers, api_url, operator.email, bus["id"])

    response = client.get(
        f"{api_url}/operators/me/assignment",
        headers=auth_headers(user=operator),
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["operator_id"] == str(operator.id)
    assert data["bus"]["id"] == bus["id"]
    assert data["bus"]["route"]["id"] == route_id


# --- Conflicts and validation ----------------------------------------------


def test_assigning_a_commuter_returns_409(
    client, auth_headers, user_factory, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    commuter = user_factory(role=UserRole.COMMUTER)
    bus = _create_bus(client, headers, api_url)

    response = _assign(client, headers, api_url, commuter.email, bus["id"])

    assert response.status_code == 409
    assert "OPERATOR" in response.json()["detail"]


def test_unknown_operator_returns_404(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    bus = _create_bus(client, headers, api_url)

    response = _assign(
        client, headers, api_url, "nobody@example.com", bus["id"]
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_unknown_bus_returns_404(client, auth_headers, user_factory, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    operator = user_factory(role=UserRole.OPERATOR)

    response = _assign(client, headers, api_url, operator.email, str(uuid4()))

    assert response.status_code == 404
    assert response.json()["detail"] == "Bus not found"


def test_second_assignment_for_the_same_operator_returns_409(
    client, auth_headers, user_factory, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    operator = user_factory(role=UserRole.OPERATOR)
    first = _create_bus(client, headers, api_url, fleet_number="BUS-01")
    second = _create_bus(
        client, headers, api_url, fleet_number="BUS-02", registration_number="ABC 1002"
    )
    _assign(client, headers, api_url, operator.email, first["id"])

    response = _assign(client, headers, api_url, operator.email, second["id"])

    assert response.status_code == 409
    assert response.json()["detail"] == "Operator already has an active assignment"


def test_a_bus_with_a_driver_returns_409(
    client, auth_headers, user_factory, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    first_operator = user_factory(role=UserRole.OPERATOR)
    second_operator = user_factory(role=UserRole.OPERATOR)
    bus = _create_bus(client, headers, api_url)
    _assign(client, headers, api_url, first_operator.email, bus["id"])

    response = _assign(client, headers, api_url, second_operator.email, bus["id"])

    assert response.status_code == 409
    assert response.json()["detail"] == "Bus already has an active operator assignment"


def test_assignment_can_be_recreated_after_ending(
    client, auth_headers, user_factory, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    operator = user_factory(role=UserRole.OPERATOR)
    first = _create_bus(client, headers, api_url, fleet_number="BUS-01")
    second = _create_bus(
        client, headers, api_url, fleet_number="BUS-02", registration_number="ABC 1002"
    )
    _assign(client, headers, api_url, operator.email, first["id"])

    end = client.delete(
        f"{api_url}/operators/{operator.email}/assignments", headers=headers
    )
    assert end.status_code == 200, end.text

    response = _assign(client, headers, api_url, operator.email, second["id"])
    assert response.status_code == 201, response.text
    assert response.json()["data"]["bus_id"] == second["id"]


# --- Ending assignments -----------------------------------------------------


def test_end_marks_the_assignment_as_finished(
    client, auth_headers, user_factory, db_session, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    operator = user_factory(role=UserRole.OPERATOR)
    bus = _create_bus(client, headers, api_url)
    _assign(client, headers, api_url, operator.email, bus["id"])

    response = client.delete(
        f"{api_url}/operators/{operator.email}/assignments", headers=headers
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["is_active"] is False
    assert data["ended_at"] is not None
    # The row survives as history; only its state changed.
    row = (
        db_session.query(OperatorAssignment)
        .filter_by(operator_id=operator.id, bus_id=bus["id"])
        .one()
    )
    assert row.is_active is False
    assert row.ended_at is not None

    # And the operator no longer has an active assignment.
    follow_up = client.delete(
        f"{api_url}/operators/{operator.email}/assignments", headers=headers
    )
    assert follow_up.status_code == 404


def test_end_without_an_active_assignment_returns_404(
    client, auth_headers, user_factory, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    operator = user_factory(role=UserRole.OPERATOR)

    response = client.delete(
        f"{api_url}/operators/{operator.email}/assignments", headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Operator has no active assignment"


def test_get_my_assignment_without_one_returns_404(
    client, auth_headers, user_factory, api_url: str
):
    operator = user_factory(role=UserRole.OPERATOR)

    response = client.get(
        f"{api_url}/operators/me/assignment",
        headers=auth_headers(user=operator),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Operator has no active assignment"


# --- Authorization ----------------------------------------------------------


def test_assignment_writes_require_management(
    client, auth_headers, user_factory, api_url: str
):
    operator = user_factory(role=UserRole.OPERATOR)
    bus_id = str(uuid4())

    assert (
        client.post(
            f"{api_url}/operators/{operator.email}/assignments", json={"bus_id": bus_id}
        ).status_code
        == 401
    )
    assert (
        client.delete(f"{api_url}/operators/{operator.email}/assignments").status_code
        == 401
    )

    for role in (UserRole.COMMUTER, UserRole.OPERATOR):
        headers = auth_headers(role=role)
        assert (
            _assign(client, headers, api_url, operator.email, bus_id).status_code == 403
        ), role
        assert (
            client.delete(
                f"{api_url}/operators/{operator.email}/assignments", headers=headers
            ).status_code
            == 403
        ), role


def test_get_my_assignment_requires_the_operator_role(
    client, auth_headers, api_url: str
):
    assert client.get(f"{api_url}/operators/me/assignment").status_code == 401

    for role in (UserRole.COMMUTER, UserRole.MANAGEMENT):
        response = client.get(
            f"{api_url}/operators/me/assignment", headers=auth_headers(role=role)
        )
        assert response.status_code == 403, role


# --- Database-level rules ---------------------------------------------------


def test_database_rejects_a_second_active_assignment(
    client, auth_headers, user_factory, db_session, api_url: str
):
    """The partial unique index, not just the service check, backs the rule."""
    headers = auth_headers(role=UserRole.MANAGEMENT)
    operator = user_factory(role=UserRole.OPERATOR)
    first = _create_bus(client, headers, api_url, fleet_number="BUS-01")
    second = _create_bus(
        client, headers, api_url, fleet_number="BUS-02", registration_number="ABC 1002"
    )
    _assign(client, headers, api_url, operator.email, first["id"])

    db_session.add(
        OperatorAssignment(
            operator_id=operator.id, bus_id=second["id"], is_active=True
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_database_rejects_a_second_driver_for_one_bus(
    client, auth_headers, user_factory, db_session, api_url: str
):
    """Same for the "one active driver per bus" rule."""
    headers = auth_headers(role=UserRole.MANAGEMENT)
    operator = user_factory(role=UserRole.OPERATOR)
    bus = _create_bus(client, headers, api_url)
    other_bus = _create_bus(
        client, headers, api_url, fleet_number="BUS-02", registration_number="ABC 1002"
    )

    db_session.add(
        OperatorAssignment(operator_id=operator.id, bus_id=bus["id"], is_active=True)
    )
    db_session.flush()

    db_session.add(
        OperatorAssignment(
            operator_id=operator.id, bus_id=other_bus["id"], is_active=True
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
