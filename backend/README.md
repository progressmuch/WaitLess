# Transport System - Backend

FastAPI backend for Transport Tracking and Commuter Information System.

## Requirements

| Component | Version | Why it is pinned |
|-----------|---------|------------------|
| Python | **3.14** | The virtual environment in this repo (`../WaitLessVenv`) runs 3.14. |
| SQLAlchemy | **2.1.3 (exact)** | SQLAlchemy 2.0.x cannot be used on Python 3.14: it raises `TypeError: descriptor '__getitem__' requires a 'typing.Union' object` for every `Mapped[Optional[...]]` model column. Any table with a nullable column fails at import time. |
| alembic | **1.20.0 (exact)** | Must be at least as new as SQLAlchemy 2.1. Older releases predate it and autogenerate behaviour is untested. |
| pwdlib | **0.3.1** | Argon2id hashing. `passlib` 1.7.4 is **not** used: it is incompatible with bcrypt >= 5. |

Do not downgrade or loosen these pins. If Python is upgraded again, re-verify
`pytest` and the migration cycle (`alembic upgrade head`, `downgrade base`,
`upgrade head`, `alembic check`) before continuing with later phases.

## Setup

1. Create virtual environment (already created: `../WaitLessVenv`)
2. Install dependencies
```bash
pip install -r requirements.txt
```
3. Copy `.env.example` to `.env`
```powershell
Copy-Item .env.example .env
```
4. Update `.env` with configuration (database URL, a real `SECRET_KEY`)
5. Run migrations
```bash
alembic upgrade head
```
6. Run development server
```bash
uvicorn app.main:app --reload
```

## Testing

```bash
pytest -v
```

The suite runs against a real PostgreSQL database (`waitless_test` by default;
override with `TEST_DATABASE_URL`). That database is created automatically, and
each test runs in a transaction that is rolled back afterwards.

## Manual API check

With the server running on port 8010:
```bash
uvicorn app.main:app --port 8010
python tests/manual_api_check.py
```

## Endpoints

| Method | Path | Auth | Role |
|--------|------|------|------|
| GET    | `/health` | public | – |
| POST   | `/api/v1/auth/register` | public | – |
| POST   | `/api/v1/auth/login` | public | – |
| GET    | `/api/v1/auth/me` | bearer token | any |
| POST   | `/api/v1/auth/users` | bearer token | MANAGEMENT |

Swagger UI: `/docs` — OpenAPI document: `/api/v1/openapi.json`.