# Transport System — Phase 1 Implementation (Authentication and Users)

Status: **complete** — all tests pass, migration applied and verified on PostgreSQL 18.
Scope follows `docs/00-development-roadmap.md` Phase 1 only. No Phase 2+ features were built.

## Implemented

- `User` model with roles `COMMUTER`, `OPERATOR`, `MANAGEMENT` (`app/models/user.py`)
- Password hashing with **Argon2id** via `pwdlib` — no plaintext, no `passlib`
- JWT access tokens (`python-jose`); payload holds only `sub`, `iat`, `exp`, `type`
- Public registration that **always** creates a `COMMUTER`
- Management-only staff account creation (`POST /auth/users`)
- Login with user-enumeration protection (identical response and timing for
  unknown email and wrong password)
- Role-based authorization through a FastAPI dependency (`require_roles`)
- Current-user endpoint (`GET /auth/me`)
- Immediate revocation: the role and `is_active` flag are read from the database on
  every request, so deactivating a user invalidates tokens already issued

### Endpoints

| Method | Path                   | Auth        | Role       | Success |
|--------|------------------------|-------------|------------|---------|
| POST   | `/api/v1/auth/register` | public      | –          | 201     |
| POST   | `/api/v1/auth/login`    | public      | –          | 200     |
| GET    | `/api/v1/auth/me`       | bearer      | any        | 200     |
| POST   | `/api/v1/auth/users`    | bearer      | MANAGEMENT | 201     |

Responses use the envelope from `docs/05-api-specification.md` section 12:
`{"data": {...}, "message": "Success"}`. Errors use `{"detail": "..."}`.

## Files created

- `app/models/__init__.py`, `app/models/user.py`
- `app/schemas/__init__.py`, `common.py`, `user.py`, `auth.py`, `validators.py`
- `app/services/__init__.py`, `user_service.py`, `auth_service.py`
- `app/api/__init__.py`, `deps.py`, `api/v1/__init__.py`, `api/v1/router.py`,
  `api/v1/endpoints/__init__.py`, `api/v1/endpoints/auth.py`
- `alembic/versions/218616e36e34_create_users_table.py`
- `tests/conftest.py`, `tests/test_security.py`, `tests/test_auth.py`,
  `tests/test_rbac.py`, `tests/manual_api_check.py`

## Files changed

- `app/core/security.py` – Phase 0 stub replaced with real hashing and JWT helpers
- `app/core/config.py` – `SettingsConfigDict`, `TEST_DATABASE_URL`,
  `TEST_DATABASE_NAME`, `is_production`, refuse to start in production with the
  placeholder `SECRET_KEY`
- `app/main.py` – mounts `api_router` under `/api/v1`
- `alembic/env.py` – imports `app.models` so autogenerate sees the models
- `tests/test_health.py` – uses the shared `client` fixture; adds an OpenAPI check
- `requirements.txt` – `pwdlib[argon2]==0.3.1`, `SQLAlchemy==2.1.3`,
  `alembic==1.20.0`, `psycopg2-binary==2.9.13`, removed the broken
  `passlib[bcrypt]`
- `README.md` – added a pinned version table (Python 3.14, SQLAlchemy 2.1.3,
  alembic 1.20.0) explaining why each pin exists, plus test/manual-check commands
- `.env.example` – documents the test-database settings and how to generate a secret

### Removed

- `requirements.alt.txt` – a second, contradictory pin set that still listed the
  broken `passlib` and no `pwdlib`. One requirements file is now the single source
  of truth.

## Tests

`pytest` → **46 passed**.

| File | Covers |
|------|--------|
| `test_security.py` | hash is not plaintext, verify ok/wrong, salting, malformed hash, token round-trip, no sensitive claims, expired token, wrong-secret token, wrong token type |
| `test_auth.py` | register 201/normalisation/no hash in response, duplicate 409 (incl. case-insensitive), invalid email 422, short password 422, role self-assignment 422, login 200, mixed-case email, wrong password 401, enumeration check, deactivated 403, `/auth/me` 200 and 401 paths, expired/forged/unknown-user tokens, deactivation revokes live tokens |
| `test_rbac.py` | management creates staff, commuter 403, operator 403, anonymous 401, invalid role 422, duplicate 409, weak password 422, all roles can read `/auth/me`, role read from DB not token |
| `test_health.py` | health endpoint, OpenAPI document lists the auth endpoints |

Tests run against a real PostgreSQL database (`waitless_test`, created
automatically); each test runs in a transaction that is rolled back, and the
schema is dropped at the end of the run. SQLite was deliberately not used:
UUID columns, timezone-aware timestamps, server defaults and CHECK constraints
are PostgreSQL behaviour that must be exercised for real.

### Manual verification

`tests/manual_api_check.py` runs 12 checks over real HTTP against a running
server (`python -m uvicorn app.main:app --port 8010`) → **12/12 passed**:
health, register 201 COMMUTER, no hash in response, role field 422, duplicate
409, login token, identical 401s for wrong password and unknown email, `/auth/me`
401 without token and 200 with token, commuter 403 on the management endpoint,
anonymous 401, OpenAPI contents. The server was stopped and the test accounts
deleted from the development database afterwards.

## Migration

`alembic/versions/218616e36e34_create_users_table.py` (revision `218616e36e34`,
down_revision `299d519af363`).

- Verified: `upgrade head` → `downgrade base` → `upgrade head` all succeed on
  PostgreSQL 18.4
- `alembic check` → "No new upgrade operations detected" (models and database agree)
- `users`: `id` UUID PK, `full_name`, `email` (UNIQUE INDEX), `phone`,
  `password_hash`, `role` VARCHAR + CHECK (`user_role`), `is_active`,
  `created_at`/`updated_at` with `now()` defaults
- `role` is not a PostgreSQL ENUM type on purpose: adding a role later is a
  constraint change, not a type migration

## Known limitations

1. **No refresh tokens.** Access tokens last 30 minutes
   (`ACCESS_TOKEN_EXPIRE_MINUTES`) and there is no refresh endpoint, so clients
   must log in again after expiry. Add with Phase 8 if the Flutter app needs it.
2. **No "forgot password" / password reset or email verification.**
3. **Email validation is a regex** in `app/schemas/validators.py`, not RFC 5322.
   Swap in the `email-validator` package if stricter validation is needed
   (requires `EmailStr` and a new dependency).
4. **No management endpoint to list/deactivate users yet** — those are needed
   before Phase 2 can be exercised realistically, and would be a small Phase 2
   addition.
5. **Validation errors use FastAPI's default body** (`{"detail": [{...}]}`) rather
   than the literal `{"detail": "Invalid request"}` in `docs/05` section 12, so
   clients get per-field messages.
6. **CORS is still `*` and OpenAPI is exposed in every environment** (Phase 0
   settings). Tighten in Phase 8.
7. **fastapi 0.115.4 / starlette 0.41.3 emit deprecation warnings** on Python 3.14
   (`asyncio.iscoroutinefunction`, "slated for removal in Python 3.16"). Harmless
   today; upgrade before the Python version moves again.
8. **`alembic/script.py.mako` is still the 1.14 template** while alembic 1.20 is
   installed. It produces valid migrations (the Phase 1 migration was generated
   with it), but new autogenerate features such as `type_` are not wired in.
9. **Repository hygiene**: `*.pyc` files and `backend/waitless.db` are tracked in
   git and there is no `.gitignore`. Not changed here (needs approval).

## Decisions worth knowing

- `SECRET_KEY` now has a guard: the app refuses to start when
  `ENVIRONMENT=production` and the secret is still the placeholder.
- `HTTPBearer` (not `OAuth2PasswordBearer`) is used because login takes a JSON
  body, not form-encoded credentials. Clients send `Authorization: Bearer <token>`.
- Request schemas use `extra="forbid"`, so posting `role` to
  `/auth/register` returns 422 instead of being silently ignored.
- SQLAlchemy was upgraded 2.0.36 → 2.1.3: 2.0.x raises
  `TypeError: descriptor '__getitem__' requires a 'typing.Union' object` on
  Python 3.14 for any `Mapped[Optional[...]]` column.
- alembic was upgraded 1.14.0 → 1.20.0 so the migration tool is at least as new as
  SQLAlchemy 2.1. alembic 1.14.0 declared only `Requires: SQLAlchemy` with no
  upper bound, so pip installed the mismatched pair without complaint. The
  migration cycle and `alembic check` were re-verified after the upgrade.

## Next phase

Phase 2 — Transport Network: routes, stops, ordered route stops, buses,
operator assignments, and the management/operator endpoints for them. Phase 2
should also add the user-management endpoints listed in limitation 4, because
`operator_assignments.operator_id` references `users.id`.