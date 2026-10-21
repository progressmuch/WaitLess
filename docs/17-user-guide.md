# WaitLess User Guide

How the whole system works, and exactly what each kind of user does with it.

> Every example in this guide was executed against a running server and its
> real response checked, so the shapes and status codes shown here are the
> ones the API actually returns.

- **Base URL (production):** `https://waitless-api-dl75.onrender.com`
- **API prefix:** `/api/v1`
- **Interactive API docs (Swagger UI):** `https://waitless-api-dl75.onrender.com/docs`
- **Health check:** `https://waitless-api-dl75.onrender.com/health`

Every request returns the same envelope, so you can parse one shape:

```json
{ "data": { }, "message": "Success" }
```

Errors always use `detail`:

```json
{ "detail": "Route not found" }
```

---

## 1. The three roles at a glance

| Role | What they do | Can they see live bus positions? |
|---|---|---|
| **MANAGEMENT** | Owns the network: stops, routes, buses, fares, staff accounts, and the analytics | Yes |
| **OPERATOR** | Drives a bus: gets a bus assigned, runs a trip, streams GPS locations | Yes |
| **COMMUTER** | Passengers: browse the network, search a journey, see the price and ETA | Yes (public) |

A person has exactly one role, and **nobody can promote themselves**. Public
registration always produces a `COMMUTER`. The only way to create an
`OPERATOR` or `MANAGEMENT` account is for an existing management user to create
it, or for the one-time bootstrap script to run.

### How the pieces fit together

```text
          MANAGEMENT                    OPERATOR                    COMMUTER
        builds the network              drives a bus              looks for a bus
               |                             |                          |
      stops -> routes -> buses        trips + GPS points        journey search
               |                             |                          |
               +----------- trips (active) ---+--------------------------+
                                      |
                              bus_locations
                                      |
                    commuter sees: position, freshness, ETA, price
```

The chain that makes it work:

1. Management creates **stops** (named points with GPS coordinates).
2. Management creates **routes** — an ordered list of at least two stops.
3. Management registers **buses** and puts them on a route.
4. Management creates **operator accounts** and **assigns a bus** to each.
5. An operator starts a **trip** and posts **location updates** while driving.
6. A commuter **searches a journey** and sees the bus, its last position, how
   fresh that position is, an ETA, and the fare.

Nothing works out of order: a route needs stops before it can be published, a
bus needs a route, an operator needs an assigned bus before starting a trip, and
an ETA needs at least one location update.

---

## 2. Part 1 — Management

Management is the operator of the transport network. Here is the full job, in
the order you should do it the first time.

### 2.1 Get a MANAGEMENT account

The very first one cannot be created through the API, because creating
management accounts requires management credentials. Run the bootstrap script
once:

```powershell
cd backend
..\WaitLessVenv\Scripts\python.exe scripts/create_staff.py `
  --database-url "postgresql://postgres.REF:PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres?sslmode=require" `
  --email "admin@example.com" --password "YourStrongPassword!" --role MANAGEMENT
```

Every later management account is created through the API (see 2.5).

### 2.2 Sign in

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"YourStrongPassword!"}'
```

```json
{
  "data": { "access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer", "expires_in": 1800 },
  "message": "Login successful"
}
```

`expires_in` is 1800 seconds (30 minutes). Put the token in a variable and
send it on every protected call:

```bash
export TOKEN="eyJhbGciOiJIUzI1NiIs..."
curl https://waitless-api-dl75.onrender.com/api/v1/routes \
  -H "Authorization: Bearer $TOKEN"
```

The token only carries the user id. Your role and active flag are re-read from
the database on every request, so deactivating an account invalidates its
tokens immediately.

### 2.3 Manage stops

A stop is a named place with WGS84 coordinates. Everything else hangs off
stops.

**Create a stop**

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/stops \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Harare Central","latitude":-17.8252,"longitude":31.0335}'
```

```json
{ "data": { "id": "3f1c...", "name": "Harare Central", "latitude": -17.8252,
            "longitude": 31.0335, "is_active": true, "created_at": "...",
            "updated_at": "..." }, "message": "Stop created successfully" }
```

Keep the returned `id` — you need it everywhere else.

**List stops** (public, no token needed)

```bash
curl https://waitless-api-dl75.onrender.com/api/v1/stops
```

Only **active** stops are listed by default. Pass `?is_active=false` to see
the ones you have switched off.

**Update a stop** — only the fields you send are changed

```bash
curl -X PATCH https://waitless-api-dl75.onrender.com/api/v1/stops/<stop_id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Harare Central Bus Terminal"}'
```

**Deactivate a stop** — there is no DELETE. Stops stay in the database because
routes still point at them.

```bash
curl -X PATCH .../api/v1/stops/<stop_id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"is_active":false}'
```

> Latitude must be −90…90 and longitude −180…180, or you get a `422`.

### 2.4 Manage routes

A route is an **ordered** list of stops. The order is what makes it a route.

**Create a route with its stops** (one call, recommended)

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/routes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Harare - Chitungwiza",
    "code": "HR-CHI",
    "description": "Main corridor",
    "stops": [
      { "stop_id": "<stop_a>", "estimated_minutes_from_start": 0 },
      { "stop_id": "<stop_b>", "estimated_minutes_from_start": 15 },
      { "stop_id": "<stop_c>", "estimated_minutes_from_start": 35 }
    ]
  }'
```

Rules the system enforces for you:

- The list order becomes the stop order — first stop first, like a passenger
  reads it.
- **At least two stops** are required, or you get a `422`.
- The same stop may not appear twice (`422`).
- `estimated_minutes_from_start` must never decrease along the route (`422`).
  Leave it out entirely if you do not know the timings yet.
- `code` is upper-cased for you (`hr-chi` becomes `HR-CHI`) and must be unique
  — a clash is a `409`.
- **A route created with stops is active immediately.** A route created
  *without* `stops` is a draft and starts inactive.

**Replace the whole stop list** (use this to reorder or add stops later)

```bash
curl -X PUT https://waitless-api-dl75.onrender.com/api/v1/routes/<route_id>/stops \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"stops":[{"stop_id":"<stop_a>"},{"stop_id":"<stop_b>"},{"stop_id":"<stop_c>"}]}'
```

This replaces everything in one transaction, so the list never ends up
half-updated and the ordering never has gaps.

**Publish a draft route** (only possible once it has 2+ stops)

```bash
curl -X PATCH .../api/v1/routes/<route_id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"is_active":true}'
```

Activating a route with fewer than two stops returns a `409`.

**Read a route with its ordered stops** (public)

```bash
curl https://waitless-api-dl75.onrender.com/api/v1/routes/<route_id>
```

```json
{ "data": { "id": "9a2...", "name": "Harare - Chitungwiza", "code": "HR-CHI",
            "is_active": true,
            "stops": [ { "stop_sequence": 1, "stop_id": "...",
                         "estimated_minutes_from_start": 0,
                         "stop": { "id": "...", "name": "Harare Central",
                                   "latitude": -17.8252, "longitude": 31.0335,
                                   "is_active": true } } ] },
  "message": "Success" }
```

### 2.5 Manage people

**Create an operator account**

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/auth/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Brian Driver","email":"brian@example.com","password":"Password123!","role":"OPERATOR"}'
```

`role` must be `OPERATOR` or `MANAGEMENT`. Use `MANAGEMENT` for another
manager. The response never contains the password hash.

Password rules: 8–128 characters. Emails are trimmed and lower-cased, so
`Brian@Example.com` and `brian@example.com` are the same account.

### 2.6 Manage the fleet

**Register a bus**

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/buses \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"registration_number":"ABC 1234","fleet_number":"BUS-001","capacity":60,"route_id":"<route_id>"}'
```

- `registration_number` and `fleet_number` are upper-cased and must be unique
  (`409` on a clash).
- `capacity` is passenger seats, 1–1000.
- `route_id` is optional — a bus may join the fleet before it has a route.

**List buses** (management only — the fleet is operational data)

```bash
curl https://waitless-api-dl75.onrender.com/api/v1/buses \
  -H "Authorization: Bearer $TOKEN"
```

**Update a bus** — `route_id: null` removes it from its route

```bash
curl -X PATCH .../api/v1/buses/<bus_id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"route_id":"<new_route_id>"}'
```

### 2.7 Assign a bus to an operator

Operators are identified by **email address**, so you never need to look up a
user id first.

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/operators/brian@example.com/assignments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"bus_id":"<bus_id>"}'
```

```json
{ "data": { "id": "7c4...", "operator_id": "...", "bus_id": "...",
            "assigned_at": "2026-10-21T08:00:00Z", "ended_at": null,
            "is_active": true,
            "bus": { "id": "...", "registration_number": "ABC 1234",
                     "fleet_number": "BUS-001", "capacity": 60,
                     "is_active": true,
                     "route": { "id": "...", "name": "Harare - Chitungwiza",
                                "code": "HR-CHI", "is_active": true } } },
  "message": "Bus assigned successfully" }
```

The response nests the bus **and that bus's route** — this is exactly what the
operator will see.

**Why an assignment can fail with `409`:**

| Message | Meaning | Fix |
|---|---|---|
| Operator already has an active assignment | That operator still holds another bus | End the old assignment first |
| Bus already has an active operator | Somebody else is driving that bus | End their assignment first |
| Only users with role OPERATOR can be assigned | The email belongs to a commuter or manager | Check the role |

**Release a bus** — this *ends* the assignment; it does not delete the record,
which stays as history.

```bash
curl -X DELETE https://waitless-api-dl75.onrender.com/api/v1/operators/brian@example.com/assignments \
  -H "Authorization: Bearer $TOKEN"
```

### 2.8 Manage fares

A fare always names a **whole journey**: one route plus both ends of the trip.

**Set a price**

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/fares \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "route_id": "<route_id>",
    "origin_stop_id": "<stop_a>",
    "destination_stop_id": "<stop_c>",
    "amount": "1.50",
    "currency": "USD"
  }'
```

- `amount` must be positive with at most two decimals. Send it as a string
  (`"1.50"`) — the API returns money as a string too, never as a float.
- `currency` is a 3-letter code, default `USD`.
- Both stops must be **on that route** and must be different, or you get a
  `422`.
- An unknown route or stop gives a `404`.

**Changing a price never overwrites the old one.** Send a new `POST /fares`:
the previous fare is automatically closed at the moment the new one starts and
becomes history. Two active fares of the same journey can never cover the same
instant — starting one where another already starts is a `409`.

**Adjust the lifecycle** (deactivate, or set an end date)

```bash
curl -X PATCH .../api/v1/fares/<fare_id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"is_active":false}'
```

Only `is_active` and `effective_to` may be patched. Sending `amount` is
rejected with a `422` on purpose, so the price history is never destroyed.

**Read fares**

```bash
# what applies right now (public)
curl https://waitless-api-dl75.onrender.com/api/v1/fares

# the full history, including superseded and expired prices
curl "https://waitless-api-dl75.onrender.com/api/v1/fares?include_history=true"

# the price for one stop pair (public)
curl "https://waitless-api-dl75.onrender.com/api/v1/fares/search?origin_stop_id=<a>&destination_stop_id=<b>"
```

### 2.9 Watch operations

**See every trip currently running** (public)

```bash
curl https://waitless-api-dl75.onrender.com/api/v1/trips/active
curl "https://waitless-api-dl75.onrender.com/api/v1/trips/active?route_id=<route_id>"
```

**See where a bus is right now** (public)

```bash
curl https://waitless-api-dl75.onrender.com/api/v1/trips/<trip_id>/location/latest
```

```json
{ "data": { "id": 812, "trip_id": "...", "bus_id": "...",
            "latitude": -17.83, "longitude": 31.04, "speed": 35.5,
            "heading": 90,
            "captured_at": "2026-10-21T08:15:00Z",
            "received_at": "2026-10-21T08:15:01Z",
            "freshness_status": "fresh" },
  "message": "Success" }
```

**`freshness_status` is the single most important field in the whole system.**
It tells you how much to trust the position:

| Value | Meaning |
|---|---|
| `fresh` | Captured within the last 20 minutes. Trust it. |
| `stale` | 20–40 minutes old. The bus may have moved on. |
| `very_stale` | Over 40 minutes old. Do not trust it — the trip is probably dead. |
| `unknown` | No location has ever been posted for this trip. |

### 2.10 Read analytics

Five management-only endpoints describe what passengers are asking for:

```bash
curl .../api/v1/analytics/overview           -H "Authorization: Bearer $TOKEN"
curl .../api/v1/analytics/routes             -H "Authorization: Bearer $TOKEN"
curl .../api/v1/analytics/destinations        -H "Authorization: Bearer $TOKEN"
curl .../api/v1/analytics/origin-destination  -H "Authorization: Bearer $TOKEN"
curl .../api/v1/analytics/demand-by-time      -H "Authorization: Bearer $TOKEN"
```

> ⚠️ **These are currently always empty.** The `journey_searches` table is
> never written to, so every counter reads `0` no matter how many people
> search. See [Known gaps](#3-known-gaps-and-limitations).

---

## 3. Part 2 — Operator

An operator drives a bus. Their whole job is: check the assignment, start a
trip, keep posting locations, end the trip.

### 3.1 Sign in

Same endpoint as everyone else, but with an operator account:

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"brian@example.com","password":"Password123!"}'
```

### 3.2 Check your assignment

**This is the first thing you should do.** Without an active assignment you
cannot start a trip.

```bash
curl https://waitless-api-dl75.onrender.com/api/v1/operators/me/assignment \
  -H "Authorization: Bearer $OP_TOKEN"
```

```json
{ "data": { "id": "7c4...", "operator_id": "...", "bus_id": "...",
            "assigned_at": "2026-10-21T08:00:00Z", "ended_at": null,
            "is_active": true,
            "bus": { "id": "...", "registration_number": "ABC 1234",
                     "fleet_number": "BUS-001", "capacity": 60,
                     "is_active": true,
                     "route": { "id": "...", "name": "Harare - Chitungwiza",
                                "code": "HR-CHI", "is_active": true } } },
  "message": "Success" }
```

You get the bus **and the route you are running**. Note the `route.id` — you
need it to start the trip.

If you get a `404`, management has not given you a bus yet. Ask them.

### 3.3 Start a trip

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/trips/start \
  -H "Authorization: Bearer $OP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"bus_id":"<bus_id>","route_id":"<route_id>"}'
```

```json
{ "data": { "id": "e91...", "bus_id": "...", "operator_id": "...",
            "route_id": "...", "status": "ACTIVE",
            "started_at": "2026-10-21T08:00:00Z", "ended_at": null },
  "message": "Trip started" }
```

Both ids come from your assignment response. The system checks that:

- the bus exists and is active (`404` / `409`),
- the route exists and is active (`404` / `409`),
- **the bus is the one assigned to you** (`403` — "Operator is not assigned to
  this bus"),
- the bus has no other active trip (`409`),
- you have no other active trip (`409`).

**Keep the `trip.id` — every location update needs it.**

### 3.4 Post location updates

This is what makes the system live. Post one every few seconds while moving,
and at least every couple of minutes while stopped.

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/trips/<trip_id>/location \
  -H "Authorization: Bearer $OP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": -17.8252,
    "longitude": 31.0335,
    "speed": 35.5,
    "heading": 90,
    "captured_at": "2026-10-21T08:15:00Z"
  }'
```

| Field | Required | Notes |
|---|---|---|
| `latitude` | yes | −90 … 90 |
| `longitude` | yes | −180 … 180 |
| `speed` | no | km/h, 0 … 200. This drives the ETA — send it. |
| `heading` | no | degrees 0 … 359 |
| `captured_at` | no | When the phone took the reading. Omit and the server uses the current time. A timestamp without a timezone is treated as UTC. |

The server records its own `received_at` next to your `captured_at`. The gap
between the two is what the freshness status measures — a phone that was
offline for an hour shows up immediately.

```json
{ "data": { "id": 812, "trip_id": "...", "bus_id": "...",
            "latitude": -17.83, "longitude": 31.04, "speed": 35.5,
            "heading": 90,
            "captured_at": "2026-10-21T08:15:00Z",
            "received_at": "2026-10-21T08:15:01Z",
            "freshness_status": null },
  "message": "Location recorded" }
```

> `freshness_status` is `null` **in this response only**. The freshness of a
> position is computed when you read it back, so ask
> `GET /trips/{trip_id}/location/latest` (or a journey search) for it.

Only the operator who owns the trip may post for it (`403` otherwise).

> **A good habit:** send `captured_at` from the GPS fix, not the moment you
> built the request. That is what makes "the bus has not moved in 40 minutes"
> detectable.

### 3.5 End the trip

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/trips/<trip_id>/end \
  -H "Authorization: Bearer $OP_TOKEN"
```

The trip becomes `COMPLETED` and `ended_at` is stamped. After this, location
updates for that trip are refused.

### 3.6 Operator troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| `409 Operator has no active assignment` | Management has not given you a bus | Ask management to assign one |
| `403 Operator is not assigned to this bus` | You are posting for somebody else's bus | Check your `bus_id` |
| `409 Bus already has an active trip` | The trip was never ended | End it first |
| `409 Operator already has an active trip` | You started twice | End the old trip |
| `404 Active trip not found` | The trip id is wrong, or it was already ended | Use `GET /trips/active` to find the live one |
| `403 Operator does not control this trip` | Not your trip | Check the trip id |
| `401 Not authenticated` | Token missing or expired | Log in again (tokens last 30 minutes) |

---

## 4. Part 3 — Commuter

A commuter wants one thing: *where is my bus, when does it arrive, and what
does it cost?*

**None of this needs an account.** The public endpoints below work with no
token at all.

### 4.1 Browse the network

```bash
# all active stops
curl https://waitless-api-dl75.onrender.com/api/v1/stops

# all active routes
curl https://waitless-api-dl75.onrender.com/api/v1/routes

# one route with its stops in order
curl https://waitless-api-dl75.onrender.com/api/v1/routes/<route_id>
```

### 4.2 Search a journey

```bash
curl "https://waitless-api-dl75.onrender.com/api/v1/journeys/search?origin_stop_id=<stop_a>&destination_stop_id=<stop_c>"
```

```json
{ "data": { "results": [
      { "route": { "id": "...", "name": "Harare - Chitungwiza", "code": "HR-CHI" },
        "fare": { "amount": "1.50", "currency": "USD" },
        "active_bus": { "id": "...", "registration_number": "ABC 1234",
                        "fleet_number": "BUS-001" },
        "trip_id": "e91...",
        "latest_location": { "latitude": -17.83, "longitude": 31.04,
                             "captured_at": "2026-10-21T08:15:00Z",
                             "received_at": "2026-10-21T08:15:01Z" },
        "last_updated_time": "2026-10-21T08:15:01Z",
        "eta_minutes": 12,
        "freshness_status": "fresh" } ] },
  "message": "Success" }
```

How to read it:

- **`results`** — one entry per route that serves both stops *and* has a bus
  currently running on it. An empty list means: no bus is running that route
  right now.
- **`eta_minutes`** — minutes until the bus reaches your destination. `null`
  when the position is too old to trust.
- **`freshness_status`** — how much to trust the position. Show a warning when
  it is `stale`, and "bus location unknown" when it is `very_stale` or
  `unknown`.
- **`fare`** — `null` when no price has been configured for that stop pair.

Add `&route_id=<route_id>` to restrict the search to one route.

### 4.3 Check the price

```bash
curl "https://waitless-api-dl75.onrender.com/api/v1/fares/search?origin_stop_id=<stop_a>&destination_stop_id=<stop_c>"
```

Returns `200` with an empty list when no fare is configured yet, `404` for an
unknown stop, and `422` if you pass the same stop twice.

### 4.4 Optional: an account

Registration is optional and only creates a `COMMUTER`:

```bash
curl -X POST https://waitless-api-dl75.onrender.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Alice Commuter","email":"alice@example.com","password":"Password123!"}'
```

The role is always `COMMUTER` — the field is not even accepted in the
payload, so trying to set it gives a `422` instead of a silent success.

---

## 5. API reference by role

**Public — no token**

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service alive |
| GET | `/api/v1/routes` | List active routes |
| GET | `/api/v1/routes/{route_id}` | Route with ordered stops |
| GET | `/api/v1/stops` | List active stops |
| GET | `/api/v1/fares` | Fares that apply now |
| GET | `/api/v1/fares/search` | Fare for a stop pair |
| GET | `/api/v1/trips/active` | Trips currently running |
| GET | `/api/v1/trips/{trip_id}/location/latest` | Last known position |
| GET | `/api/v1/journeys/search` | Journey, ETA and fare |
| POST | `/api/v1/auth/register` | Create a commuter account |
| POST | `/api/v1/auth/login` | Get a token |

**Any authenticated user**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/auth/me` | Own profile |

**OPERATOR only**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/operators/me/assignment` | My bus and route |
| POST | `/api/v1/trips/start` | Start a trip |
| POST | `/api/v1/trips/{trip_id}/location` | Post a position |
| POST | `/api/v1/trips/{trip_id}/end` | End a trip |

**MANAGEMENT only**

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/auth/users` | Create an operator or manager |
| POST/PATCH | `/api/v1/stops`, `/api/v1/stops/{id}` | Manage stops |
| POST/PATCH | `/api/v1/routes`, `/api/v1/routes/{id}` | Manage routes |
| PUT | `/api/v1/routes/{id}/stops` | Replace the ordered stop list |
| GET/POST/PATCH | `/api/v1/buses`, `/api/v1/buses/{id}` | Manage the fleet |
| POST | `/api/v1/operators/{email}/assignments` | Assign a bus |
| DELETE | `/api/v1/operators/{email}/assignments` | End an assignment |
| POST/PATCH | `/api/v1/fares`, `/api/v1/fares/{id}` | Manage prices |
| GET | `/api/v1/analytics/*` | Demand analytics |

---

## 6. Status codes

| Code | Meaning | Typical cause |
|---|---|---|
| `200` | Read or update succeeded | |
| `201` | Something was created | |
| `400` | Malformed request | |
| `401` | Not authenticated | Missing or expired token |
| `403` | Wrong role, or not your trip | |
| `404` | No such record | Wrong id, or an endpoint that does not exist |
| `405` | Method not allowed | Tried to DELETE a route or fare |
| `409` | Business conflict | Duplicate code, double assignment, active trip exists |
| `422` | Validation failed | Bad coordinates, fewer than two stops, extra fields |
| `500` | Unexpected server error | Check the Render logs |

---

## 7. Known gaps and limitations

Being straight about what does not work yet.

| # | Gap | Impact | Where |
|---|---|---|---|
| 1 | **Journey searches are never recorded.** The `journey_searches` table is never written to. | All five analytics endpoints always return zero/empty, no matter how many passengers search. | `app/services/journey_service.py` |
| 2 | **The ETA is a straight-line estimate.** It is the distance from the bus's *last known position* to your destination stop, divided by the bus's speed (or 30 km/h if unknown). It does not follow the route. | The ETA is optimistic when the bus must still travel to your *origin* first, and when the road is not a straight line. | `app/services/eta_service.py` |
| 3 | **A very stale position produces no ETA** (`null`), and a `very_stale` bus is still shown. | Commuters must be taught to read `freshness_status`, not just the ETA. | `journey_service.py` |
| 4 | **Journey search does not check stop order or route activity.** It matches any route containing both stops, even a deactivated one, and it does not verify the origin comes before the destination. | A search may offer a journey that runs the wrong way. | `journey_service.py` |
| 5 | **Tokens last 30 minutes and cannot be refreshed.** There is no refresh token. | The app must send the user back to the login screen. | `app/core/security.py` |
| 6 | **There is no user list endpoint.** | Management has to know the email address of the person they want to assign a bus to. | `app/api/v1/endpoints/auth.py` |
| 7 | **Nothing is ever deleted.** Routes, stops, buses and fares are deactivated with `PATCH {"is_active": false}`; a `DELETE` answers `405`. | Intentional — it preserves history — but surprising the first time. | API design |
| 8 | **There is no `GET /fares/{fare_id}`.** | Read fares through the list or the search. | `app/api/v1/endpoints/fares.py` |
| 9 | **The free Render tier sleeps.** After 15 minutes idle the service spins down and the next request takes 30–60 seconds. | Clients need a long timeout and a loading state, or the first request after a break looks like a crash. | Render |
| 10 | **Vehicle location and trips are public.** | Anyone can read live bus positions without a token. Fine for passengers, worth knowing if you ever add staff-only detail. | `app/api/v1/endpoints/trips.py` |

> **Fixed on 2026-10-21:** journey search used to return the coordinates as
> JSON *strings* (`"-17.830000"`) while every other endpoint returned
> numbers, because the columns are `Numeric` and the response was built
> without the schema layer. The coordinates are now numbers everywhere, and
> a regression test pins that down.

---

## 8. Glossary

| Term | Meaning |
|---|---|
| **Stop** | A named place with GPS coordinates |
| **Route** | An ordered list of two or more stops, identified by a unique code |
| **Bus** | A vehicle with a registration number, fleet number and seat capacity |
| **Assignment** | The link between an operator and a bus, with a start and end time |
| **Trip** | One journey of one bus on one route, from `ACTIVE` to `COMPLETED` |
| **Location** | One GPS point: where the bus was, when it was captured, when it arrived |
| **Freshness** | How old a location is: `fresh` (≤20 min), `stale` (≤40 min), `very_stale`, `unknown` |
| **ETA** | Estimated minutes until the bus reaches the destination |
| **Fare** | The price of one journey: a route plus an origin and a destination stop |
| **Superseded fare** | An old price, closed off when a new one started, kept as history |

---

## 9. Quick start: from nothing to a live bus

The shortest path to seeing the whole system work, in order.

```bash
BASE=https://waitless-api-dl75.onrender.com/api/v1
```

1. **Log in as management**, keep the token in `$TOKEN`.
2. **Create two stops** → `POST /stops` ×2, note the ids.
3. **Create a route** → `POST /routes` with both stops in the `stops` array.
4. **Register a bus** → `POST /buses` with the route id.
5. **Create an operator** → `POST /auth/users` with `"role":"OPERATOR"`.
6. **Assign the bus** → `POST /operators/<operator-email>/assignments`.
7. **Log in as the operator** → `$OP_TOKEN`.
8. **Check the assignment** → `GET /operators/me/assignment`, note `bus_id`
   and `route.id`.
9. **Start the trip** → `POST /trips/start`.
10. **Post a location** → `POST /trips/<trip_id>/location`.
11. **Search as a commuter** → `GET /journeys/search?origin_stop_id=…&destination_stop_id=…`
    and watch `eta_minutes` and `freshness_status` appear.
12. **End the trip** → `POST /trips/<trip_id>/end`.
