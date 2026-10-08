"""Fare endpoint tests (docs/05-api-specification.md section 7).

Covers the public reads, the management-only configuration, the
journey-context rule (docs/02-product-requirements.md rule 6) and the
preserved fare history (rule 7).
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.user import UserRole

# A fixed future moment used by the "duplicate start" tests; far enough away
# that it never collides with the server clock.
FUTURE = "2030-05-05T00:00:00"


def _stop(client, headers, api_url: str, name: str) -> str:
    response = client.post(
        f"{api_url}/stops",
        headers=headers,
        json={"name": name, "latitude": -17.8261, "longitude": 31.0346},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _route(client, headers, api_url: str, code: str, *stop_ids: str) -> str:
    response = client.post(
        f"{api_url}/routes",
        headers=headers,
        json={
            "name": f"Line {code}",
            "code": code,
            "stops": [{"stop_id": stop_id} for stop_id in stop_ids],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


def _journey(client, headers, api_url: str, code: str = "FARE-1") -> tuple[str, str, str]:
    """Create a route with two stops; returns (route_id, origin, destination)."""
    origin = _stop(client, headers, api_url, f"{code} Origin")
    destination = _stop(client, headers, api_url, f"{code} Destination")
    route_id = _route(client, headers, api_url, code, origin, destination)
    return route_id, origin, destination


def _payload(route_id: str, origin: str, destination: str, **overrides) -> dict:
    payload = {
        "route_id": route_id,
        "origin_stop_id": origin,
        "destination_stop_id": destination,
        "amount": "2.50",
    }
    payload.update(overrides)
    return payload


def _create(client, headers, api_url: str, route_id: str, origin: str, destination: str, **overrides) -> dict:
    response = client.post(
        f"{api_url}/fares",
        headers=headers,
        json=_payload(route_id, origin, destination, **overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


# --- Create -----------------------------------------------------------------


def test_management_creates_fare(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)

    response = client.post(
        f"{api_url}/fares",
        headers=headers,
        json=_payload(route_id, origin, destination),
    )

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["route_id"] == route_id
    assert data["origin_stop_id"] == origin
    assert data["destination_stop_id"] == destination
    # Money comes back as a decimal string, never a float (docs/10 section 4).
    assert data["amount"] == "2.50"
    assert data["currency"] == "USD"  # default currency
    assert data["is_active"] is True
    assert data["effective_to"] is None  # open ended until superseded
    assert data["effective_from"]
    assert data["created_at"]
    assert response.json()["message"] == "Fare created successfully"


def test_create_fare_normalizes_currency(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)

    data = _create(
        client, headers, api_url, route_id, origin, destination, currency="  zwl "
    )

    assert data["currency"] == "ZWL"


def test_create_fare_rejects_invalid_currency(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)

    for bad in ("U5D", "US", "EURO"):
        response = client.post(
            f"{api_url}/fares",
            headers=headers,
            json=_payload(route_id, origin, destination, currency=bad),
        )
        assert response.status_code == 422, (bad, response.text)


def test_create_fare_accepts_explicit_effective_from(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)

    data = _create(
        client,
        headers,
        api_url,
        route_id,
        origin,
        destination,
        effective_from="2030-01-02T03:04:05",  # no offset -> stored as UTC
    )

    # Same instant as sent, read back with the session's offset.
    assert datetime.fromisoformat(data["effective_from"]) == datetime(
        2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc
    )


def test_create_fare_rejects_explicit_null_effective_from(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)

    response = client.post(
        f"{api_url}/fares",
        headers=headers,
        json=_payload(route_id, origin, destination, effective_from=None),
    )

    assert response.status_code == 422


def test_create_fare_rejects_non_positive_amount(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)

    for amount in ("0", "-1.00"):
        response = client.post(
            f"{api_url}/fares",
            headers=headers,
            json=_payload(route_id, origin, destination, amount=amount),
        )
        assert response.status_code == 422, (amount, response.text)


def test_create_fare_rejects_more_than_two_decimals(client, auth_headers, api_url: str):
    """Money must never be silently rounded (docs/04 section 14)."""
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)

    response = client.post(
        f"{api_url}/fares",
        headers=headers,
        json=_payload(route_id, origin, destination, amount="1.505"),
    )

    assert response.status_code == 422


def test_create_fare_rejects_extra_fields(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)

    response = client.post(
        f"{api_url}/fares",
        headers=headers,
        json={**_payload(route_id, origin, destination), "note": "promo"},
    )

    assert response.status_code == 422


def test_create_fare_requires_two_different_stops(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, _ = _journey(client, headers, api_url)

    response = client.post(
        f"{api_url}/fares",
        headers=headers,
        json=_payload(route_id, origin, origin),
    )

    assert response.status_code == 422


def test_create_fare_requires_stops_on_the_route(client, auth_headers, api_url: str):
    """Rule 6: a fare applies to a defined route/journey context."""
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url, "FARE-1")
    other_route_id, other_origin, _ = _journey(client, headers, api_url, "FARE-2")

    # A stop that belongs to a different route cannot price this journey.
    response = client.post(
        f"{api_url}/fares",
        headers=headers,
        json=_payload(route_id, origin, other_origin),
    )
    assert response.status_code == 422, response.text

    # Neither can a route that does not contain the stops at all.
    response = client.post(
        f"{api_url}/fares",
        headers=headers,
        json=_payload(other_route_id, origin, destination),
    )
    assert response.status_code == 422, response.text


def test_create_fare_unknown_route_returns_404(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _, origin, destination = _journey(client, headers, api_url)

    response = client.post(
        f"{api_url}/fares",
        headers=headers,
        json=_payload(str(uuid4()), origin, destination),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Route not found"


def test_create_fare_unknown_stop_returns_404(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, _ = _journey(client, headers, api_url)

    response = client.post(
        f"{api_url}/fares",
        headers=headers,
        json=_payload(route_id, origin, str(uuid4())),
    )

    assert response.status_code == 404
    assert response.json()["detail"].startswith("Stop not found")


def test_fares_reject_anonymous_and_wrong_roles_on_write(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    payload = _payload(route_id, origin, destination)

    assert client.post(f"{api_url}/fares", json=payload).status_code == 401

    for role in (UserRole.COMMUTER, UserRole.OPERATOR):
        response = client.post(
            f"{api_url}/fares", headers=auth_headers(role=role), json=payload
        )
        assert response.status_code == 403, role

    fare_id = _create(client, headers, api_url, route_id, origin, destination)["id"]
    assert client.patch(f"{api_url}/fares/{fare_id}", json={"is_active": False}).status_code == 401
    for role in (UserRole.COMMUTER, UserRole.OPERATOR):
        response = client.patch(
            f"{api_url}/fares/{fare_id}",
            headers=auth_headers(role=role),
            json={"is_active": False},
        )
        assert response.status_code == 403, role


# --- Read -------------------------------------------------------------------


def test_list_fares_is_public(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    fare = _create(client, headers, api_url, route_id, origin, destination)

    response = client.get(f"{api_url}/fares")  # no token

    assert response.status_code == 200
    data = response.json()["data"]
    assert [item["id"] for item in data] == [fare["id"]]
    assert data[0]["amount"] == "2.50"


def test_list_fares_is_empty_when_nothing_is_configured(client, api_url: str):
    response = client.get(f"{api_url}/fares")

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_list_fares_filters_by_route_and_stops(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route1, origin1, destination1 = _journey(client, headers, api_url, "FARE-1")
    route2, origin2, destination2 = _journey(client, headers, api_url, "FARE-2")
    fare1 = _create(client, headers, api_url, route1, origin1, destination1)
    fare2 = _create(client, headers, api_url, route2, origin2, destination2)

    def ids(params: dict) -> list[str]:
        response = client.get(f"{api_url}/fares", params=params)
        assert response.status_code == 200, response.text
        return [item["id"] for item in response.json()["data"]]

    assert ids({"route_id": route1}) == [fare1["id"]]
    assert ids({"origin_stop_id": origin2}) == [fare2["id"]]
    assert ids({"destination_stop_id": destination1}) == [fare1["id"]]
    assert ids({"route_id": route1, "origin_stop_id": origin2}) == []


def test_list_fares_hides_expired_fares_unless_history_is_asked_for(
    client, auth_headers, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    past = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    fare = _create(
        client,
        headers,
        api_url,
        route_id,
        origin,
        destination,
        effective_from=past,
    )

    # Close the window in the past: the fare has run out.
    ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    response = client.patch(
        f"{api_url}/fares/{fare['id']}",
        headers=headers,
        json={"effective_to": ten_days_ago},
    )
    assert response.status_code == 200, response.text

    assert client.get(f"{api_url}/fares").json()["data"] == []

    history = client.get(f"{api_url}/fares", params={"include_history": True}).json()["data"]
    assert [item["id"] for item in history] == [fare["id"]]
    assert history[0]["effective_to"] is not None


# --- Superseding (history is preserved, never overwritten) -------------------


def test_new_fare_supersedes_the_previous_price(client, auth_headers, api_url: str):
    """Rule 7: the old price stays in the table with its window closed."""
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    old = _create(client, headers, api_url, route_id, origin, destination)
    assert old["effective_to"] is None  # open ended when it was written

    new = _create(client, headers, api_url, route_id, origin, destination)
    assert new["id"] != old["id"]

    history = client.get(
        f"{api_url}/fares", params={"route_id": route_id, "include_history": True}
    ).json()["data"]
    assert [item["id"] for item in history] == [new["id"], old["id"]]

    old_row = next(item for item in history if item["id"] == old["id"])
    new_row = next(item for item in history if item["id"] == new["id"])
    # The superseded fare keeps its amount and is closed exactly when the new
    # one starts, so the two windows meet without overlapping.
    assert old_row["amount"] == "2.50"
    assert old_row["effective_to"] == new_row["effective_from"]
    assert new_row["effective_to"] is None

    current = client.get(f"{api_url}/fares", params={"route_id": route_id}).json()["data"]
    assert [item["id"] for item in current] == [new["id"]]


def test_create_fare_with_identical_start_time_conflicts(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    _create(
        client, headers, api_url, route_id, origin, destination, effective_from=FUTURE
    )

    response = client.post(
        f"{api_url}/fares",
        headers=headers,
        json=_payload(route_id, origin, destination, effective_from=FUTURE),
    )

    assert response.status_code == 409


def test_new_fare_is_capped_by_a_later_scheduled_fare(client, auth_headers, api_url: str):
    """A price scheduled for later must not swallow the one starting sooner."""
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    later = datetime.now(timezone.utc) + timedelta(days=3)
    sooner = datetime.now(timezone.utc) + timedelta(days=1)

    scheduled = _create(
        client,
        headers,
        api_url,
        route_id,
        origin,
        destination,
        effective_from=later.isoformat(),
    )
    inserted = _create(
        client,
        headers,
        api_url,
        route_id,
        origin,
        destination,
        effective_from=sooner.isoformat(),
    )

    # The inserted fare stops exactly where the scheduled one begins.
    assert inserted["effective_to"] == scheduled["effective_from"]

    history = client.get(
        f"{api_url}/fares", params={"route_id": route_id, "include_history": True}
    ).json()["data"]
    scheduled_row = next(item for item in history if item["id"] == scheduled["id"])
    inserted_row = next(item for item in history if item["id"] == inserted["id"])
    assert inserted_row["effective_to"] == scheduled_row["effective_from"]
    assert scheduled_row["effective_to"] is None  # untouched by the insert


# --- Search -----------------------------------------------------------------


def test_search_is_public_and_returns_the_current_fare(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    fare = _create(client, headers, api_url, route_id, origin, destination)

    response = client.get(
        f"{api_url}/fares/search",
        params={"origin_stop_id": origin, "destination_stop_id": destination},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert [item["id"] for item in data] == [fare["id"]]
    assert data[0]["amount"] == "2.50"


def test_search_requires_both_stops(client, api_url: str):
    assert client.get(f"{api_url}/fares/search").status_code == 422
    assert (
        client.get(
            f"{api_url}/fares/search", params={"origin_stop_id": str(uuid4())}
        ).status_code
        == 422
    )


def test_search_returns_empty_list_when_no_fare_is_configured(
    client, auth_headers, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _, origin, destination = _journey(client, headers, api_url)

    response = client.get(
        f"{api_url}/fares/search",
        params={"origin_stop_id": origin, "destination_stop_id": destination},
    )

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_search_rejects_unknown_or_equal_stops(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    _, origin, destination = _journey(client, headers, api_url)

    # Unknown ids are a mistyped query, not "no fares".
    assert (
        client.get(
            f"{api_url}/fares/search",
            params={"origin_stop_id": str(uuid4()), "destination_stop_id": destination},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"{api_url}/fares/search",
            params={"origin_stop_id": origin, "destination_stop_id": str(uuid4())},
        ).status_code
        == 404
    )
    # Origin and destination must differ.
    assert (
        client.get(
            f"{api_url}/fares/search",
            params={"origin_stop_id": origin, "destination_stop_id": origin},
        ).status_code
        == 422
    )


def test_search_can_be_restricted_to_one_route(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route1, origin, destination = _journey(client, headers, api_url, "FARE-1")
    other_route, other_origin, other_destination = _journey(
        client, headers, api_url, "FARE-2"
    )
    _create(client, headers, api_url, route1, origin, destination)
    _create(
        client, headers, api_url, other_route, other_origin, other_destination
    )

    def search(params: dict) -> list[dict]:
        response = client.get(f"{api_url}/fares/search", params=params)
        assert response.status_code == 200, response.text
        return response.json()["data"]

    base = {"origin_stop_id": origin, "destination_stop_id": destination}
    assert len(search(base)) == 1
    assert search({**base, "route_id": route1}) != []
    assert search({**base, "route_id": other_route}) == []
    assert (
        client.get(
            f"{api_url}/fares/search", params={**base, "route_id": str(uuid4())}
        ).status_code
        == 404
    )


def test_search_returns_only_the_current_fare(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    _create(client, headers, api_url, route_id, origin, destination, amount="2.50")
    replacement = _create(
        client, headers, api_url, route_id, origin, destination, amount="3.00"
    )

    response = client.get(
        f"{api_url}/fares/search",
        params={"origin_stop_id": origin, "destination_stop_id": destination},
    )

    data = response.json()["data"]
    assert [item["id"] for item in data] == [replacement["id"]]
    assert data[0]["amount"] == "3.00"


def test_fares_are_never_deleted_or_read_by_id(client, auth_headers, api_url: str):
    """Fares are deactivated, not removed, and read through list/search."""
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    fare = _create(client, headers, api_url, route_id, origin, destination)

    assert (
        client.delete(f"{api_url}/fares/{fare['id']}", headers=headers).status_code
        == 405
    )
    # docs/05 section 7 defines no per-fare read either.
    assert client.get(f"{api_url}/fares/{fare['id']}").status_code == 405


# --- Update (lifecycle only) -------------------------------------------------


def test_patch_fare_deactivates_and_reactivates(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    fare = _create(client, headers, api_url, route_id, origin, destination)

    response = client.patch(
        f"{api_url}/fares/{fare['id']}",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False
    assert response.json()["message"] == "Fare updated successfully"

    # Deactivated – gone from the commuter view, still in the history.
    assert client.get(f"{api_url}/fares").json()["data"] == []
    history = client.get(
        f"{api_url}/fares", params={"include_history": True}
    ).json()["data"]
    assert [item["id"] for item in history] == [fare["id"]]
    assert history[0]["is_active"] is False

    # Reactivating puts it back to work.
    response = client.patch(
        f"{api_url}/fares/{fare['id']}", headers=headers, json={"is_active": True}
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is True
    assert [item["id"] for item in client.get(f"{api_url}/fares").json()["data"]] == [
        fare["id"]
    ]


def test_patch_fare_reopens_an_expired_window(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    past = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    fare = _create(
        client, headers, api_url, route_id, origin, destination, effective_from=past
    )
    ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    client.patch(
        f"{api_url}/fares/{fare['id']}", headers=headers, json={"effective_to": ten_days_ago}
    )
    assert client.get(f"{api_url}/fares").json()["data"] == []

    # No newer fare exists, so the window can be opened again.
    response = client.patch(
        f"{api_url}/fares/{fare['id']}", headers=headers, json={"effective_to": None}
    )

    assert response.status_code == 200
    assert response.json()["data"]["effective_to"] is None
    assert [item["id"] for item in client.get(f"{api_url}/fares").json()["data"]] == [
        fare["id"]
    ]


def test_patch_unknown_fare_returns_404(client, auth_headers, api_url: str):
    response = client.patch(
        f"{api_url}/fares/{uuid4()}",
        headers=auth_headers(role=UserRole.MANAGEMENT),
        json={"is_active": False},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Fare not found"


def test_patch_fare_empty_body_rejected(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    fare = _create(client, headers, api_url, route_id, origin, destination)

    response = client.patch(f"{api_url}/fares/{fare['id']}", headers=headers, json={})

    assert response.status_code == 422


def test_patch_fare_cannot_change_the_price(client, auth_headers, api_url: str):
    """The price is only ever changed by POSTing a new fare (rule 7)."""
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    fare = _create(client, headers, api_url, route_id, origin, destination)

    for body in (
        {"amount": "9.99"},
        {"currency": "EUR"},
        {"route_id": str(uuid4())},
        {"effective_from": FUTURE},
    ):
        response = client.patch(f"{api_url}/fares/{fare['id']}", headers=headers, json=body)
        assert response.status_code == 422, (body, response.text)

    # The stored fare is untouched.
    history = client.get(
        f"{api_url}/fares", params={"include_history": True}
    ).json()["data"]
    assert history[0]["amount"] == "2.50"


def test_patch_fare_rejects_window_that_ends_before_it_starts(
    client, auth_headers, api_url: str
):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    past = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    fare = _create(
        client, headers, api_url, route_id, origin, destination, effective_from=past
    )

    response = client.patch(
        f"{api_url}/fares/{fare['id']}",
        headers=headers,
        json={"effective_to": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()},
    )

    assert response.status_code == 422


def test_patch_fare_cannot_reopen_over_a_newer_fare(client, auth_headers, api_url: str):
    """Windows of one journey never overlap, before or after an update."""
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    old = _create(client, headers, api_url, route_id, origin, destination)
    new = _create(client, headers, api_url, route_id, origin, destination)

    response = client.patch(
        f"{api_url}/fares/{old['id']}", headers=headers, json={"effective_to": None}
    )

    assert response.status_code == 409
    assert "already covers" in response.json()["detail"]

    # The refused update changed nothing: the old fare is still closed at the
    # moment the new one starts, and the new one is still open ended.
    history = client.get(
        f"{api_url}/fares", params={"route_id": route_id, "include_history": True}
    ).json()["data"]
    old_row = next(item for item in history if item["id"] == old["id"])
    new_row = next(item for item in history if item["id"] == new["id"])
    assert old_row["effective_to"] == new_row["effective_from"]
    assert new_row["effective_to"] is None


def test_patch_fare_cannot_reactivate_over_a_newer_fare(client, auth_headers, api_url: str):
    headers = auth_headers(role=UserRole.MANAGEMENT)
    route_id, origin, destination = _journey(client, headers, api_url)
    old = _create(client, headers, api_url, route_id, origin, destination)
    client.patch(
        f"{api_url}/fares/{old['id']}", headers=headers, json={"is_active": False}
    )
    _create(client, headers, api_url, route_id, origin, destination)

    response = client.patch(
        f"{api_url}/fares/{old['id']}", headers=headers, json={"is_active": True}
    )

    assert response.status_code == 409
