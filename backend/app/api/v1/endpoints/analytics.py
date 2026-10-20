"""Analytics endpoints (Phase 7) - Management only."""

from typing import Annotated
from sqlalchemy import func, literal_column, select
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.journey_search import JourneySearch
from app.models.route import Route
from app.schemas.common import APIResponse

router = APIRouter(tags=["analytics"])

ManagementUser = Annotated[User, Depends(require_roles(UserRole.MANAGEMENT))]


@router.get("/analytics/overview")
def overview(db: Session = Depends(get_db), _: ManagementUser = ManagementUser):
    total = db.scalar(select(func.count(JourneySearch.id))) or 0
    return APIResponse(data={"total_searches": total})


@router.get("/analytics/routes")
def routes_popularity(db: Session = Depends(get_db), _: ManagementUser = ManagementUser):
    stmt = (
        select(Route.code, Route.name, func.count(JourneySearch.id).label("search_count"))
        .join(JourneySearch, JourneySearch.route_id == Route.id, isouter=True)
        .group_by(Route.id, Route.code, Route.name)
        .order_by(func.count(JourneySearch.id).desc())
    )
    rows = db.execute(stmt).all()
    data = [{"route_code": r.code, "route_name": r.name, "search_count": r.search_count} for r in rows]
    return APIResponse(data=data)


@router.get("/analytics/destinations")
def destinations(db: Session = Depends(get_db), _: ManagementUser = ManagementUser):
    from app.models.stop import Stop
    stmt = (
        select(Stop.name, func.count(JourneySearch.id).label("search_count"))
        .join(JourneySearch, JourneySearch.destination_stop_id == Stop.id)
        .group_by(Stop.id, Stop.name)
        .order_by(func.count(JourneySearch.id).desc())
    )
    rows = db.execute(stmt).all()
    data = [{"destination": r.name, "search_count": r.search_count} for r in rows]
    return APIResponse(data=data)


@router.get("/analytics/origin-destination")
def origin_dest(db: Session = Depends(get_db), _: ManagementUser = ManagementUser):
    from app.models.stop import Stop
    orig = func.coalesce(func.max(Stop.name), "unknown").label("origin")
    stmt = (
        select(
            JourneySearch.origin_stop_id,
            JourneySearch.destination_stop_id,
            func.count(JourneySearch.id).label("search_count"),
        )
        .group_by(JourneySearch.origin_stop_id, JourneySearch.destination_stop_id)
        .order_by(func.count(JourneySearch.id).desc())
    )
    rows = db.execute(stmt).all()
    # simpler - just return counts
    data = [
        {
            "origin_stop_id": str(r.origin_stop_id),
            "destination_stop_id": str(r.destination_stop_id),
            "search_count": r.search_count,
        }
        for r in rows
    ]
    return APIResponse(data=data)


@router.get("/analytics/demand-by-time")
def demand_by_time(db: Session = Depends(get_db), _: ManagementUser = ManagementUser):
    hour = func.date_trunc(literal_column("'hour'"), JourneySearch.searched_at)
    stmt = select(
        hour.label("hour"),
        func.count(JourneySearch.id).label("search_count"),
    ).group_by(hour).order_by("hour")
    rows = db.execute(stmt).all()
    data = [{"hour": r.hour.isoformat() if r.hour else None, "search_count": r.search_count} for r in rows]
    return APIResponse(data=data)
