"""Commuter journey discovery service (Phase 5)."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, aliased

from app.models.bus import Bus
from app.models.bus_location import BusLocation
from app.models.fare import Fare
from app.models.route import Route
from app.models.route_stop import RouteStop
from app.models.stop import Stop
from app.models.trip import Trip, TripStatus
from app.services.eta_service import ETAService
from app.services.trip_service import get_freshness_status, LOCATION_FRESHNESS_TARGET_MINUTES


def _datetime_aware(v: datetime | None) -> Optional[datetime]:
    if v is None:
        return None
    if v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v.astimezone(timezone.utc)


def get_freshness_minutes(received_at: datetime | None) -> Optional[float]:
    if not received_at:
        return None
    now = datetime.now(timezone.utc)
    dt = _datetime_aware(received_at)
    delta = (now - dt).total_seconds() / 60.0
    if delta < 0:
        return 0.0
    return delta


def find_journeys(
    db: Session,
    origin_stop_id: str,
    destination_stop_id: str,
    route_id: str | None = None,
):
    """Find relevant active journeys for a stop pair."""
    # Find routes that have both stops (by id) in order? 
    # Simple approach: find routes where route_stops contains both
    # and there might be an active trip on that route with a bus
    results = []

    # Get routes that serve both stops
    rs1 = aliased(RouteStop)
    rs2 = aliased(RouteStop)
    stmt = select(Route).distinct()
    stmt = stmt.join(rs1, rs1.route_id == Route.id)
    stmt = stmt.join(rs2, rs2.route_id == Route.id)
    stmt = stmt.where(rs1.stop_id == origin_stop_id, rs2.stop_id == destination_stop_id)
    if route_id:
        stmt = stmt.where(Route.id == route_id)
    routes = db.execute(stmt).scalars().all()

    for route in routes:
        # Find active trips on this route
        trips = db.execute(
            select(Trip).where(Trip.route_id == route.id, Trip.status == TripStatus.ACTIVE)
        ).scalars().all()
        for trip in trips:
            bus = db.get(Bus, trip.bus_id)
            # Get latest location for this trip
            latest_loc = db.execute(
                select(BusLocation)
                .where(BusLocation.trip_id == trip.id)
                .order_by(BusLocation.received_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            # Get fare for this route+stop pair (any applicable active fare)
            fare = db.execute(
                select(Fare)
                .where(
                    Fare.route_id == route.id,
                    Fare.origin_stop_id == origin_stop_id,
                    Fare.destination_stop_id == destination_stop_id,
                    Fare.is_active.is_(True),
                )
                .order_by(Fare.effective_from.desc())
                .limit(1)
            ).scalar_one_or_none()
            # Compute freshness
            fresh_mins = get_freshness_minutes(latest_loc.received_at if latest_loc else None)
            fs = get_freshness_status(latest_loc) if latest_loc else {"status": "unknown", "minutes_since": fresh_mins}
            # ETA - simple: if we have origin stop lat/lon and latest loc, compute distance from latest to destination? 
            # But we don't have origin coords here easily; use latest location as is - Phase 5 says "ETA" - simple estimate
            eta = None
            if latest_loc:
                dest = db.get(Stop, destination_stop_id)
                orig = db.get(Stop, origin_stop_id)
                # If bus is moving, estimate based on speed or default
                dist = ETAService.calculate_distance_km(latest_loc.latitude, latest_loc.longitude, dest.latitude, dest.longitude) if dest else 0
                speed = latest_loc.speed if latest_loc.speed and latest_loc.speed > 0 else None
                eta = ETAService.estimate_eta_minutes(dist, speed, is_stale=(fs.get("status") == "very_stale"))
            results.append(
                {
                    "route": {
                        "id": str(route.id),
                        "name": route.name,
                        "code": route.code,
                    },
                    "fare": {
                        "amount": str(fare.amount) if fare else None,
                        "currency": fare.currency if fare else "USD",
                    } if fare else None,
                    "active_bus": {
                        "id": str(bus.id) if bus else None,
                        "registration_number": bus.registration_number if bus else None,
                        "fleet_number": bus.fleet_number if bus else None,
                    } if bus else None,
                    "trip_id": str(trip.id),
                    "latest_location": {
                        "latitude": latest_loc.latitude,
                        "longitude": latest_loc.longitude,
                        "captured_at": latest_loc.captured_at.isoformat() if latest_loc and latest_loc.captured_at else None,
                        "received_at": latest_loc.received_at.isoformat() if latest_loc and latest_loc.received_at else None,
                    } if latest_loc else None,
                    "last_updated_time": latest_loc.received_at.isoformat() if latest_loc and latest_loc.received_at else None,
                    "eta_minutes": eta,
                    "freshness_status": fs.get("status"),
                }
            )
    return results
