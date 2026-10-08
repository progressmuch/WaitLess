"""SQLAlchemy models.

Every model module is imported here so that `Base.metadata` is complete.
Alembic (`alembic/env.py`) and the test fixture (`tests/conftest.py`) rely on
this to detect/create the schema.
"""

from app.models.bus import Bus
from app.models.bus_location import BusLocation
from app.models.fare import Fare
from app.models.operator_assignment import OperatorAssignment
from app.models.route import Route
from app.models.route_stop import RouteStop
from app.models.stop import Stop
from app.models.trip import Trip
from app.models.user import User, UserRole

__all__ = [
    "Bus",
    "BusLocation",
    "Fare",
    "OperatorAssignment",
    "Route",
    "RouteStop",
    "Stop",
    "Trip",
    "User",
    "UserRole",
]
