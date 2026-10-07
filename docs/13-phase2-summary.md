# Transport System — Phase 2 Implementation (Transport Network)

Status: **complete** — 134 tests pass, both migrations applied and verified on PostgreSQL 18.4.
Scope follows `docs/00-development-roadmap.md` Phase 2 only. No Phase 3+ features were built.
Shipped as two commits, as agreed: `feat: add routes and stops`, then
`feat: add bus and operator management`.

## Implemented

- `Route`, `Stop` and `RouteStop` models; the stop order lives in
  `route_stops.stop_sequence` with `UNIQUE(route_id, stop_sequence)`
- `Bus` and `OperatorAssignment` models
- Public route and stop reads (no token): commuters browse before they register
- Management-only writes for routes, stops and buses
- Ordered stop list as a single atomic `PUT`, renumbered from 1 by the server
- Route activation only once it has at least two stops (`docs/02` rule 5)
- `buses.route_id`: the route a bus currently runs; an operator's route is read
  from their assigned bus (the agreed deviation, recorded in `docs/04` §7/§13)
- Operator-to-bus assignment with the three conflict rules, plus
  `GET /operators/me/assignment` returning the bus **and** its route
- Assignments are ended, never deleted: `ended_at` is set and the row stays as
  history
- Identifier normalization: route codes, plates and fleet numbers are trimmed
  and upper-cased by the schema layer

### Endpoints

| Method | Path                                       | Auth   | Role       | Success |
|--------|--------------------------------------------|--------|------------|---------|
| GET    | `/api/v1/routes`                           | no     | –          | 200     |
| GET    | `/api/v1/routes/{route_id}`                | no     | –          | 200     |
| POST   | `/api/v1/routes`                           | bearer | MANAGEMENT | 201     |
| PATCH  | `/api/v1/routes/{route_id}`                | bearer | MANAGEMENT | 200     |
| PUT    | `/api/v1/routes/{route_id}/stops`          | bearer | MANAGEMENT | 200     |
| GET    | `/api/v1/stops`                            | no     | –          | 200     |
| POST   | `/api/v1/stops`                            | bearer | MANAGEMENT | 201     |
| PATCH  | `/api/v1/stops/{stop_id}`                  | bearer | MANAGEMENT | 200     |
| GET    | `/api/v1/buses`                            | bearer | MANAGEMENT | 200     |
| POST   | `/api/v1/buses`                            | bearer | MANAGEMENT | 201     |
| PATCH  | `/api/v1/buses/{bus_id}`                   | bearer | MANAGEMENT | 200     |
| POST   | `/api/v1/operators/{operator_id}/assignments` | bearer | MANAGEMENT | 201  |
| GET    | `/api/v1/operators/me/assignment`          | bearer | OPERATOR    | 200     |
| DELETE | `/api/v1/operators/{operator_id}/assignments` | bearer | MANAGEMENT | 200  |

Responses use the envelope from `docs/05-api-specification.md` section 12:
`{"data": ..., "message": "Success"}`. Errors use `{"detail": "..."}`.

There is deliberately no `DELETE` for routes, stops or buses: they are
deactivated with `PATCH {"is_active": false}`, so a DELETE answers 405.

## Files created

- `app/models/route.py`, `stop.py`, `route_stop.py`, `bus.py`,
  `operator_assignment.py`
- `app/schemas/route.py`, `stop.py`, `bus.py`, `operator_assignment.py`
- `app/services/route_service.py`, `stop_service.py`, `bus_service.py`,
  `assignment_service.py`
- `app/api/v1/endpoints/routes.py`, `stops.py`, `buses.py`, `operators.py`
- `alembic/versions/92c12e0e12f2_create_routes_stops_tables.py`
- `alembic/versions/0d6cf8f316be_create_buses_and_operator_assignments_.py`
- `tests/test_routes.py`, `test_stops.py`, `test_route_stops.py`,
  `test_buses.py`, `test_operator_assignments.py`

## Files changed

- `app/models/__init__.py` – registers the five new models so `create_all` and
  autogenerate see them
- `app/schemas/validators.py` – `normalize_route_code`, `normalize_identifier`
- `app/api/v1/router.py` – mounts the routes, stops, buses and operators routers
- `tests/manual_api_check.py` – Phase 2 and Phase 2b sections (46 checks total)
- `docs/04-database-specification.md` – §4 nullable timing note, §6 ordering
  note, §7 `buses.route_id`, §13 Bus → Route relationship
- `docs/05-api-specification.md` – §3 `PUT /routes/{id}/stops`, public reads,
  deactivation instead of `DELETE`, §5 bus rules, §6 the three 409 rules and
  `DELETE` for ending an assignment

## Tests

`pytest` → **134 passed** (46 from Phase 1, 88 new).

| File | Covers |
|------|--------|
| `test_routes.py` | list filtering/order, public reads, create with and without stops, code normalization and uniqueness, 409 on activation without stops, 404/401/403 paths, extra fields rejected, deactivated route hidden from list but 200 by id, DELETE → 405 |
| `test_stops.py` | create/read/update, coordinates validation, duplicate names, auth matrix |
| `test_route_stops.py` | atomic replace, renumbering from 1, partial timings, <2 stops 422, duplicate stop 422, decreasing minutes 422, unknown route/stop 404, auth matrix |
| `test_buses.py` | create/normalize identifiers, duplicate plate/fleet 409, invalid identifiers and capacity 422, unknown route 404, list filtering and ordering, PATCH assigns/clears route, empty PATCH 422, auth matrix |
| `test_operator_assignments.py` | assignment returns bus + route, non-OPERATOR target 409, unknown operator/bus 404, operator-bus conflicts 409, end → history → reassign, `GET /operators/me/assignment` 200/404, auth matrix, and two tests that prove the partial unique indexes reject duplicates at the database level |

Tests run against a real PostgreSQL database (`waitless_test`, created
automatically); each test runs in a transaction that is rolled back.

### Manual verification

`tests/manual_api_check.py` runs **46/46 checks** over real HTTP against a
running server (`python -m uvicorn app.main:app --port 8010`): everything from
Phases 0-1 plus public route/stop reads, route creation with stops, the
reorder/409/405 paths, bus registration with normalized identifiers, route
assignment and clearing, the three assignment 409 rules, ending an assignment,
and the OpenAPI document listing all Phase 2 endpoints. The server was stopped
afterwards; the accounts and data it created stay in the development database
under a unique suffix.

## Migration

Two migrations, one per commit:

1. `92c12e0e12f2_create_routes_stops_tables.py` (revision `92c12e0e12f2`,
   down_revision `218616e36e34`) — `routes`, `stops`, `route_stops`.
2. `0d6cf8f316be_create_buses_and_operator_assignments_.py` (revision
   `0d6cf8f316be`, down_revision `92c12e0e12f2`) — `buses`,
   `operator_assignments`.

Verified on PostgreSQL 18.4: `upgrade head` → `downgrade` → `upgrade head` for
both, and `alembic check` → "No new upgrade operations detected" after each.

- `routes`: `code` unique index, `is_active` defaults to **false**, timing
  column nullable
- `route_stops`: `UNIQUE(route_id, stop_sequence)` named
  `uq_route_stops_route_id_stop_sequence`, plus `ix_route_stops_stop_id`
- `buses`: unique indexes on `registration_number`/`fleet_number`,
  `route_id` nullable and indexed
- `operator_assignments`: no `created_at`/`updated_at` (per `docs/04` §8);
  two **partial** unique indexes, `WHERE is_active`, one per operator and one
  per bus
- Foreign keys are left unnamed so PostgreSQL names them exactly the way
  `Base.metadata.create_all` does for the test database

## Decisions worth knowing

- **Public route/stop reads.** `docs/04` §12 keeps `journey_searches.commuter_id`
  nullable, i.e. anonymous users search for journeys, so `GET /routes`,
  `GET /routes/{id}` and `GET /stops` take no token. Every write is
  management-only. `GET /buses` is management-only instead: plates and capacity
  are operational data.
- **`buses.route_id` (the approved deviation).** The route lives on the bus
  rather than on the assignment, so it is stored once and an operator's route
  is derived from their bus. `docs/04` §7 and §13 were updated before the code.
- **409 on reassignment, plus an explicit way out.** Re-assigning an operator
  or a bus that already has an active assignment returns 409 (the agreed
  behaviour). That would be a dead end without an endpoint to end an
  assignment, so `DELETE /operators/{operator_id}/assignments` was added — it
  marks the row ended instead of removing it. This is one addition beyond the
  originally listed endpoints and is documented in `docs/05` §6.
- **The database enforces "one active" too.** Two partial unique indexes back
  the 409 rules, so racing requests cannot both win; the service checks run
  first only to give a friendly message.
- **Draft routes.** `POST /routes` with stops publishes immediately; without
  stops it creates a draft that can only be activated once two stops exist.
  A deactivated route still answers 200 with `is_active: false` by id — it is
  only hidden from the list.
- **Order comes from the payload.** `stop_sequence` is assigned from list
  order on every write, so clients never send it and cannot create gaps.

## Known limitations

1. **No `GET /buses/{bus_id}`** — `docs/05` §5 does not define it, so
   management identifies a bus through the list.
2. **No route history on a bus.** `buses.route_id` holds only the current
   route; past assignments of a bus are not tracked (the operator assignment
   rows are, since they carry `ended_at`).
3. **Assignment history has no list endpoint** (e.g.
   `GET /operators/{id}/assignments`); the rows are queryable in the database.
4. **Capacity's upper bound (1000) is an invented sanity limit**, not a
   requirement from `docs/02`.
5. **Still open from Phase 1**: no management endpoint to list/deactivate
   users, no SQL-injection test (`docs/07` §5), no linter/formatter installed,
   CORS `*` and OpenAPI exposed everywhere, `.env` is loaded relative to the
   working directory (run everything from `backend/`), FastAPI/starlette
   deprecation warnings on Python 3.14.
6. **The development database accumulates test data**: every manual run leaves
   accounts, stops, routes, buses and assignments behind under a unique suffix.

## Next phase

Phase 3 — Journey Pricing: fare configuration per route, public fare
retrieval, operator/management fare management and fare validation, so that a
commuter selecting a route receives the current fare. The Phase 1 limitation on
user-management endpoints should also be settled before the Flutter app needs
to create operators itself.
