"""Stop endpoint tests (docs/05-api-specification.md section 4).

Covers the public read, management-only writes, coordinate validation and the
"deactivate instead of delete" rule for stops.
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.route import Route
from app.models.user import UserRole


def _payload(name: str = "Market Square", latitude: float = -17.8252, longitude: float = 31.0335) -> dict:
    return {"name": name, "latitude": latitude, "longitude": longitude}


def _create(client, headers, api_url: str, **overrides) -> dict:
    response = client.post(
        f"{api_url}/stops", headers=headers, json=_payload(**overrides)
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --- Create -----------------------------------------------------------------


def test_management_creates_stop(client, auth_headers, api_url: str):
    response = client.post(
        f"{api_url}/stops",
        headers=auth_headers(role=UserRole.MANAGEMENT),
        json=_payload(name="  Junction  "),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Junction"  # trimmed
    assert data["latitude"] == -17.8252
    assert data["longitude"] == 31.0335
    assert data["is_active"] is True
    assert response.json()["message"] == "Stop created successfully"


def test_create_stop_rejects_out_of_range_coordinates(
    client, auth_headers, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)

    assert (
        client.post(
            f"{api_url}/stops", headers=headers, json=_payload(latitude=91)
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{api_url}/stops", headers=headers, json=_payload(longitude=-181)
        ).status_code
        == 422
    )


def test_create_stop_rejects_empty_name(client, auth_headers, api_url: str):
    response = client.post(
        f"{api_url}/stops",
        headers=auth_headers(role=UserRole.MANAGEMENT),
        json=_payload(name="   "),
    )

    assert response.status_code == 422


def test_create_stop_rejects_extra_fields(client, auth_headers, api_url: str):
    response = client.post(
        f"{api_url}/stops",
        headers=auth_headers(role=UserRole.MANAGEMENT),
        json={**_payload(), "route_id": str(uuid4())},
    )

    assert response.status_code == 422


def test_stops_reject_anonymous_and_wrong_roles(client, auth_headers, api_url: str):
    assert client.post(f"{api_url}/stops", json=_payload()).status_code == 401

    for role in (UserRole.COMMUTER, UserRole.OPERATOR):
        response = client.post(
            f"{api_url}/stops", headers=auth_headers(role=role), json=_payload()
        )
        assert response.status_code == 403, role


# --- Read -------------------------------------------------------------------


def test_list_stops_is_public(client, auth_headers, api_url: str):
    _create(client, auth_headers(role=UserRole.MANAGEMENT), api_url)

    response = client.get(f"{api_url}/stops")  # no token

    assert response.status_code == 200
    data = response.json()["data"]
    assert [stop["name"] for stop in data] == ["Market Square"]


def test_list_stops_hides_deactivated_stops(
    client, auth_headers, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    stop = _create(client, headers, api_url)

    client.patch(
        f"{api_url}/stops/{stop['id']}", headers=headers, json={"is_active": False}
    )

    assert client.get(f"{api_url}/stops").json()["data"] == []
    # Management can still find it explicitly.
    drafts = client.get(f"{api_url}/stops", params={"is_active": False}).json()["data"]
    assert [item["id"] for item in drafts] == [stop["id"]]


# --- Update -----------------------------------------------------------------


def test_patch_stop_updates_coordinates(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    stop = _create(client, headers, api_url)

    response = client.patch(
        f"{api_url}/stops/{stop['id']}",
        headers=headers,
        json={"latitude": -18.5, "name": "Renamed Square"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["latitude"] == -18.5
    assert data["name"] == "Renamed Square"
    assert data["longitude"] == stop["longitude"]  # untouched


def test_patch_stop_empty_body_rejected(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    stop = _create(client, headers, api_url)

    response = client.patch(f"{api_url}/stops/{stop['id']}", headers=headers, json={})

    assert response.status_code == 422


def test_patch_stop_null_name_rejected(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    stop = _create(client, headers, api_url)

    response = client.patch(
        f"{api_url}/stops/{stop['id']}", headers=headers, json={"name": None}
    )

    assert response.status_code == 422


def test_patch_unknown_stop_returns_404(client, auth_headers, api_url: str):
    response = client.patch(
        f"{api_url}/stops/{uuid4()}",
        headers=auth_headers(role=UserRole.MANAGEMENT),
        json={"name": "Nowhere"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Stop not found"


# --- Deactivation instead of deletion ---------------------------------------


def test_deactivated_stop_stays_in_route_detail(
    client, auth_headers, db_session: Session, api_url: str
):
    """A stop is deactivated, never removed: routes that use it keep working."""
    headers = auth_headers(role=UserRole.MANAGEMENT)
    first = _create(client, headers, api_url, name="First")
    second = _create(client, headers, api_url, name="Second")
    route = client.post(
        f"{api_url}/routes",
        headers=headers,
        json={
            "name": "Depot Line",
            "code": "DPT-1",
            "stops": [{"stop_id": first["id"]}, {"stop_id": second["id"]}],
        },
    ).json()["data"]

    client.patch(
        f"{api_url}/stops/{first['id']}", headers=headers, json={"is_active": False}
    )

    # Still listed on the route, now flagged as inactive...
    stops = client.get(f"{api_url}/routes/{route['id']}").json()["data"]["stops"]
    assert len(stops) == 2
    assert stops[0]["stop"]["is_active"] is False
    # ...but gone from the public stop list.
    assert [item["id"] for item in client.get(f"{api_url}/stops").json()["data"]] == [
        second["id"]
    ]
    # And still present in the database.
    assert db_session.get(Route, route["id"]) is not None
