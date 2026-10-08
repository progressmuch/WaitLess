"""ETA tests for Phase 6."""
import pytest
from app.services import eta_service


def test_calculate_distance_km():
    # Same point
    assert eta_service.ETAService.calculate_distance_km(0, 0, 0, 0) == 0
    # Known distance roughly (approximate)
    dist = eta_service.ETAService.calculate_distance_km(-17.825, 31.033, -17.826, 31.033)
    assert dist > 0 and dist < 0.2  # small distance


def test_estimate_eta_minutes():
    # Normal case
    eta = eta_service.ETAService.estimate_eta_minutes(30, 60)  # 30km at 60kmh = 30 min
    assert eta == 30
    # With default speed
    eta = eta_service.ETAService.estimate_eta_minutes(15)  # 15km at 30kmh default = 30 min
    assert eta == 30
    # Already at destination
    eta = eta_service.ETAService.estimate_eta_minutes(-1)
    assert eta == 0
    # Stale location
    eta = eta_service.ETAService.estimate_eta_minutes(10, is_stale=True)
    assert eta is None
    # Zero/unknown speed uses default
    eta = eta_service.ETAService.estimate_eta_minutes(30, speed_kmh=0)
    assert eta == 60  # 30km at 30kmh = 60 min
