# Transport System - Backend

FastAPI backend for Transport Tracking and Commuter Information System.

## Setup

1. Create virtual environment (already created: WaitLessVenv)
2. Install dependencies
```bash
pip install -r backend/requirements.txt
```
3. Copy .env.example to .env
```bash
cp backend/.env.example backend/.env
```
4. Update .env with configuration
5. Run migrations
```bash
cd backend
alembic upgrade head
```
6. Run development server
```bash
cd backend
uvicorn app.main:app --reload
```

## Testing

```bash
cd backend
PYTHONPATH=. pytest -v
```

## Health Check

```bash
GET /health
```
