"""Analytics tests (Phase 7)."""
from app.models.user import UserRole


def _stop(client, headers, api_url: str, name: str):
    r = client.post(f"{api_url}/stops", headers=headers, json={"name": name, "latitude": -17.825, "longitude": 31.033})
    assert r.status_code == 201
    return r.json()["data"]["id"]


def _route(client, headers, api_url: str, code: str, *stop_ids):
    r = client.post(f"{api_url}/routes", headers=headers, json={"name": f"L{code}", "code": code, "stops": [{"stop_id": s} for s in stop_ids]})
    assert r.status_code == 201
    return r.json()["data"]["id"]


def test_analytics_requires_management(client, auth_headers, api_url: str):
    commuter = auth_headers(role=UserRole.COMMUTER)
    r = client.get(f"{api_url}/analytics/overview", headers=commuter)
    assert r.status_code == 403
    r = client.get(f"{api_url}/analytics/overview")
    assert r.status_code == 401


def test_analytics_overview_empty(client, auth_headers, api_url: str):
    mgmt = auth_headers(role=UserRole.MANAGEMENT)
    r = client.get(f"{api_url}/analytics/overview", headers=mgmt)
    assert r.status_code == 200
    assert "total_searches" in r.json()["data"]


def test_analytics_routes_and_destinations(client, auth_headers, api_url: str, db_session):
    mgmt = auth_headers(role=UserRole.MANAGEMENT)
    s1 = _stop(client, mgmt, api_url, "A7")
    s2 = _stop(client, mgmt, api_url, "B7")
    route = _route(client, mgmt, api_url, "R7", s1, s2)
    from app.models.journey_search import JourneySearch
    db_session.add(JourneySearch(origin_stop_id=s1, destination_stop_id=s2, route_id=route))
    db_session.commit()
    r = client.get(f"{api_url}/analytics/routes", headers=mgmt)
    assert r.status_code == 200
    r = client.get(f"{api_url}/analytics/destinations", headers=mgmt)
    assert r.status_code == 200
