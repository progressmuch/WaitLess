"""Aggregates every v1 router.

`main.py` mounts this under `settings.API_V1_STR`, so all endpoints are served
from `/api/v1/...` (docs/03-system-architecture.md section 3).
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, buses, fares, journeys, operators, routes, stops, trips, analytics

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(routes.router)
api_router.include_router(stops.router)
api_router.include_router(buses.router)
api_router.include_router(operators.router)
api_router.include_router(fares.router)
api_router.include_router(trips.router)
api_router.include_router(journeys.router)
api_router.include_router(analytics.router)
