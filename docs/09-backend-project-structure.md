# Backend Project Structure

## Recommended Structure

```text
transport-system/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   │
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── exceptions.py
│   │   │
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   │
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   └── api/
│   │       └── v1/
│   │           ├── router.py
│   │           └── endpoints/
│   │
│   ├── alembic/
│   ├── tests/
│   ├── .env.example
│   ├── requirements.txt
│   └── README.md
│
├── frontend/
│   └── Flutter application
│
└── docs/
```

## Module Responsibilities

### core

Application configuration, security and shared infrastructure.

### db

Database engine, sessions and model metadata.

### models

SQLAlchemy database models.

### schemas

Pydantic request and response schemas.

### services

Business logic.

Example:

```text
fare_service.py
location_service.py
eta_service.py
analytics_service.py
```

### repositories

Optional data-access layer for complex queries.

### api

FastAPI routers and endpoint definitions.

## Important Principle

Do not place complex business logic directly inside route handlers.

Prefer:

```text
API endpoint
    |
    v
Service
    |
    v
Repository/Database
```

This keeps the backend easier to test and maintain.
