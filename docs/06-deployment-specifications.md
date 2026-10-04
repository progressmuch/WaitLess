# Deployment Specification

## 1. Environments

Use three conceptual environments:

```text
Development
Testing
Production
```

## 2. Development

Local stack:

```text
Flutter
   |
FastAPI localhost
   |
PostgreSQL local
```

Use `.env` locally.

Never commit `.env`.

Create:

```text
.env.example
```

## 3. Required Environment Variables

Example:

```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/transport_db
JWT_SECRET_KEY=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

Production secrets must be supplied by the hosting platform's secret/environment-variable system.

## 4. Database Deployment

Production PostgreSQL should:
- Use encrypted connections where supported
- Have regular backups
- Use strong credentials
- Restrict public access where possible
- Run Alembic migrations during controlled deployment

## 5. Backend Deployment

The FastAPI application should run behind a production process manager/platform.

Example start command:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The exact deployment command depends on the selected hosting provider.

## 6. HTTPS

Production API must use HTTPS.

The Flutter application must not send authentication credentials over plain HTTP in production.

## 7. Health Check

Provide:

```text
GET /health
```

Response:

```json
{
  "status": "ok"
}
```

This endpoint can be used by deployment platforms for health monitoring.

## 8. Database Migrations

Deployment process:

```text
Build
  |
Run tests
  |
Apply Alembic migrations
  |
Start API
  |
Health check
```

## 9. Backups

At minimum:
- Automated database backups
- Defined retention policy
- Periodic restore testing

## 10. Monitoring

Future production monitoring should include:
- API errors
- Response times
- Database health
- Authentication failures
- Location update failures
- Active trip errors

## 11. Mobile Configuration

Flutter should receive API base URL through build configuration/environment settings.

Do not hard-code development API URLs into production builds.

## 12. Deployment Rule

Do not deploy unfinished phases simply because the code runs.

A phase is deployment-ready only after:
- Tests pass
- Migration is reviewed
- API behavior is verified
- Security checks are completed
- Documentation is updated
