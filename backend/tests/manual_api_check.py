"""Manual end-to-end verification of the Phase 1 API over real HTTP.

Starts nothing itself: run the app with
    python -m uvicorn app.main:app --port 8010
in another shell, then run this script. It uses the development database and
prints a PASS/FAIL line per check.
"""

import json
import sys
import urllib.error
import urllib.request
from uuid import uuid4

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

failed = [name for ok, name in results if not ok]
print()
print(f"{len(results) - len(failed)}/{len(results)} checks passed")
if failed:
    print("FAILED: " + "; ".join(failed))
sys.exit(1 if failed else 0)