# Transport System — Phase 3 Implementation (Journey Pricing)

Status: **complete** — 169 tests pass, the migration is applied and verified on
PostgreSQL 18.4. Scope follows `docs/00-development-roadmap.md` Phase 3 only.
No Phase 4+ features (location tracking, trips, ETA) were built.

## Implemented

- `Fare` model: a price for one `(route, origin, destination)` journey with a
  validity window `[effective_from, effective_to)` (`effective_to` NULL = the
  current, open-ended fare)
- Fare configuration by management, public fare retrieval for commuters
- `GET /fares/search?origin_stop_id=...&destination_stop_id=...` so a
  commuter who selected a journey receives the current fare — the Phase 3
  acceptance criterion
- Supersede instead of overwrite: posting a new fare for a journey that has
  one in force closes the old row at the moment the new price starts, so
  historical fares are preserved (docs/02 rules 6 and 7)
- Windows of one journey never overlap: a new fare is capped by a fare
  already scheduled to start later, and an update that would create an
  overlap returns `409`
- Lifecycle-only `PATCH` (`is_active`, `effective_to`); the price itself is
  only ever set through `POST`
- Money as `Decimal` with at most two decimals — serialised as a JSON string
  (`"1.50"`), never a float (docs/10 §4); a third decimal is rejected instead
  of silently rounded
- Currency normalised to upper case, defaulting to `USD`

### Endpoints

| Method | Path                    | Auth   | Role       | Success |
|--------|-------------------------|--------|------------|---------|
| GET    | `/api/v1/fares`         | no     | –          | 200     |
| GET    | `/api/v1/fares/search`  | no     | –          | 200     |
| POST   | `/api/v1/fares`         | bearer | MANAGEMENT | 201     |
| PATCH  | `/api/v1/fares/{fare_id}` | bearer | MANAGEMENT | 200   |

Responses use the envelope from `docs/05-api-specification.md` §12
(`{"data": ..., "message": "Success"}`); errors use `{"detail": "..."}`.

`GET /fares` returns the fares that apply right now; `include_history=true`
additionally returns the preserved history. `DELETE /fares/{fare_id}` and
`GET /fares/{fare_id}` answer `405`: fares are deactivated, not removed, and
read through the list and the search.

## Files created

- `app/models/fare.py`
- `app/schemas/fare.py`
- `app/services/fare_service.py`
- `app/api/v1/endpoints/fares.py`
- `alembic/versions/48aab18ee306_create_fares_table.py`
- `tests/test_fares.py`
- `docs/14-phase3-summary.md`

## Files changed

- `app/models/__init__.py` – registers `Fare` so `create_all` and autogenerate
  see it
- `app/api/v1/router.py` – mounts the fares router
- `tests/manual_api_check.py` – Phase 3 section (19 checks, 65 in total)
- `docs/04-database-specification.md` §9 – window semantics, `Numeric(10, 2)`,
  indexes, no `updated_at`
- `docs/05-api-specification.md` §7 – full contract for the four endpoints

## Tests

`pytest` → **169 passed** (134 from Phases 0–2, 35 new).

| Area | Covers |
|------|--------|
| Create | 201 with default currency and string amount, currency normalisation and rejection, explicit/`null` `effective_from`, non-positive amount, more than two decimals, extra fields, equal stops, stops from another route, unknown route/stop, auth matrix (401/403) |
| Read | public list, empty list, filters by route/origin/destination, expired fares hidden unless `include_history` |
| Supersede | old fare kept with its amount and closed exactly at the new `effective_from`, identical start time → 409, a fare already scheduled later caps the new one |
| Search | public, required params, empty result for an unpriced pair, unknown stop → 404, equal stops → 422, `route_id` filter, only the current price after a supersede |
| Update | deactivate/reactivate, expire/re-open, unknown fare → 404, empty body → 422, `amount`/`currency`/`route_id`/`effective_from` rejected → 422, window ending before it starts → 422, overlap → 409, auth matrix, `DELETE`/`GET` by id → 405 |

Tests run against a real PostgreSQL database (`waitless_test`, created
automatically); each test runs in a transaction that is rolled back.

### Manual verification

`tests/manual_api_check.py` runs **65/65 checks** over real HTTP against a
running server (`python -m uvicorn app.main:app --port 8010`): everything from
Phases 0–2 plus public fare reads, management configuration, the supersede
and history rules, the 409/422/404 paths and the OpenAPI document listing the
Phase 3 endpoints. The server was stopped afterwards; the accounts and data it
created stay in the development database under a unique suffix.

## Migration

One migration: `48aab18ee306_create_fares_table.py` (revision `48aab18ee306`,
down_revision `0d6cf8f316be`) — the `fares` table.

Verified on PostgreSQL 18.4: `upgrade head` → `downgrade` → `upgrade head`,
and `alembic check` → "No new upgrade operations detected" after the upgrade.

- `amount` `Numeric(10, 2)`, `currency` defaults to `USD`
- `ck_fares_effective_window` rejects a window that ends before it starts
- `ix_fares_route_id` (per-route list) and `ix_fares_origin_destination`
  (fare search)
- Foreign keys left unnamed, so PostgreSQL names them exactly the way
  `Base.metadata.create_all` does for the test database

## Decisions worth knowing

- **A fare is a price for a period, not a mutable field.** `POST` supersedes,
  `PATCH` only moves lifecycle fields. This is the concrete meaning of
  docs/02 rule 7 ("historical fare records must not be destroyed"); it also
  makes "the current fare" a single row by construction.
- **No database unique index on the journey triple.** Several history rows of
  one journey legitimately coexist, so overlap is enforced in the service
  layer (with `409`), backed by the window check constraint. A race could in
  theory insert two fares at the same instant; the follow-up request would
  then find the duplicate and fail its own start-time check.
- **Public reads.** `GET /fares` and `GET /fares/search` take no token, like
  routes and stops: journey searches may be anonymous (docs/04 §12).
  Configuration stays management-only — an operator cannot reprice a route.
- **`include_history` instead of an admin endpoint.** Fare history is not
  sensitive, so one public list with a flag replaces a second endpoint.
- **404 vs 422 vs 409.** Unknown ids are `404` (a mistyped query); a
  well-formed but impossible payload — stops not on the route, equal ends,
  bad amount — is `422`; a clash with existing fare state is `409`.
- **Timestamps without an offset are read as UTC** (docs/10 §3).
- **Directional fares.** A fare names an origin and a destination, so
  `A → B` and `B → A` are configured separately, and a journey needs its own
  fare rather than inheriting the route's.

## Known limitations

1. **No route-level default fare.** Every origin/destination pair needs its
   own row, so a long route costs O(n²) configurations. If that becomes
   painful, a fallback fare on the route itself can be added in a later phase.
2. **No `GET /fares/{fare_id}`** (docs/05 §7 does not define it); management
   identifies a fare through the list, using `include_history=true`.
3. **Timestamps are returned in the database session's offset** (currently
   `+02:00` on this machine) rather than `Z`. The instants are correct;
   setting `TimeZone=UTC` on the connection would make every endpoint — not
   only fares — output UTC.
4. **No fare validation endpoint** ("does this journey have a fare?") beyond
   the search itself, and no expiry notification: a fare that runs out simply
   disappears from the applicable list.
5. **Still open from Phase 1/2**: no management endpoint to list/deactivate
   users, no SQL-injection test (`docs/07` §5), no linter/formatter installed,
   CORS `*` and OpenAPI exposed everywhere, `.env` is loaded relative to the
   working directory (run everything from `backend/`), FastAPI/starlette
   deprecation warnings on Python 3.14.
6. **The development database accumulates test data**: every manual run leaves
   accounts, stops, routes, buses, assignments and fares behind under a unique
   suffix.

## Next phase

Phase 4 — Bus Location Tracking: operator location updates, active
trip/session, latest known bus location, timestamps and freshness rules
(the commuter-facing target is roughly a 20-minute update interval).

The Phase 1 limitation on user-management endpoints should still be settled
before the Flutter app needs to create operators itself.
