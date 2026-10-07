"""Tests for PUT /routes/{route_id}/stops (docs/05-api-specification.md section 3).

The endpoint replaces a route's whole ordered stop list in one transaction, so
these tests focus on ordering, list-level validation and the resulting rows.
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.route_stop import RouteStop
from app.models.user import UserRole


def _stop(client, headers, api_url: str, name: str) -> str:
    response = client.post(
        f"{api_url}/stops",
        headers=headers,
        json={"name": name, "latitude": -17.8252, "longitude": 31.0335},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _setup(client, headers, api_url: str, stop_names=("Alpha", "Bravo")):
    """Create a published route with two stops and return (route_id, stop_ids)."""
    stop_ids = [_stop(client, headers, api_url, name) for name in stop_names]
    response = client.post(
        f"{api_url}/routes",
        headers=headers,
        json={
            "name": "Test Route",
            "code": "TST-1",
            "stops": [{"stop_id": stop_id} for stop_id in stop_ids],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"], stop_ids


def _detail_stops(client, api_url: str, route_id: str) -> list[dict]:
    response = client.get(f"{api_url}/routes/{route_id}")
    assert response.status_code == 200, response.text
    return response.json()["data"]["stops"]


# --- Happy path -------------------------------------------------------------


def test_put_replaces_the_whole_list_in_order(
    client, auth_headers, db_session: Session, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, (alpha, bravo) = _setup(client, headers, api_url)
    charlie = _stop(client, headers, api_url, name="Charlie")

    response = client.put(
        f"{api_url}/routes/{route_id}/stops",
        headers=headers,
        json={"stops": [{"stop_id": charlie}, {"stop_id": bravo}]},
    )

    assert response.status_code == 200
    stops = response.json()["data"]["stops"]
    assert [entry["stop_sequence"] for entry in stops] == [1, 2]
    assert [entry["stop_id"] for entry in stops] == [charlie, bravo]
    # Alpha is gone from the database, not merely hidden.
    remaining = {
        str(row.stop_id)
        for row in db_session.query(RouteStop).filter_by(route_id=route_id).all()
    }
    assert remaining == {charlie, bravo}


def test_put_renumbers_from_one(
    client, auth_headers, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, _ = _setup(client, headers, api_url)
    extra = [
        _stop(client, headers, api_url, name=f"Extra {i}") for i in range(3)
    ]

    response = client.put(
        f"{api_url}/routes/{route_id}/stops",
        headers=headers,
        json={"stops": [{"stop_id": stop_id} for stop_id in extra]},
    )

    assert response.status_code == 200
    stops = response.json()["data"]["stops"]
    assert [entry["stop_sequence"] for entry in stops] == [1, 2, 3]
    assert [entry["stop_id"] for entry in stops] == extra


def test_put_allows_partial_timings(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, (alpha, bravo) = _setup(client, headers, api_url)
    charlie = _stop(client, headers, api_url, name="Charlie")

    response = client.put(
        f"{api_url}/routes/{route_id}/stops",
        headers=headers,
        json={
            "stops": [
                {"stop_id": alpha},
                {"stop_id": bravo, "estimated_minutes_from_start": 5},
                {"stop_id": charlie},
            ]
        },
    )

    assert response.status_code == 200
    stops = response.json()["data"]["stops"]
    assert stops[0]["estimated_minutes_from_start"] is None
    assert stops[1]["estimated_minutes_from_start"] == 5


# --- Validation and conflicts ----------------------------------------------


def test_put_requires_at_least_two_stops(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, (alpha, _) = _setup(client, headers, api_url)

    response = client.put(
        f"{api_url}/routes/{route_id}/stops",
        headers=headers,
        json={"stops": [{"stop_id": alpha}]},
    )

    assert response.status_code == 422


def test_put_rejects_the_same_stop_twice(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, (alpha, bravo) = _setup(client, headers, api_url)

    response = client.put(
        f"{api_url}/routes/{route_id}/stops",
        headers=headers,
        json={"stops": [{"stop_id": alpha}, {"stop_id": alpha}, {"stop_id": bravo}]},
    )

    assert response.status_code == 422


def test_put_rejects_decreasing_timings(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, (alpha, bravo) = _setup(client, headers, api_url)

    response = client.put(
        f"{api_url}/routes/{route_id}/stops",
        headers=headers,
        json={
            "stops": [
                {"stop_id": alpha, "estimated_minutes_from_start": 20},
                {"stop_id": bravo, "estimated_minutes_from_start": 15},
            ]
        },
    )

    assert response.status_code == 422


def test_put_unknown_route_returns_404(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _, (alpha, bravo) = _setup(client, headers, api_url)

    response = client.put(
        f"{api_url}/routes/{uuid4()}/stops",
        headers=headers,
        json={"stops": [{"stop_id": alpha}, {"stop_id": bravo}]},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Route not found"


def test_put_unknown_stop_returns_404(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, (alpha, _) = _setup(client, headers, api_url)

    response = client.put(
        f"{api_url}/routes/{route_id}/stops",
        headers=headers,
        json={"stops": [{"stop_id": alpha}, {"stop_id": str(uuid4())}]},
    )

    assert response.status_code == 404
    assert response.json()["detail"].startswith("Stop not found")


def test_put_requires_management(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, (alpha, bravo) = _setup(client, headers, api_url)
    body = {"stops": [{"stop_id": alpha}, {"stop_id": bravo}]}

    assert (
        client.put(f"{api_url}/routes/{route_id}/stops", json=body).status_code
        == 401
    )
    for role in (UserRole.COMMUTER, UserRole.OPERATOR):
        response = client.put(
            f"{api_url}/routes/{route_id}/stops",
            headers=auth_headers(role=role),
            json=body,
        )
        assert response.status_code == 403, role
