# Product Requirements Document

## 1. Product Goal

Provide commuters with reliable, understandable and timely information about public transport routes, fares and active buses while giving transport management useful demand statistics.

## 2. Functional Requirements

### FR-01 Authentication

The system shall support:
- Registration for permitted users
- Login
- Logout/client-side token removal
- Password hashing
- JWT authentication
- Role-based access control

Roles:
- `COMMUTER`
- `OPERATOR`
- `MANAGEMENT`

### FR-02 Commuter Journey Search

A commuter shall be able to:
- Select origin
- Select destination
- Search available routes
- View fare
- View active buses serving the route
- View latest bus location information
- View estimated arrival time

### FR-03 Route Management

Management shall be able to:
- Create route
- Update route
- Activate/deactivate route
- Define ordered stops
- Set route metadata

A route should have a clear ordered sequence of stops.

### FR-04 Bus Management

Management shall be able to:
- Register bus
- Assign bus to operator
- Assign bus to route
- Activate/deactivate bus

### FR-05 Operator Trip Management

An operator shall be able to:
- View assigned bus
- View assigned route
- Start trip
- Stop trip
- Send location updates

The backend must validate that the operator is authorized to operate the selected bus/trip.

### FR-06 Location Tracking

The system shall:
- Receive latitude and longitude
- Store timestamp
- Associate location with an active bus/trip
- Provide latest valid location to authorized clients
- Indicate when location information is stale

The commuter-facing requirement is approximately a 20-minute update interval. The system should display the actual `last_updated_at` time instead of claiming that a bus is live when the data is stale.

### FR-07 ETA

The system shall estimate:
- Approximate distance from bus to relevant commuter stop
- Estimated time to arrival

The initial implementation may use:
- Route distance
- Current/estimated speed
- Historical/basic speed assumptions

The system must clearly distinguish an estimate from a guaranteed arrival time.

### FR-08 Fare Management

Management shall be able to configure fares.

Commuters shall see the fare associated with their selected journey.

Fare history should be preserved rather than silently overwriting historical values.

### FR-09 Analytics

Management shall be able to view:
- Number of journey searches
- Popular origins
- Popular destinations
- Popular origin-destination pairs
- Popular routes
- Demand by date
- Demand by time period

Analytics should preferably use aggregated data.

## 3. Non-Functional Requirements

### NFR-01 Performance

Common read endpoints should respond quickly under normal load.

### NFR-02 Security

The system must:
- Hash passwords
- Protect private endpoints
- Validate roles
- Validate input
- Avoid exposing passwords
- Avoid exposing unnecessary personal data
- Use HTTPS in production

### NFR-03 Reliability

The API should fail gracefully when:
- Database is unavailable
- Location data is stale
- A bus has no active trip
- An invalid route is requested

### NFR-04 Maintainability

Backend code should use clear modules and separation of concerns:
- API/routes
- Schemas
- Services
- Models
- Repositories/data access where useful
- Configuration

### NFR-05 Scalability

The design should allow:
- More buses
- More routes
- More commuters
- Multiple transport operators
- Future mobile/web clients

## 4. Business Rules

1. A user has one primary system role.
2. An operator may only update locations for an authorized bus/trip.
3. A bus should have at most one active trip at a time.
4. A trip must belong to a valid route.
5. A route must have ordered stops.
6. A fare must apply to a defined route/journey context.
7. Historical fare records must not be destroyed when a new fare is configured.
8. Stale bus locations must be clearly marked.
9. Management analytics should avoid unnecessary personally identifiable information.
10. ETA is an estimate, not a guarantee.
