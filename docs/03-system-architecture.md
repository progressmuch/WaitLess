# System Architecture

## 1. Architecture Style

Use a modular client-server architecture.

```text
+----------------------+
| Flutter Mobile App   |
|----------------------|
| Commuter UI          |
| Operator UI          |
| Management UI        |
+----------+-----------+
           |
         HTTPS
           |
           v
+----------------------+
| FastAPI Backend      |
|----------------------|
| Auth Module          |
| User Module          |
| Route Module         |
| Bus Module           |
| Fare Module          |
| Location Module      |
| ETA Module           |
| Analytics Module     |
+----------+-----------+
           |
           v
+----------------------+
| PostgreSQL           |
+----------------------+
```

## 2. Backend Layers

Recommended structure:

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── exceptions.py
│   ├── db/
│   │   ├── session.py
│   │   └── base.py
│   ├── models/
│   ├── schemas/
│   ├── api/
│   │   └── v1/
│   ├── services/
│   └── utils/
├── alembic/
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

## 3. API Versioning

Use:

```text
/api/v1/
```

This makes future breaking API changes easier to manage.

## 4. Authentication

Use:
- Password hashing
- JWT access tokens
- Role claims or role lookup
- Dependency-based authorization in FastAPI

Do not place sensitive information inside JWT payloads.

## 5. Location Architecture

The operator mobile client obtains GPS coordinates.

```text
Operator Flutter App
       |
       | latitude, longitude, timestamp
       v
FastAPI
       |
       v
Validate operator + active trip
       |
       v
PostgreSQL
       |
       v
Commuter request
       |
       v
Latest bus location + timestamp + ETA
```

## 6. Location Update Strategy

The system should distinguish:

- `location_received_at`: when backend received the update
- `captured_at`: when device captured the location
- `latitude`
- `longitude`
- optional `speed`
- optional `heading`

For the initial version, store the latest location and historical records.

The commuter application can poll the API approximately every 20 minutes according to the initial product requirement. A future version can use WebSockets or push-based updates for more real-time behavior.

## 7. ETA Strategy

Initial ETA:

```text
ETA = estimated_distance / estimated_speed
```

The implementation should prefer route-aware distance over straight-line distance when route geometry is available.

Future versions may introduce:
- traffic data
- historical route speeds
- machine learning
- map-routing services

## 8. Analytics Architecture

Record journey/search events without unnecessarily storing sensitive information.

Example:

```text
origin_stop_id
destination_stop_id
route_id
searched_at
```

Management analytics can aggregate these records.

## 9. Separation of Responsibilities

FastAPI:
- Authentication
- Authorization
- Business rules
- Data validation
- Database operations
- Location processing
- ETA calculation
- Analytics

Flutter:
- UI
- Local state
- Authentication token handling
- GPS acquisition for operator
- API communication
- User interaction
- Presentation of results

PostgreSQL:
- Persistent storage
- Relationships
- Constraints
- Indexing
- Analytics source data

## 10. Important Architectural Decision

Do not make Flutter directly connect to PostgreSQL.

Correct:

```text
Flutter -> FastAPI -> PostgreSQL
```

Incorrect:

```text
Flutter -> PostgreSQL
```
