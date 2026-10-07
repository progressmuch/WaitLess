"""Tests for the bus endpoints (docs/05-api-specification.md section 5).

The fleet is management-only, registration and fleet numbers are unique and
normalized, and a bus carries at most one route (`buses.route_id`).
"""

from uuid import uuid4

from app.models.user import UserRole


def _create_bus(
    client,
    headers,
    api_url: str,
    *,
    fleet_number: str = "BUS-01",
    registration_number: str = "ABC 1001",
    capacity: int = 40,
    route_id: str | None = None,
) -> dict:
    payload = {
        "registration_number": registration_number,
        "fleet_number": fleet_number,
        "capacity": capacity,
    }
    if route_id is not None:
        payload["route_id"] = route_id
    response = client.post(f"{api_url}/buses", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


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
            "name": "Bus Route",
            "code": code,
            "stops": [{"stop_id": stop_id} for stop_id in stop_ids],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


# --- Happy path -------------------------------------------------------------


def test_create_bus_normalizes_identifiers(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    data = _create_bus(
        client,
        headers,
        api_url,
        registration_number="  abc 1001 ",
        fleet_number="bus-7",
    )

    assert data["registration_number"] == "ABC 1001"
    assert data["fleet_number"] == "BUS-7"
    assert data["capacity"] == 40
    assert data["route_id"] is None
    assert data["is_active"] is True


def test_create_bus_can_start_assigned_to_a_route(
    client, auth_headers, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(client, headers, api_url)

    data = _create_bus(client, headers, api_url, route_id=route_id)

    assert data["route_id"] == route_id


def test_list_buses_returns_active_buses_only(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    first = _create_bus(client, headers, api_url, fleet_number="BUS-01")
    second = _create_bus(
        client,
        headers,
        api_url,
        fleet_number="BUS-02",
        registration_number="ABC 1002",
    )
    client.patch(
        f"{api_url}/buses/{second['id']}",
        headers=headers,
        json={"is_active": False},
    )

    response = client.get(f"{api_url}/buses", headers=headers)
    assert response.status_code == 200
    listed = [bus["id"] for bus in response.json()["data"]]
    assert first["id"] in listed
    assert second["id"] not in listed

    response = client.get(f"{api_url}/buses", headers=headers, params={"is_active": False})
    assert response.status_code == 200
    assert [bus["id"] for bus in response.json()["data"]] == [second["id"]]


def test_list_buses_orders_by_fleet_number(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _create_bus(client, headers, api_url, fleet_number="BUS-09")
    _create_bus(
        client, headers, api_url, fleet_number="BUS-01", registration_number="ABC 1002"
    )
    _create_bus(
        client, headers, api_url, fleet_number="BUS-05", registration_number="ABC 1003"
    )

    response = client.get(f"{api_url}/buses", headers=headers)
    assert response.status_code == 200
    assert [bus["fleet_number"] for bus in response.json()["data"]] == [
        "BUS-01",
        "BUS-05",
        "BUS-09",
    ]


# --- Conflicts and validation ----------------------------------------------


def test_duplicate_registration_returns_409(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _create_bus(client, headers, api_url)

    response = client.post(
        f"{api_url}/buses",
        headers=headers,
        json={
            "registration_number": "abc 1001",
            "fleet_number": "BUS-99",
            "capacity": 30,
        },
    )

    assert response.status_code == 409
    assert "Registration number" in response.json()["detail"]


def test_duplicate_fleet_number_returns_409(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _create_bus(client, headers, api_url)

    response = client.post(
        f"{api_url}/buses",
        headers=headers,
        json={
            "registration_number": "XYZ 9000",
            "fleet_number": "bus-01",
            "capacity": 30,
        },
    )

    assert response.status_code == 409
    assert "Fleet number" in response.json()["detail"]


def test_create_rejects_invalid_registration(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    response = client.post(
        f"{api_url}/buses",
        headers=headers,
        json={
            "registration_number": "!!bad!!",
            "fleet_number": "BUS-01",
            "capacity": 40,
        },
    )

    assert response.status_code == 422


def test_create_rejects_empty_identifiers(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    response = client.post(
        f"{api_url}/buses",
        headers=headers,
        json={"registration_number": "   ", "fleet_number": "BUS-01", "capacity": 40},
    )

    assert response.status_code == 422


def test_create_rejects_capacity_out_of_range(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    for capacity in (0, -5, 1001):
        response = client.post(
            f"{api_url}/buses",
            headers=headers,
            json={
                "registration_number": f"CAP {abs(capacity)}",
                "fleet_number": f"BUS-{abs(capacity)}",
                "capacity": capacity,
            },
        )
        assert response.status_code == 422, capacity


def test_create_rejects_unknown_route(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    response = client.post(
        f"{api_url}/buses",
        headers=headers,
        json={
            "registration_number": "ABC 1001",
            "fleet_number": "BUS-01",
            "capacity": 40,
            "route_id": str(uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"].startswith("Route not found")


def test_create_rejects_unknown_field(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    response = client.post(
        f"{api_url}/buses",
        headers=headers,
        json={
            "registration_number": "ABC 1001",
            "fleet_number": "BUS-01",
            "capacity": 40,
            "driver": "someone",
        },
    )

    assert response.status_code == 422


# --- PATCH ------------------------------------------------------------------


def test_patch_assigns_a_route(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(client, headers, api_url)
    bus = _create_bus(client, headers, api_url)

    response = client.patch(
        f"{api_url}/buses/{bus['id']}",
        headers=headers,
        json={"route_id": route_id},
    )

    assert response.status_code == 200
    assert response.json()["data"]["route_id"] == route_id


def test_patch_clears_the_route_with_null(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(client, headers, api_url)
    bus = _create_bus(client, headers, api_url, route_id=route_id)

    response = client.patch(
        f"{api_url}/buses/{bus['id']}", headers=headers, json={"route_id": None}
    )

    assert response.status_code == 200
    assert response.json()["data"]["route_id"] is None


def test_patch_normalizes_identifiers(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    bus = _create_bus(client, headers, api_url)

    response = client.patch(
        f"{api_url}/buses/{bus['id']}",
        headers=headers,
        json={"registration_number": " xyz 4321 "},
    )

    assert response.status_code == 200
    assert response.json()["data"]["registration_number"] == "XYZ 4321"


def test_patch_unknown_route_returns_404(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    bus = _create_bus(client, headers, api_url)

    response = client.patch(
        f"{api_url}/buses/{bus['id']}",
        headers=headers,
        json={"route_id": str(uuid4())},
    )

    assert response.status_code == 404


def test_patch_unknown_bus_returns_404(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    response = client.patch(
        f"{api_url}/buses/{uuid4()}", headers=headers, json={"capacity": 50}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Bus not found"


def test_patch_taking_another_buses_registration_returns_409(
    client, auth_headers, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _create_bus(client, headers, api_url, fleet_number="BUS-01")
    other = _create_bus(
        client, headers, api_url, fleet_number="BUS-02", registration_number="ABC 1002"
    )

    response = client.patch(
        f"{api_url}/buses/{other['id']}",
        headers=headers,
        json={"registration_number": "abc 1001"},
    )

    assert response.status_code == 409


def test_patch_rejects_an_empty_payload(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    bus = _create_bus(client, headers, api_url)

    response = client.patch(f"{api_url}/buses/{bus['id']}", headers=headers, json={})

    assert response.status_code == 422


def test_patch_rejects_null_capacity(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    bus = _create_bus(client, headers, api_url)

    response = client.patch(
        f"{api_url}/buses/{bus['id']}", headers=headers, json={"capacity": None}
    )

    assert response.status_code == 422


# --- Authorization ----------------------------------------------------------


def test_bus_endpoints_require_a_token(client, auth_headers, api_url: str):
    assert client.get(f"{api_url}/buses").status_code == 401
    assert (
        client.post(
            f"{api_url}/buses",
            json={
                "registration_number": "ABC 1001",
                "fleet_number": "BUS-01",
                "capacity": 40,
            },
        ).status_code
        == 401
    )
    assert (
        client.patch(f"{api_url}/buses/{uuid4()}", json={"capacity": 50}).status_code
        == 401
    )


def test_bus_endpoints_require_management(client, auth_headers, api_url: str):
    for role in (UserRole.COMMUTER, UserRole.OPERATOR):
        headers = auth_headers(role=role)
        assert client.get(f"{api_url}/buses", headers=headers).status_code == 403, role
        assert (
            client.post(
                f"{api_url}/buses",
                headers=headers,
                json={
                    "registration_number": "ABC 1001",
                    "fleet_number": "BUS-01",
                    "capacity": 40,
                },
            ).status_code
            == 403
        ), role
        assert (
            client.patch(
                f"{api_url}/buses/{uuid4()}", headers=headers, json={"capacity": 50}
            ).status_code
            == 403
        ), role
