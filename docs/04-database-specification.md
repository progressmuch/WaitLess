# Database Specification

## 1. Database

PostgreSQL.

Use SQLAlchemy for database interaction and Alembic for migrations.

## 2. Main Entities

Initial entities:

- users
- routes
- stops
- route_stops
- buses
- operator_assignments
- fares
- trips
- bus_locations
- journey_searches

## 3. Users

Suggested fields:

```text
users
- id UUID PK
- full_name
- email UNIQUE
- phone
- password_hash
- role
- is_active
- created_at
- updated_at
```

Role values:

```text
COMMUTER
OPERATOR
MANAGEMENT
```

## 4. Routes

```text
routes
- id UUID PK
- name
- code UNIQUE
- description
- is_active
- created_at
- updated_at
```

## 5. Stops

```text
stops
- id UUID PK
- name
- latitude
- longitude
- is_active
- created_at
- updated_at
```

## 6. Route Stops

A many-to-many relationship between routes and stops with ordering.

```text
route_stops
- id UUID PK
- route_id FK
- stop_id FK
- stop_sequence
- estimated_minutes_from_start
```

Constraint:

```text
UNIQUE(route_id, stop_sequence)
```

`estimated_minutes_from_start` is nullable: a route can be laid out before its
timing data exists. When present it must never decrease along `stop_sequence`.

## 7. Buses

```text
buses
- id UUID PK
- registration_number UNIQUE
- fleet_number UNIQUE
- capacity
- is_active
- created_at
- updated_at
```

## 8. Operator Assignments

```text
operator_assignments
- id UUID PK
- operator_id FK users.id
- bus_id FK buses.id
- assigned_at
- ended_at nullable
- is_active
```

Only users with role `OPERATOR` may be assigned.

## 9. Fares

```text
fares
- id UUID PK
- route_id FK
- origin_stop_id FK
- destination_stop_id FK
- amount
- currency
- effective_from
- effective_to nullable
- is_active
- created_at
```

Historical fares should remain available.

## 10. Trips

```text
trips
- id UUID PK
- bus_id FK
- operator_id FK users.id
- route_id FK
- status
- started_at
- ended_at nullable
```

Status:

```text
ACTIVE
COMPLETED
CANCELLED
```

Business rule:
A bus must not have more than one active trip.

## 11. Bus Locations

```text
bus_locations
- id BIGSERIAL PK
- trip_id FK
- bus_id FK
- latitude
- longitude
- speed nullable
- heading nullable
- captured_at
- received_at
```

Indexes:
- `(bus_id, received_at DESC)`
- `(trip_id, received_at DESC)`

## 12. Journey Searches

```text
journey_searches
- id BIGSERIAL PK
- commuter_id FK users.id nullable
- origin_stop_id FK
- destination_stop_id FK
- route_id FK nullable
- searched_at
```

For analytics, commuter identity should not be required for aggregation.

## 13. Relationships

```text
User
 ├── Operator Assignment
 ├── Trip
 └── Journey Search

Route
 ├── Route Stops
 ├── Fares
 └── Trips

Stop
 ├── Route Stops
 └── Fares

Bus
 ├── Operator Assignment
 ├── Trips
 └── Bus Locations

Trip
 └── Bus Locations
```

## 14. Database Rules

- Use UUIDs for major business entities.
- Use timestamps in UTC.
- Add foreign keys.
- Add uniqueness constraints where needed.
- Add indexes for frequent queries.
- Never store plaintext passwords.
- Use decimal/numeric for money instead of floating-point.
- Use migrations for schema changes.
- Never manually modify production schema.

## 15. Migration Workflow

```text
Modify SQLAlchemy model
        |
        v
Create Alembic migration
        |
        v
Review migration
        |
        v
Run migration locally
        |
        v
Run tests
        |
        v
Commit migration
```
