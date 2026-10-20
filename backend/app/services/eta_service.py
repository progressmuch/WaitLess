"""Simple ETA calculation (Phase 6).

The initial implementation is simple and explainable:
- If speed is known (km/h), ETA = distance_km / speed_km_h * 60 (minutes)
- If speed is unknown, assume a default speed
- If bus has not moved, use route average speed estimate
- Handle stale location data
- Return minutes to arrival (integer or float)
"""

import math
from typing import Optional


class ETAService:
    DEFAULT_SPEED_KMH = 30.0  # default assumption
    
    @staticmethod
    def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula."""
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    @staticmethod
    def estimate_eta_minutes(
        distance_km: float,
        speed_kmh: Optional[float] = None,
        is_stale: bool = False
    ) -> Optional[int]:
        """Estimate ETA in minutes. Returns None if cannot estimate."""
        if is_stale:
            return None  # or handle stale case per requirements
        if distance_km < 0:
            return 0  # already at destination
        speed = float(speed_kmh) if speed_kmh and speed_kmh > 0 else ETAService.DEFAULT_SPEED_KMH
        eta_hours = distance_km / speed if speed > 0 else float('inf')
        eta_minutes = int(round(eta_hours * 60))
        if eta_minutes < 0:
            eta_minutes = 0
        return eta_minutes
