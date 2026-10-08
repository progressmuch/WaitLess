"""Commuter journey discovery tests (Phase 5)."""

from app.models.user import UserRole


def _stop(client, headers, api_url: str, name: str):
    r = client.post(f"{api_url}/stops", headers=headers, json={"name": name, "latitude": -17.825, "longitude": 31.033})
    assert r.status_code == 201
    return r.json()["data"]["id"]


def _route(client, headers, api_url: str, code: str, *stop_ids):
    r = client.post(f"{api_url}/routes", headers=headers, json={"name": f"L{code}", "code": code, "stops": [{"stop_id": s} for s in stop_ids]})
    assert r.status_code == 201
    return r.json()["data"]["id"]


def _setup_operator(client, headers, api_url: str, suffix: str):
    s1 = _stop(client, headers, api_url, f"A{suffix}")
    s2 = _stop(client, headers, api_url, f"B{suffix}")
    route = _route(client, headers, api_url, f"R{suffix}", s1, s2)
    bus = client.post(f"{api_url}/buses", headers=headers, json={
        "registration_number": f"BUS{suffix}", "fleet_number": f"F{suffix}", "capacity": 40, "route_id": route
    }).json()["data"]["id"]
    op = client.post(f"{api_url}/auth/users", headers=headers, json={
        "full_name": "Op", "email": f"op{suffix}@ex.com", "password": "Password123!", "role": UserRole.OPERATOR.value
    }).json()["data"]["id"]
    client.post(f"{api_url}/operators/{op}/assignments", headers=headers, json={"bus_id": bus})
    return op, bus, route, s1, s2


def _token_for(client, api_url: str, email: str):
    r = client.post(f"{api_url}/auth/login", json={"email": email, "password": "Password123!"})
    assert r.status_code == 200
    return r.json()["data"]["access_token"]


def test_journey_search_returns_empty_if_no_active_trips(client, auth_headers, api_url: str):
    mgmt = auth_headers(role=UserRole.MANAGEMENT)
    s1 = _stop(client, mgmt, api_url, "J1A")
    s2 = _stop(client, mgmt, api_url, "J1B")
    r = client.get(f"{api_url}/journeys/search", params={"origin_stop_id": s1, "destination_stop_id": s2})
    assert r.status_code == 200
    assert r.json()["data"]["results"] == []


def test_journey_search_with_active_trip(client, auth_headers, api_url: str):
    mgmt = auth_headers(role=UserRole.MANAGEMENT)
    op_id, bus_id, route_id, s1, s2 = _setup_operator(client, mgmt, api_url, "j2")
    op_token = _token_for(client, api_url, "opj2@ex.com")
    client.post(f"{api_url}/trips/start", headers={"Authorization": f"Bearer {op_token}"}, json={"bus_id": bus_id, "route_id": route_id})
    r = client.get(f"{api_url}/journeys/search", params={"origin_stop_id": s1, "destination_stop_id": s2})
    assert r.status_code == 200
    data = r.json()["data"]["results"]
    assert len(data) == 1
    assert "route" in data[0]
    assert "fare" in data[0] or data[0]["fare"] is None
    assert "active_bus" in data[0]
    assert "latest_location" in data[0]
    assert "eta_minutes" in data[0] or data[0]["eta_minutes"] is None
