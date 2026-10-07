"""Manual end-to-end verification of the API over real HTTP (Phases 1 and 2).

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

failed = [name for ok, name in results if not ok]
print()
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    print("FAILED: " + "; ".join(failed))
sys.exit(1 if failed else 0)