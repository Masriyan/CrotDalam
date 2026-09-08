"""Input normalization for offline analyzers.

Analyzers accept a raw value dict, a contract record with value:dict, or a
list of either (max 10000). Text comes from explicit content fields, never
dictionary keys or arbitrary metadata. Missing data remains unknown.
"""

from datetime import datetime, timezone
import math


def rows(data):
    items = data if isinstance(data, list) else [data]
    if len(items) > 10_000:
        raise ValueError("Analysis supports at most 10000 records")
    result = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Expected a dictionary or list of dictionaries")
        value = item.get("value", item)
        if not isinstance(value, dict):
            raise ValueError("Record value must be a dictionary")
        result.append(value)
    return result


def text_of(value):
    text = " ".join(value[key] for key in ("text", "desc", "description", "signature", "bio", "title", "nickname")
                    if isinstance(value.get(key), str))
    if len(text) > 100_000:
        raise ValueError("Text exceeds 100000 characters per record")
    return text


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return float(value) if math.isfinite(value) and value >= 0 else None
    except OverflowError:
        return None


def utc_time(value):
    """Unix seconds or timezone-aware ISO 8601. Naive timestamps are rejected."""
    try:
        if isinstance(value, (float, int)) and not isinstance(value, bool):
            return datetime.fromtimestamp(value, timezone.utc)
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return None


def risk_result(score, evidence, uncertainty):
    score = min(100, score)
    return {"score": score, "risk_level": "high" if score >= 60 else "medium" if score >= 30 else "low",
            "evidence": evidence, "uncertainty": uncertainty,
            "method": "offline_heuristic", "is_probability": False}
