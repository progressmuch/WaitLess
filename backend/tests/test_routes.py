"""Route endpoint tests.

Covers docs/07-testing-strategy.md sections 3-5: the happy paths, validation
and conflicts for routes, plus the role matrix (commuter and operator cannot
reach management writes; anonymous callers cannot reach them either).
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.route import Route
from app.models.user import UserRole


def _stop(
    client,
    headers,
    api_url: str,
    name: str = "Market",
    latitude: float = -17.8252,
    longitude: float = 31.0335,
) -> str:
    """Create a stop through the API and return its id."""
    response = client.post(
        f"{api_url}/stops",
        headers=headers,
        json={"name": name, "latitude": latitude, "longitude": longitude},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _create_stops(client, headers, api_url: str, count: int = 2) -> list[str]:
    return [_stop(client, headers, api_url, name=f"Stop {i}") for i in range(count)]


def _create_route(
    client,
    headers,
    api_url: str,
    code: str = "HR-CHI",
    stops: list[str] | None = None,
) -> str:
    """Create a route (draft when `stops` is None) and return its id."""
    payload: dict = {"name": "Harare - Chitungwiza", "code": code}
    if stops is not None:
        payload["stops"] = [{"stop_id": stop_id} for stop_id in stops]
    response = client.post(f"{api_url}/routes", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


# --- Reads are public -------------------------------------------------------


def test_list_routes_is_public(client, api_url: str):
    response = client.get(f"{api_url}/routes")

    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["message"] == "Success"


def test_get_route_is_public(client, auth_headers, api_url: str):
    management = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(
        client, management, api_url, stops=_create_stops(client, management, api_url)
    )

    # No Authorization header at all.
    response = client.get(f"{api_url}/routes/{route_id}")

    assert response.status_code == 200
    assert response.json()["data"]["code"] == "HR-CHI"


def test_get_route_returns_ordered_stops(client, auth_headers, api_url: str):
    management = auth_headers(role=UserRole.MANAGEMENT)
    first = _stop(client, management, api_url, name="Terminus")
    second = _stop(client, management, api_url, name="Town Centre")
    route_id = _create_route(
        client, management, api_url, stops=[first, second]
    )

    stops = client.get(f"{api_url}/routes/{route_id}").json()["data"]["stops"]

    # Ordered by stop_sequence, each entry carrying the stop's own details.
    assert [entry["stop_sequence"] for entry in stops] == [1, 2]
    assert [entry["stop_id"] for entry in stops] == [first, second]
    assert stops[0]["stop"]["name"] == "Terminus"
    assert stops[0]["stop"]["latitude"] == -17.8252


def test_get_route_unknown_id_returns_404(client, api_url: str):
    response = client.get(f"{api_url}/routes/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Route not found"


def test_get_route_invalid_uuid_returns_422(client, api_url: str):
    response = client.get(f"{api_url}/routes/not-a-uuid")

    assert response.status_code == 422


def test_list_routes_returns_only_active_routes(
    client, auth_headers, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _create_route(client, headers, api_url, code="PUB-1", stops=_create_stops(client, headers, api_url))
    _create_route(client, headers, api_url, code="DRAFT-1")  # no stops, inactive

    listed = client.get(f"{api_url}/routes").json()["data"]

    assert [route["code"] for route in listed] == ["PUB-1"]


def test_list_routes_is_active_filter(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _create_route(client, headers, api_url, code="PUB-1", stops=_create_stops(client, headers, api_url))
    _create_route(client, headers, api_url, code="DRAFT-1")

    drafts = client.get(f"{api_url}/routes", params={"is_active": False}).json()["data"]

    assert [route["code"] for route in drafts] == ["DRAFT-1"]


def test_deactivated_route_survives_but_leaves_the_list(
    client, auth_headers, db_session: Session, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(
        client, headers, api_url, stops=_create_stops(client, headers, api_url)
    )

    patched = client.patch(
        f"{api_url}/routes/{route_id}", headers=headers, json={"is_active": False}
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["is_active"] is False

    # Hidden from the public list...
    assert client.get(f"{api_url}/routes").json()["data"] == []
    # ...but still readable by id, which is what management needs.
    detail = client.get(f"{api_url}/routes/{route_id}")
    assert detail.status_code == 200
    assert detail.json()["data"]["is_active"] is False
    assert len(detail.json()["data"]["stops"]) == 2
    # Not deleted from the database either.
    assert db_session.get(Route, route_id) is not None


# --- Create -----------------------------------------------------------------


def test_management_creates_draft_route(client, auth_headers, api_url: str):
    response = client.post(
        f"{api_url}/routes",
        headers=auth_headers(role=UserRole.MANAGEMENT),
        json={"name": "Draft Route", "code": "d1"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["is_active"] is False  # business rule 5: stops first
    assert data["code"] == "D1"  # stored upper-cased
    assert response.json()["message"] == "Route created successfully"


def test_create_route_with_stops_publishes_it(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    stops = _create_stops(client, headers, api_url)

    response = client.post(
        f"{api_url}/routes",
        headers=headers,
        json={
            "name": "Harare - Chitungwiza",
            "code": "hr-chi",
            "description": "  Main corridor  ",
            "stops": [
                {"stop_id": stops[0]},
                {"stop_id": stops[1], "estimated_minutes_from_start": 25},
            ],
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["is_active"] is True
    assert data["code"] == "HR-CHI"
    assert data["description"] == "Main corridor"


def test_create_route_rejects_single_stop(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    stops = _create_stops(client, headers, api_url, count=1)

    response = client.post(
        f"{api_url}/routes",
        headers=headers,
        json={"name": "Too short", "code": "TS-1", "stops": [{"stop_id": stops[0]}]},
    )

    assert response.status_code == 422


def test_create_route_rejects_duplicate_stop(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    stops = _create_stops(client, headers, api_url, count=1)

    response = client.post(
        f"{api_url}/routes",
        headers=headers,
        json={
            "name": "Loop",
            "code": "LP-1",
            "stops": [{"stop_id": stops[0]}, {"stop_id": stops[0]}],
        },
    )

    assert response.status_code == 422


def test_create_route_rejects_unknown_stop(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    known = _create_stops(client, headers, api_url, count=1)

    response = client.post(
        f"{api_url}/routes",
        headers=headers,
        json={
            "name": "Ghost stop",
            "code": "GS-1",
            "stops": [{"stop_id": known[0]}, {"stop_id": str(uuid4())}],
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"].startswith("Stop not found")


def test_create_route_rejects_invalid_code(client, auth_headers, api_url: str):
    response = client.post(
        f"{api_url}/routes",
        headers=auth_headers(role=UserRole.MANAGEMENT),
        json={"name": "Bad code", "code": "not a code!"},
    )

    assert response.status_code == 422


def test_create_route_rejects_duplicate_code(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _create_route(client, headers, api_url, code="R1")

    # Same code in a different case is still the same code.
    response = client.post(
        f"{api_url}/routes",
        headers=headers,
        json={"name": "Duplicate", "code": "r1"},
    )

    assert response.status_code == 409
    assert "already in use" in response.json()["detail"]


def test_create_route_rejects_extra_fields(client, auth_headers, api_url: str):
    response = client.post(
        f"{api_url}/routes",
        headers=auth_headers(role=UserRole.MANAGEMENT),
        json={"name": "Sneaky", "code": "SN-1", "is_active": True},
    )

    assert response.status_code == 422


def test_create_route_rejects_decreasing_timings(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    stops = _create_stops(client, headers, api_url)

    response = client.post(
        f"{api_url}/routes",
        headers=headers,
        json={
            "name": "Backwards",
            "code": "BW-1",
            "stops": [
                {"stop_id": stops[0], "estimated_minutes_from_start": 30},
                {"stop_id": stops[1], "estimated_minutes_from_start": 10},
            ],
        },
    )

    assert response.status_code == 422


def test_routes_reject_anonymous_writes(client, api_url: str):
    for method, path, body in (
        ("post", f"{api_url}/routes", {"name": "X", "code": "X1"}),
        ("patch", f"{api_url}/routes/{uuid4()}", {"name": "X"}),
        ("put", f"{api_url}/routes/{uuid4()}/stops", {"stops": []}),
    ):
        response = getattr(client, method)(path, json=body)
        assert response.status_code == 401, path


def test_routes_reject_commuter_writes(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.COMMUTER)

    response = client.post(
        f"{api_url}/routes", headers=headers, json={"name": "X", "code": "X1"}
    )

    assert response.status_code == 403


def test_routes_reject_operator_writes(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.OPERATOR)

    response = client.post(
        f"{api_url}/routes", headers=headers, json={"name": "X", "code": "X1"}
    )

    assert response.status_code == 403


def test_routes_reject_invalid_token(client, api_url: str):
    response = client.post(
        f"{api_url}/routes",
        headers={"Authorization": "Bearer not-a-token"},
        json={"name": "X", "code": "X1"},
    )

    assert response.status_code == 401


# --- Update -----------------------------------------------------------------


def test_patch_route_updates_only_sent_fields(
    client, auth_headers, db_session: Session, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(client, headers, api_url, code="KEEP-1")

    response = client.patch(
        f"{api_url}/routes/{route_id}",
        headers=headers,
        json={"name": "Renamed"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "Renamed"
    assert data["code"] == "KEEP-1"  # untouched
    # `updated_at` moves whenever the row changes.
    assert data["updated_at"] >= data["created_at"]


def test_patch_route_activation_without_stops_conflicts(
    client, auth_headers, db_session: Session, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(client, headers, api_url, code="DRAFT-2")

    response = client.patch(
        f"{api_url}/routes/{route_id}", headers=headers, json={"is_active": True}
    )

    assert response.status_code == 409
    assert "two stops" in response.json()["detail"]
    # Still a draft in the database.
    assert db_session.get(Route, route_id).is_active is False


def test_patch_route_activation_after_stops_succeeds(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(client, headers, api_url, code="DRAFT-3")
    stops = _create_stops(client, headers, api_url)
    client.put(
        f"{api_url}/routes/{route_id}/stops",
        headers=headers,
        json={"stops": [{"stop_id": stop_id} for stop_id in stops]},
    )

    response = client.patch(
        f"{api_url}/routes/{route_id}", headers=headers, json={"is_active": True}
    )

    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is True


def test_patch_route_empty_body_rejected(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(client, headers, api_url, code="EMPTY-1")

    response = client.patch(f"{api_url}/routes/{route_id}", headers=headers, json={})

    assert response.status_code == 422


def test_patch_route_rejects_duplicate_code(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _create_route(client, headers, api_url, code="TAKEN-1")
    other = _create_route(client, headers, api_url, code="FREE-1")

    response = client.patch(
        f"{api_url}/routes/{other}", headers=headers, json={"code": "taken-1"}
    )

    assert response.status_code == 409


def test_patch_route_rejects_null_name(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(client, headers, api_url, code="NULL-1")

    response = client.patch(
        f"{api_url}/routes/{route_id}", headers=headers, json={"name": None}
    )

    assert response.status_code == 422


def test_patch_route_unknown_returns_404(client, auth_headers, api_url: str):
    response = client.patch(
        f"{api_url}/routes/{uuid4()}",
        headers=auth_headers(role=UserRole.MANAGEMENT),
        json={"name": "Nowhere"},
    )

    assert response.status_code == 404


def test_patch_route_requires_management(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(client, headers, api_url, code="GUARD-1")

    for role in (UserRole.COMMUTER, UserRole.OPERATOR):
        response = client.patch(
            f"{api_url}/routes/{route_id}",
            headers=auth_headers(role=role),
            json={"name": "Not allowed"},
        )
        assert response.status_code == 403, role

    assert client.patch(
        f"{api_url}/routes/{route_id}", json={"name": "Not allowed"}
    ).status_code == 401


# --- Deletion ---------------------------------------------------------------


def test_delete_route_is_not_supported(client, auth_headers, api_url: str):
    """Routes are deactivated, never deleted (docs/05 section 3), so DELETE
    on this path is not an allowed method."""
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id = _create_route(client, headers, api_url, code="NODEL-1")

    response = client.delete(f"{api_url}/routes/{route_id}", headers=headers)

    assert response.status_code == 405
