# OpenAPI and API Conventions

## 1. Naming

Use plural resource names where appropriate:

```text
/users
/routes
/stops
/buses
/trips
/fares
```

Use action endpoints only when an operation is not naturally represented as CRUD:

```text
/trips/start
/trips/{trip_id}/end
```

## 2. IDs

Use UUIDs for business resources.

Example:

```json
{
  "id": "0b6d2e25-4c5f-4c44-9d90-3c3e1f7d4f18"
}
```

## 3. Dates

Use ISO 8601 timestamps.

Prefer UTC in the backend.

Example:

```text
2026-10-04T18:00:00Z
```

## 4. Money

Represent money as a decimal value in the database.

Example:

```json
{
  "amount": "1.50",
  "currency": "USD"
}
```

## 5. Pagination

List endpoints that may become large should eventually support:

```text
?page=1&page_size=20
```

or cursor pagination where appropriate.

## 6. Filtering

Use query parameters:

```text
/routes?is_active=true
```

## 7. OpenAPI Documentation

FastAPI should expose development documentation through its standard OpenAPI/Swagger support.

Before production, review whether public exposure of interactive API documentation is appropriate.

## 8. API Contract Rule

Flutter development should consume the documented API contract rather than directly depending on database structures.

When an API contract changes:
1. Update backend schema.
2. Update API documentation.
3. Update Flutter integration.
4. Run integration tests.
