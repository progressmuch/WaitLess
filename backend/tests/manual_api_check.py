"""Manual end-to-end verification of the API over real HTTP (Phases 1 to 3).

Starts nothing itself: run the app with
    python -m uvicorn app.main:app --port 8010
in another shell, then run this script from the `backend/` directory (the
application loads `.env` relative to the working directory):
    python tests/manual_api_check.py

It uses the development database - the accounts, stops and routes it creates
stay behind, all under a unique suffix - and prints a PASS/FAIL line per check.
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

# Make `app` importable no matter where the script is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE = "http://127.0.0.1:8010"
API = f"{BASE}/api/v1"

# Unique per run so the script can be repeated without cleaning up first.
SUFFIX = uuid4().hex[:8]

results: list[tuple[bool, str]] = []


def call(method: str, path: str, body=None, token: str | None = None):
    url = path if path.startswith("http") else f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return exc.code, {"raw": raw.decode(errors="replace")}


def check(name: str, condition: bool, extra: str = "") -> None:
    results.append((condition, f"{name} {extra}".strip()))
    print(("PASS  " if condition else "FAIL  ") + f"{name} {extra}".strip())


# 1. Health
status, body = call("GET", f"{BASE}/health")
check("GET /health -> 200 ok", status == 200 and body.get("status") == "ok", str(body))

# 2. Public registration (always COMMUTER)
commuter_email = f"commuter-{SUFFIX}@example.com"
status, body = call(
    "POST",
    "/auth/register",
    {
        "full_name": "Manual Commuter",
        "email": commuter_email,
        "phone": "+263770000000",
        "password": "Password123!",
    },
)
check("POST /auth/register -> 201 COMMUTER", status == 201 and body["data"]["role"] == "COMMUTER", str(status))
check("response hides password/hash", "password" not in body.get("data", {}) and "password_hash" not in body.get("data", {}))

# 3. Registration cannot self-assign a role
status, _ = call(
    "POST",
    "/auth/register",
    {
        "full_name": "Sneaky",
        "email": f"sneaky-{SUFFIX}@example.com",
        "password": "Password123!",
        "role": "MANAGEMENT",
    },
)
check("POST /auth/register with role -> 422", status == 422, str(status))

# 4. Duplicate email -> 409
status, body = call(
    "POST",
    "/auth/register",
    {"full_name": "Dup", "email": commuter_email, "password": "Password123!"},
)
check("POST /auth/register duplicate -> 409", status == 409, str(status))

# 5. Login
status, body = call(
    "POST",
    "/auth/login",
    {"email": commuter_email, "password": "Password123!"},
)
check("POST /auth/login -> 200 token", status == 200 and bool(body["data"]["access_token"]), str(status))
commuter_token = body.get("data", {}).get("access_token", "")

# 6. Wrong password -> 401 and no user enumeration
status_wrong, body_wrong = call(
    "POST",
    "/auth/login",
    {"email": commuter_email, "password": "WrongPassword123!"},
)
status_unknown, body_unknown = call(
    "POST",
    "/auth/login",
    {"email": f"nobody-{SUFFIX}@example.com", "password": "Password123!"},
)
check(
    "POST /auth/login wrong pw + unknown email identical 401",
    status_wrong == status_unknown == 401 and body_wrong == body_unknown,
)

# 7. /auth/me requires a token
status, _ = call("GET", "/auth/me")
check("GET /auth/me without token -> 401", status == 401, str(status))

# 8. /auth/me with a token
status, body = call("GET", "/auth/me", token=commuter_token)
check(
    "GET /auth/me -> 200 profile",
    status == 200 and body["data"]["email"] == commuter_email,
    str(status),
)

# 9. Commuter cannot create staff accounts
status, _ = call(
    "POST",
    "/auth/users",
    {"full_name": "X", "email": f"x-{SUFFIX}@example.com", "password": "Password123!", "role": "OPERATOR"},
    token=commuter_token,
)
check("POST /auth/users as COMMUTER -> 403", status == 403, str(status))

# 10. No MANAGEMENT account exists yet: bootstrap one directly via SQL is out of
#     scope for this script, so the management-only path is covered by pytest.
#     Here we only confirm the endpoint is not open to anonymous callers.
status, _ = call(
    "POST",
    "/auth/users",
    {"full_name": "X", "email": f"anon-{SUFFIX}@example.com", "password": "Password123!", "role": "OPERATOR"},
)
check("POST /auth/users anonymous -> 401", status == 401, str(status))

# 11. OpenAPI documents the endpoints
status, body = call("GET", f"{BASE}/api/v1/openapi.json")
paths = body.get("paths", {}) if status == 200 else {}
# OpenAPI path keys are the full paths, including the /api/v1 prefix.
check(
    "GET /api/v1/openapi.json lists auth endpoints",
    status == 200
    and all(
        f"/api/v1/auth/{name}" in paths
        for name in ("register", "login", "me", "users")
    ),
    str(status),
)

# --- Phase 2: transport network ---------------------------------------------
# The Phase 2 writes need a MANAGEMENT account, and none may exist yet. The
# script creates one directly in the development database (hashed by the
# application's own Argon2id function, the same way the SQL bootstrap does)
# and then logs in through the API like any other client.

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

management_email = f"manual-mgmt-{SUFFIX}@example.com"
with SessionLocal() as session:
    session.add(
        User(
            full_name="Manual Management",
            email=management_email,
            password_hash=hash_password("Password123!"),
            role=UserRole.MANAGEMENT,
            is_active=True,
        )
    )
    session.commit()

status, body = call(
    "POST", "/auth/login", {"email": management_email, "password": "Password123!"}
)
check(
    "management account can log in -> 200 token",
    status == 200 and bool(body.get("data", {}).get("access_token")),
    str(status),
)
management_token = body.get("data", {}).get("access_token", "")

# 12. Route and stop reads are public - no token sent.
status, _ = call("GET", "/stops")
check("GET /stops without token -> 200", status == 200, str(status))
status, _ = call("GET", "/routes")
check("GET /routes without token -> 200", status == 200, str(status))

# 13. Management creates two stops.
stop_ids: list[str] = []
for label in ("Manual Alpha", "Manual Bravo"):
    status, body = call(
        "POST",
        "/stops",
        {"name": label, "latitude": -17.8252, "longitude": 31.0335},
        token=management_token,
    )
    check(f"POST /stops ({label}) -> 201", status == 201, str(status))
    if status == 201:
        stop_ids.append(body["data"]["id"])

# 14. Commuters may read but not write.
status, _ = call(
    "POST",
    "/stops",
    {"name": "Nope", "latitude": -17.8, "longitude": 31.0},
    token=commuter_token,
)
check("POST /stops as COMMUTER -> 403", status == 403, str(status))

route_code = f"R{SUFFIX.upper()}"
status, body = call(
    "POST",
    "/routes",
    {
        "name": "Manual Line",
        "code": route_code,
        "stops": [
            {"stop_id": stop_ids[0]},
            {"stop_id": stop_ids[1], "estimated_minutes_from_start": 12},
        ],
    },
    token=management_token,
)
check(
    "POST /routes with stops -> 201 active",
    status == 201 and body["data"]["is_active"] is True,
    str(status),
)
route_id = body["data"]["id"] if status == 201 else ""

# 15. The public detail returns the ordered stops.
status, body = call("GET", f"/routes/{route_id}")
stops = body.get("data", {}).get("stops", [])
check(
    "GET /routes/{id} -> 200 with ordered stops",
    status == 200 and [entry["stop_sequence"] for entry in stops] == [1, 2],
    str(status),
)

# 16. Route codes are unique regardless of case.
status, _ = call(
    "POST",
    "/routes",
    {"name": "Duplicate code", "code": route_code.lower()},
    token=management_token,
)
check("POST /routes with a taken code -> 409", status == 409, str(status))

# 17. Reordering replaces the whole list.
status, body = call(
    "PUT",
    f"/routes/{route_id}/stops",
    {
        "stops": [
            {"stop_id": stop_ids[1]},
            {"stop_id": stop_ids[0], "estimated_minutes_from_start": 5},
        ]
    },
    token=management_token,
)
check(
    "PUT /routes/{id}/stops -> 200 and reordered",
    status == 200
    and [entry["stop_id"] for entry in body["data"]["stops"]]
    == [stop_ids[1], stop_ids[0]],
    str(status),
)

# 18. A draft route cannot be activated before it has stops.
status, body = call(
    "POST",
    "/routes",
    {"name": "Manual Draft", "code": f"D{SUFFIX.upper()}"},
    token=management_token,
)
check("POST /routes without stops -> 201 draft", status == 201 and body["data"]["is_active"] is False, str(status))
draft_id = body["data"]["id"] if status == 201 else ""
status, _ = call("PATCH", f"/routes/{draft_id}", {"is_active": True}, token=management_token)
check("PATCH activating a draft -> 409", status == 409, str(status))

# 19. Anonymous callers cannot write.
status, _ = call("POST", "/routes", {"name": "Anon", "code": f"A{SUFFIX.upper()}"})
check("POST /routes anonymous -> 401", status == 401, str(status))

# 20. Routes are deactivated, never deleted.
status, _ = call("DELETE", f"/routes/{route_id}", token=management_token)
check("DELETE /routes/{id} -> 405", status == 405, str(status))

# 21. OpenAPI documents the Phase 2 endpoints too.
status, body = call("GET", f"{BASE}/api/v1/openapi.json")
paths = body.get("paths", {}) if status == 200 else {}
check(
    "GET /api/v1/openapi.json lists Phase 2 endpoints",
    status == 200
    and all(
        path in paths
        for path in (
            "/api/v1/routes",
            "/api/v1/routes/{route_id}",
            "/api/v1/routes/{route_id}/stops",
            "/api/v1/stops",
        )
    ),
    str(status),
)

# 22. The fleet is management-only.
status, _ = call("GET", "/buses")
check("GET /buses without token -> 401", status == 401, str(status))
status, _ = call("GET", "/buses", token=commuter_token)
check("GET /buses as COMMUTER -> 403", status == 403, str(status))

# 23. Management registers a bus, already assigned to the route above.
plate_input = f"  mn {SUFFIX}  "
status, body = call(
    "POST",
    "/buses",
    {
        "registration_number": plate_input,
        "fleet_number": f"fleet-{SUFFIX}",
        "capacity": 45,
        "route_id": route_id,
    },
    token=management_token,
)
check(
    "POST /buses -> 201 with normalized identifiers",
    status == 201
    and body["data"]["registration_number"] == f"MN {SUFFIX.upper()}"
    and body["data"]["fleet_number"] == f"FLEET-{SUFFIX.upper()}"
    and body["data"]["route_id"] == route_id,
    str(status),
)
bus_id = body["data"]["id"] if status == 201 else ""

# 24. A taken plate is a conflict, and a second bus joins the fleet.
status, _ = call(
    "POST",
    "/buses",
    {
        "registration_number": f"MN {SUFFIX.upper()}",
        "fleet_number": f"OTHER-{SUFFIX.upper()}",
        "capacity": 30,
    },
    token=management_token,
)
check("POST /buses with a taken plate -> 409", status == 409, str(status))

status, body = call(
    "POST",
    "/buses",
    {
        "registration_number": f"MN {SUFFIX.upper()} B",
        "fleet_number": f"FLEETB-{SUFFIX.upper()}",
        "capacity": 30,
    },
    token=management_token,
)
check("POST /buses second bus -> 201", status == 201, str(status))
bus2_id = body["data"]["id"] if status == 201 else ""

# 25. PATCH clears the route with null, then sets it again.
status, body = call(
    "PATCH", f"/buses/{bus_id}", {"route_id": None}, token=management_token
)
check(
    "PATCH /buses/{id} route_id null -> 200 cleared",
    status == 200 and body["data"]["route_id"] is None,
    str(status),
)
status, body = call(
    "PATCH", f"/buses/{bus_id}", {"route_id": route_id}, token=management_token
)
check(
    "PATCH /buses/{id} assign route -> 200",
    status == 200 and body["data"]["route_id"] == route_id,
    str(status),
)
status, _ = call(
    "PATCH", f"/buses/{bus_id}", {"route_id": str(uuid4())}, token=management_token
)
check("PATCH /buses/{id} unknown route -> 404", status == 404, str(status))

# 26. Two operator accounts, created directly like the management one.
def _login_staff(role: UserRole, prefix: str) -> tuple[str, str]:
    email = f"{prefix}-{SUFFIX}@example.com"
    with SessionLocal() as session:
        session.add(
            User(
                full_name=f"Manual {role.value.title()}",
                email=email,
                password_hash=hash_password("Password123!"),
                role=role,
                is_active=True,
            )
        )
        session.commit()
    status, body = call(
        "POST", "/auth/login", {"email": email, "password": "Password123!"}
    )
    assert status == 200, body
    return body["data"]["access_token"], email


operator1_token, operator1_email = _login_staff(UserRole.OPERATOR, "manual-op1")
operator2_token, operator2_email = _login_staff(UserRole.OPERATOR, "manual-op2")

# 27. Nothing assigned yet -> 404, then the assignment and what it returns.
status, _ = call("GET", "/operators/me/assignment", token=operator1_token)
check(
    "GET /operators/me/assignment without assignment -> 404",
    status == 404,
    str(status),
)

status, body = call(
    "POST",
    f"/operators/{operator1_email}/assignments",
    {"bus_id": bus_id},
    token=management_token,
)
check(
    "POST /operators/{email}/assignments -> 201 with bus and route",
    status == 201
    and body["data"]["bus"]["id"] == bus_id
    and body["data"]["bus"]["route"]["code"] == route_code,
    str(status),
)

status, body = call("GET", "/operators/me/assignment", token=operator1_token)
check(
    "GET /operators/me/assignment -> 200 with bus and route",
    status == 200
    and body["data"]["bus"]["id"] == bus_id
    and body["data"]["bus"]["route"]["id"] == route_id,
    str(status),
)

# 28. The three 409 rules.
status, _ = call(
    "POST",
    f"/operators/{operator1_email}/assignments",
    {"bus_id": bus2_id},
    token=management_token,
)
check("second assignment for the same operator -> 409", status == 409, str(status))

status, _ = call(
    "POST",
    f"/operators/{operator2_email}/assignments",
    {"bus_id": bus_id},
    token=management_token,
)
check("second driver for the same bus -> 409", status == 409, str(status))

status, _ = call(
    "POST",
    f"/operators/{commuter_email}/assignments",
    {"bus_id": bus2_id},
    token=management_token,
)
check("assigning a COMMUTER -> 409", status == 409, str(status))

# 29. Ending the assignment keeps it as history and frees both sides.
status, body = call(
    "DELETE", f"/operators/{operator1_email}/assignments", token=management_token
)
check(
    "DELETE /operators/{email}/assignments -> 200 ended",
    status == 200
    and body["data"]["is_active"] is False
    and bool(body["data"]["ended_at"]),
    str(status),
)
status, _ = call(
    "DELETE", f"/operators/{operator1_email}/assignments", token=management_token
)
check("DELETE without an active assignment -> 404", status == 404, str(status))

status, _ = call(
    "POST",
    f"/operators/{operator1_email}/assignments",
    {"bus_id": bus2_id},
    token=management_token,
)
check("assign again after ending -> 201", status == 201, str(status))

# 30. Operators stay read-only on the fleet.
status, _ = call("GET", "/buses", token=operator1_token)
check("GET /buses as OPERATOR -> 403", status == 403, str(status))

# 31. OpenAPI documents the Phase 2b endpoints too.
status, body = call("GET", f"{BASE}/api/v1/openapi.json")
paths = body.get("paths", {}) if status == 200 else {}
check(
    "GET /api/v1/openapi.json lists Phase 2b endpoints",
    status == 200
    and all(
        path in paths
        for path in (
            "/api/v1/buses",
            "/api/v1/buses/{bus_id}",
            "/api/v1/operators/{operator_email}/assignments",
            "/api/v1/operators/me/assignment",
        )
    ),
    str(status),
)

# --- Phase 3: journey pricing ------------------------------------------------
# Reuses the route and its two stops from Phase 2 above.

# 32. Fares are public reads, like routes and stops.
status, _ = call("GET", "/fares")
check("GET /fares without token -> 200", status == 200, str(status))
status, _ = call(
    "GET",
    f"/fares/search?origin_stop_id={stop_ids[0]}&destination_stop_id={stop_ids[1]}",
)
check("GET /fares/search without token -> 200", status == 200, str(status))

# 33. Management configures the fare for the journey.
status, body = call(
    "POST",
    "/fares",
    {
        "route_id": route_id,
        "origin_stop_id": stop_ids[0],
        "destination_stop_id": stop_ids[1],
        "amount": "1.50",
    },
    token=management_token,
)
check(
    "POST /fares -> 201 with decimal string amount and default currency",
    status == 201
    and body["data"]["amount"] == "1.50"
    and body["data"]["currency"] == "USD"
    and body["data"]["effective_to"] is None,
    str(status),
)
first_fare_id = body["data"]["id"] if status == 201 else ""

# 34. Commuters may read but not configure fares.
status, _ = call(
    "POST",
    "/fares",
    {
        "route_id": route_id,
        "origin_stop_id": stop_ids[0],
        "destination_stop_id": stop_ids[1],
        "amount": "9.99",
    },
    token=commuter_token,
)
check("POST /fares as COMMUTER -> 403", status == 403, str(status))
status, _ = call(
    "POST",
    "/fares",
    {
        "route_id": route_id,
        "origin_stop_id": stop_ids[0],
        "destination_stop_id": stop_ids[1],
        "amount": "9.99",
    },
)
check("POST /fares anonymous -> 401", status == 401, str(status))

# 35. The commuter view shows the fare that applies right now.
status, body = call(
    "GET",
    f"/fares/search?origin_stop_id={stop_ids[0]}&destination_stop_id={stop_ids[1]}",
)
fares = body.get("data", [])
check(
    "GET /fares/search -> 200 with the current fare",
    status == 200 and len(fares) == 1 and fares[0]["amount"] == "1.50",
    str(status),
)

# 36. A price change supersedes the old fare instead of overwriting it.
status, body = call(
    "POST",
    "/fares",
    {
        "route_id": route_id,
        "origin_stop_id": stop_ids[0],
        "destination_stop_id": stop_ids[1],
        "amount": "2.00",
    },
    token=management_token,
)
check("POST /fares (price change) -> 201", status == 201, str(status))
second_fare_id = body["data"]["id"] if status == 201 else ""

status, body = call("GET", f"/fares?route_id={route_id}&include_history=true")
history = body.get("data", [])
old_row = next((item for item in history if item["id"] == first_fare_id), {})
new_row = next((item for item in history if item["id"] == second_fare_id), {})
check(
    "GET /fares include_history keeps the superseded fare",
    status == 200
    and len(history) == 2
    and old_row.get("amount") == "1.50"
    and old_row.get("effective_to") == new_row.get("effective_from"),
    str(status),
)
status, body = call("GET", f"/fares?route_id={route_id}")
current = body.get("data", [])
check(
    "GET /fares without history returns only the current fare",
    status == 200 and [item["id"] for item in current] == [second_fare_id],
    str(status),
)

# 37. Two fares cannot start at the same moment.
same_start = "2031-01-01T00:00:00"
for _ in range(2):
    status, _ = call(
        "POST",
        "/fares",
        {
            "route_id": route_id,
            "origin_stop_id": stop_ids[0],
            "destination_stop_id": stop_ids[1],
            "amount": "2.50",
            "effective_from": same_start,
        },
        token=management_token,
    )
check("POST /fares with a taken start time -> 409", status == 409, str(status))

# 38. Rule 6: both stops must belong to the route being priced.
status, body = call(
    "POST",
    "/stops",
    {"name": f"Manual Off-Route {SUFFIX}", "latitude": -17.9, "longitude": 31.1},
    token=management_token,
)
off_route_stop = body["data"]["id"] if status == 201 else ""
status, _ = call(
    "POST",
    "/fares",
    {
        "route_id": route_id,
        "origin_stop_id": stop_ids[0],
        "destination_stop_id": off_route_stop,
        "amount": "3.00",
    },
    token=management_token,
)
check("POST /fares with a stop that is not on the route -> 422", status == 422, str(status))

# 39. Rule 7: the price itself cannot be patched away.
status, _ = call(
    "PATCH", f"/fares/{second_fare_id}", {"amount": "9.99"}, token=management_token
)
check("PATCH /fares with amount -> 422", status == 422, str(status))

status, _ = call(
    "PATCH", f"/fares/{second_fare_id}", {"is_active": False}, token=management_token
)
check("PATCH /fares deactivate -> 200", status == 200, str(status))
status, body = call("GET", f"/fares?route_id={route_id}")
check(
    "deactivated fare leaves the commuter list",
    status == 200 and body.get("data") == [],
    str(status),
)
status, _ = call(
    "PATCH", f"/fares/{second_fare_id}", {"is_active": True}, token=management_token
)
check("PATCH /fares reactivate -> 200", status == 200, str(status))

status, _ = call("PATCH", f"/fares/{uuid4()}", {"is_active": True}, token=management_token)
check("PATCH /fares unknown id -> 404", status == 404, str(status))

# 40. A mistyped search is a 404, an impossible one a 422.
status, _ = call(
    "GET", f"/fares/search?origin_stop_id={uuid4()}&destination_stop_id={stop_ids[1]}"
)
check("GET /fares/search unknown stop -> 404", status == 404, str(status))
status, _ = call(
    "GET", f"/fares/search?origin_stop_id={stop_ids[0]}&destination_stop_id={stop_ids[0]}"
)
check("GET /fares/search same stop twice -> 422", status == 422, str(status))

# 41. OpenAPI documents the Phase 3 endpoints too.
status, body = call("GET", f"{BASE}/api/v1/openapi.json")
paths = body.get("paths", {}) if status == 200 else {}
check(
    "GET /api/v1/openapi.json lists Phase 3 endpoints",
    status == 200
    and all(
        path in paths
        for path in (
            "/api/v1/fares",
            "/api/v1/fares/search",
            "/api/v1/fares/{fare_id}",
        )
    ),
    str(status),
)

failed = [name for ok, name in results if not ok]
print()
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    print("FAILED: " + "; ".join(failed))
sys.exit(1 if failed else 0)