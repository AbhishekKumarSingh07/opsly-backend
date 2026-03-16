from __future__ import annotations

import math


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great-circle distance in meters between two GPS coordinates
    using the Haversine formula.

    Args:
        lat1: Latitude of point 1 (degrees, -90..90)
        lng1: Longitude of point 1 (degrees, -180..180)
        lat2: Latitude of point 2 (degrees, -90..90)
        lng2: Longitude of point 2 (degrees, -180..180)

    Returns:
        Distance in meters.
    """
    R = 6_371_000  # Earth radius in metres

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)

    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def is_within_radius(
    user_lat: float,
    user_lng: float,
    target_lat: float,
    target_lng: float,
    radius_meters: float,
) -> bool:
    """Return True if the user is within the specified radius of the target location."""
    distance = haversine_distance(user_lat, user_lng, target_lat, target_lng)
    return distance <= radius_meters
