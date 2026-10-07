# API Specification

## 1. Base URL

Development:

```text
http://localhost:8000/api/v1
```

Production URL will be configured through environment variables.

## 2. Authentication

### POST /auth/register

Creates a permitted user account.

### POST /auth/login

Returns an access token.

### GET /auth/me

Returns the authenticated user's profile.

## 3. Routes

### GET /routes

Returns active routes. Public, no token required.

Optional `is_active` query parameter; when omitted only active routes are
returned.

### GET /routes/{route_id}

Returns route details and ordered stops. Public, no token required.

A deactivated route still returns `200` with `is_active: false`; it is only
hidden from the list.

### POST /routes

Management only.

Accepts an optional `stops` array of `{stop_id, estimated_minutes_from_start}`
entries so a route can be created together with its ordered stops in one call.
A route created without stops starts inactive.

### PATCH /routes/{route_id}

Management only.

Activating a route (`is_active: true`) that has fewer than two stops returns
`409`.

### PUT /routes/{route_id}/stops

Management only.

Replaces the full ordered stop list of the route in a single transaction.
Requires at least two stops (`422` otherwise) and returns `409` when the same
stop appears twice.

### DELETE /routes/{route_id}

Not implemented: routes are deactivated rather than deleted, so this method
answers `405`. Use `PATCH /routes/{route_id}` with `{"is_active": false}`.

## 4. Stops

### GET /stops

Returns available stops. Public, no token required.

Optional `is_active` query parameter; when omitted only active stops are
returned.

### POST /stops

Management only.

### PATCH /stops/{stop_id}

Management only.

## 5. Buses

### GET /buses

Management only.

Optional `is_active` query parameter; when omitted only active buses are
returned.

### POST /buses

Management only.

`registration_number` and `fleet_number` are unique; a clash returns `409`.

### PATCH /buses/{bus_id}

Management only.

`route_id` assigns the bus to a route, or `null` clears the assignment. An
unknown route id returns `404`.

## 6. Operator Assignments

### POST /operators/{operator_id}/assignments

Management only.

Assigns a bus to an operator. Returns `409` when the target user is not an
`OPERATOR`, when that operator already has an active assignment, or when the
bus already has an active operator. The route an operator sees comes from the
assigned bus (`buses.route_id`).

### GET /operators/me/assignment

Operator only.

Returns the active assignment together with its bus and that bus's route.
`404` when the operator has no active assignment.

### DELETE /operators/{operator_id}/assignments

Management only.

Ends the operator's active assignment (`ended_at` set, `is_active: false`);
the record is kept as history. `404` when there is no active assignment. This
is the action that resolves the `409` returned by POST.

## 7. Fares

### GET /fares

Returns applicable fares.

### GET /fares/search

Example query:

```text
/fares/search?origin_stop_id=...&destination_stop_id=...
```

### POST /fares

Management only.

### PATCH /fares/{fare_id}

Management only.

## 8. Trips

### POST /trips/start

Operator only.

Request concept:

```json
{
  "bus_id": "uuid",
  "route_id": "uuid"
}
```

The backend must verify operator authorization.

### POST /trips/{trip_id}/end

Operator only.

### GET /trips/active

Returns active trips relevant to a route.

## 9. Location

### POST /trips/{trip_id}/location

Operator only.

Example:

```json
{
  "latitude": -17.8252,
  "longitude": 31.0335,
  "speed": 35.5,
  "heading": 90,
  "captured_at": "2026-10-04T18:00:00Z"
}
```

The backend must:
- Verify authentication
- Verify operator owns/controls the active trip
- Validate coordinates
- Store the location
- Record server receipt time

### GET /trips/{trip_id}/location/latest

Returns:
- latitude
- longitude
- captured_at
- received_at
- freshness status

## 10. Commuter Journey Search

### GET /journeys/search

Parameters:

```text
origin_stop_id
destination_stop_id
```

Response should contain:
- route
- fare
- active bus
- latest location
- last updated time
- ETA

## 11. Analytics

Management only.

### GET /analytics/overview

Returns high-level demand statistics.

### GET /analytics/routes

Returns route popularity.

### GET /analytics/destinations

Returns destination demand.

### GET /analytics/origin-destination

Returns popular travel pairs.

### GET /analytics/demand-by-time

Returns demand grouped by time period.

## 12. API Response Principles

Use consistent responses.

Success example:

```json
{
  "data": {},
  "message": "Success"
}
```

Validation error:

```json
{
  "detail": "Invalid request"
}
```

Do not expose:
- password hashes
- internal secrets
- database errors
- stack traces

## 13. HTTP Status Codes

Use:
- `200` successful read/update
- `201` successful creation
- `204` successful deletion/deactivation where appropriate
- `400` invalid request
- `401` unauthenticated
- `403` unauthorized role/action
- `404` resource not found
- `409` business conflict
- `422` validation error
- `500` unexpected server error

## 14. API Development Rule

Do not implement every endpoint at once.

Implement endpoints according to the roadmap phase and test them before proceeding.
