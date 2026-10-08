"""Trip and location endpoint tests (Phase 4)."""

from uuid import uuid4

from app.models.user import UserRole


def _stop(client, headers, api_url: str, name: str) -> str:
    r = client.post(f"{api_url}/stops", headers=headers, json={"name": name, "latitude": -17.825, "longitude": 31.033})
    assert r.status_code == 201
    return r.json()["data"]["id"]


def _route(client, headers, api_url: str, code: str, *stop_ids: str) -> str:
    r = client.post(f"{api_url}/routes", headers=headers, json={"name": f"L{code}", "code": code, "stops": [{"stop_id": s} for s in stop_ids]})
    assert r.status_code == 201
    return r.json()["data"]["id"]


def _setup_operator(client, headers, api_url: str, suffix: str):
    s1 = _stop(client, headers, api_url, f"A{suffix}")
    s2 = _stop(client, headers, api_url, f"B{suffix}")
    route = _route(client, headers, api_url, f"R{suffix}", s1, s2)
    bus = client.post(f"{api_url}/buses", headers=headers, json={
        "registration_number": f"BUS {suffix}", "fleet_number": f"F {suffix}", "capacity": 40, "route_id": route
    }).json()["data"]["id"]
    op = client.post(f"{api_url}/auth/users", headers=headers, json={
        "full_name": "Op", "email": f"op{suffix}@example.com", "password": "Password123!", "role": UserRole.OPERATOR.value
    }).json()["data"]["id"]
    client.post(f"{api_url}/operators/{op}/assignments", headers=headers, json={"bus_id": bus})
    return op, bus, route


def _token_for(client, api_url: str, email: str, pwd: str = "Password123!"):
    r = client.post(f"{api_url}/auth/login", json={"email": email, "password": pwd})
    assert r.status_code == 200
    return r.json()["data"]["access_token"]


def test_start_trip_requires_operator(client, auth_headers, api_url: str):
    mgmt = auth_headers(role=UserRole.MANAGEMENT)
    op_id, bus_id, route_id = _setup_operator(client, mgmt, api_url, "s1")
    commuter = auth_headers(role=UserRole.COMMUTER)
    assert client.post(f"{api_url}/trips/start", headers=commuter, json={"bus_id": bus_id, "route_id": route_id}).status_code == 403
    assert client.post(f"{api_url}/trips/start", json={"bus_id": bus_id, "route_id": route_id}).status_code == 401


def test_operator_can_start_and_end_trip(client, auth_headers, api_url: str):
    mgmt = auth_headers(role=UserRole.MANAGEMENT)
    suffix = "s2"
    op_id, bus_id, route_id = _setup_operator(client, mgmt, api_url, suffix)
    op_token = _token_for(client, api_url, f"op{suffix}@example.com")
    r = client.post(f"{api_url}/trips/start", headers={"Authorization": f"Bearer {op_token}"}, json={"bus_id": bus_id, "route_id": route_id})
    assert r.status_code == 201
    trip_id = r.json()["data"]["id"]
    assert r.json()["data"]["status"] == "ACTIVE"
    r2 = client.post(f"{api_url}/trips/{trip_id}/end", headers={"Authorization": f"Bearer {op_token}"})
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "COMPLETED"
    assert r2.json()["data"]["ended_at"] is not None


def test_only_assigned_operator_can_start_trip(client, auth_headers, api_url: str):
    mgmt = auth_headers(role=UserRole.MANAGEMENT)
    suffix = "t1"
    op_id, bus_id, route_id = _setup_operator(client, mgmt, api_url, suffix)
    other = client.post(f"{api_url}/auth/users", headers=mgmt, json={"full_name": "O", "email": f"{suffix}other@example.com", "password": "Password123!", "role": "OPERATOR"}).json()["data"]["id"]
    s1 = _stop(client, mgmt, api_url, f"{suffix}c1")
    s2 = _stop(client, mgmt, api_url, f"{suffix}c2")
    route2 = _route(client, mgmt, api_url, f"{suffix}R2", s1, s2)
    bus2 = client.post(f"{api_url}/buses", headers=mgmt, json={"registration_number": f"{suffix}B2", "fleet_number": f"{suffix}F2", "capacity": 30, "route_id": route2}).json()["data"]["id"]
    client.post(f"{api_url}/operators/{other}/assignments", headers=mgmt, json={"bus_id": bus2})
    other_token = _token_for(client, api_url, f"{suffix}other@example.com")
    r = client.post(f"{api_url}/trips/start", headers={"Authorization": f"Bearer {other_token}"}, json={"bus_id": bus_id, "route_id": route_id})
    assert r.status_code == 403


def test_bus_cannot_have_two_active_trips(client, auth_headers, api_url: str):
    mgmt = auth_headers(role=UserRole.MANAGEMENT)
    suffix = "t2"
    op_id, bus_id, route_id = _setup_operator(client, mgmt, api_url, suffix)
    op_token = _token_for(client, api_url, f"op{suffix}@example.com")
    client.post(f"{api_url}/trips/start", headers={"Authorization": f"Bearer {op_token}"}, json={"bus_id": bus_id, "route_id": route_id})
    r = client.post(f"{api_url}/trips/start", headers={"Authorization": f"Bearer {op_token}"}, json={"bus_id": bus_id, "route_id": route_id})
    assert r.status_code == 409


def test_operator_cannot_end_another_operators_trip(client, auth_headers, api_url: str):
    mgmt = auth_headers(role=UserRole.MANAGEMENT)
    suffix = "t3"
    op_id, bus_id, route_id = _setup_operator(client, mgmt, api_url, suffix)
    op_token = _token_for(client, api_url, f"op{suffix}@example.com")
    r = client.post(f"{api_url}/trips/start", headers={"Authorization": f"Bearer {op_token}"}, json={"bus_id": bus_id, "route_id": route_id})
    trip_id = r.json()["data"]["id"]
    other = auth_headers(role=UserRole.OPERATOR)
    r2 = client.post(f"{api_url}/trips/{trip_id}/end", headers=other)
    assert r2.status_code == 403