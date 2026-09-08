"""Offline coordinates only; no account-IP inference or geolocation requests."""

import math


def validate_coordinates(latitude: float, longitude: float) -> tuple[float, float]:
    for value, bound in ((latitude, 90), (longitude, 180)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not -bound <= value <= bound:
            raise ValueError("coordinates must be finite numbers within latitude/longitude bounds")
    return float(latitude), float(longitude)
