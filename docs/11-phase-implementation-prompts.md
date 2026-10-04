# OpenCode Phase Prompts

These prompts are intended to be given to OpenCode one at a time.

## Phase 0 — Foundation

```text
Read the project documentation in docs/ first.

Implement Phase 0 from docs/00-development-roadmap.md only.

Set up the FastAPI backend foundation, PostgreSQL connection, SQLAlchemy, Alembic, configuration, environment handling, logging, health endpoint and testing structure.

Do not implement authentication, routes, buses, fares, location tracking, ETA or analytics yet.

Inspect the existing project before changing files. Reuse working code where possible.

After implementation:
- run tests
- verify the health endpoint
- verify database connectivity
- verify Alembic setup
- report files changed
- report tests
- report known limitations

Do not start Phase 1.
```

## Phase 1 — Authentication

```text
Read docs/00-development-roadmap.md through docs/08-ai-workflow-rules.md.

Implement Phase 1 only.

Add users, roles, password hashing, JWT authentication, registration/login, current-user endpoint and role-based authorization.

Do not implement routes, buses, fares, location tracking, ETA or analytics.

Create and test the database migration.

Run the complete test suite.

Do not start Phase 2.
```

## Phase 2 — Transport Network

```text
Implement Phase 2 only.

Add routes, stops, ordered route stops, buses, operator assignments and the required management/operator endpoints.

Follow the database and API specifications.

Do not implement fares, location tracking, ETA or analytics yet.

Create migrations and tests.

Do not start Phase 3.
```

## Phase 3 — Fares

```text
Implement Phase 3 only.

Add fare configuration and fare lookup.

Preserve historical fares.

Implement validation and authorization.

Create migration and tests.

Do not implement location tracking or ETA.
```

## Phase 4 — Location Tracking

```text
Implement Phase 4 only.

Add active trips and operator location updates.

Validate that only an authorized operator can send location data for an active trip.

Store latitude, longitude, timestamps and optional speed/heading.

Implement latest-location retrieval and freshness handling.

Do not implement advanced ETA or analytics.
```

## Phase 5 — Commuter Discovery

```text
Implement Phase 5 only.

Create commuter journey search that combines route, fare, active bus and latest location information.

Return clear location freshness information.

Do not implement advanced traffic-aware ETA yet.
```

## Phase 6 — ETA

```text
Implement Phase 6 only.

Add a simple, testable ETA calculation based on available route/location information.

Handle stale location, missing speed and invalid journey cases.

Do not introduce machine learning or external map services unless explicitly requested.
```

## Phase 7 — Analytics

```text
Implement Phase 7 only.

Add aggregated management analytics for commuter demand, routes, destinations and origin-destination pairs.

Protect analytics endpoints so only management users can access them.

Avoid exposing unnecessary commuter personal information.

Add tests.
```

## Phase 8 — Production Hardening

```text
Implement Phase 8 only.

Review the complete backend for security, performance, error handling, indexes, logging, configuration, rate limiting where appropriate, API versioning, backups and deployment readiness.

Do not add unrelated product features.

Run the complete test suite and provide a production-readiness report.
```
