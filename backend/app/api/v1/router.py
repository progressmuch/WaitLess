"""Aggregates every v1 router.

`main.py` mounts this under `settings.API_V1_STR`, so all endpoints are served
from `/api/v1/...` (docs/03-system-architecture.md section 3).
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth

api_router = APIRouter()
api_router.include_router(auth.router)