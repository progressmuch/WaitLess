"""Commuter journey discovery endpoints (Phase 5)."""

from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.journey_service import find_journeys
from app.schemas.common import APIResponse

router = APIRouter(tags=["journeys"])


@router.get("/journeys/search")
def search_journeys(
    origin_stop_id: str = Query(...),
    destination_stop_id: str = Query(...),
    route_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    results = find_journeys(db, origin_stop_id, destination_stop_id, route_id)
    return APIResponse(data={"results": results})
