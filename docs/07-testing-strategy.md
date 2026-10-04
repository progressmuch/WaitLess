# Testing Strategy

## 1. Goal

Every development phase must be tested before the next phase starts.

## 2. Unit Tests

Test:
- Password hashing
- JWT logic
- Role checks
- Fare calculations
- ETA calculations
- Location freshness
- Route matching
- Business rules

## 3. API Tests

Test:
- Registration
- Login
- Protected endpoints
- Role restrictions
- Route CRUD
- Bus CRUD
- Trip start/end
- Location update
- Latest location retrieval
- Journey search
- Analytics

## 4. Database Tests

Verify:
- Foreign keys
- Unique constraints
- Active trip constraints
- Fare history
- Route-stop ordering

## 5. Security Tests

Verify:
- Wrong password rejected
- Expired token rejected
- Missing token rejected
- Commuter cannot access management endpoints
- Operator cannot update another operator's trip
- Invalid coordinates rejected
- SQL injection is prevented through parameterized ORM/database operations

## 6. Location Tests

Test:
- Valid coordinates
- Invalid latitude
- Invalid longitude
- Stale location
- Location for inactive trip
- Unauthorized operator
- Multiple updates
- Latest location selection

## 7. ETA Tests

Test:
- Normal distance/speed
- Zero/unknown speed
- Missing location
- Stale location
- Destination already reached
- Invalid route

## 8. Phase Completion Rule

A phase is complete only when:
- Automated tests pass
- Manual API checks pass
- No known critical errors remain
- Documentation reflects the implementation
