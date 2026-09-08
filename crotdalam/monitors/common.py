from crotdalam.utils.helpers import sha256_value, utc_now, parse_timestamp
from crotdalam.utils.models import validate_record


def snapshot(db, kind: str, record: dict) -> tuple[str, dict, dict, str]:
    validate_record(record)
    value = record["value"]
    identity = next((value[field] for field in ("id", "user_id", "sec_uid")
                     if value.get(field) is not None and str(value[field])), record["target"])
    key = kind + ":" + sha256_value(str(identity))
    timestamp = record.get("timestamp", utc_now())
    return key, db.get_state(key) or {}, value, timestamp


def stale(state: dict, timestamp: str) -> bool:
    return bool(state.get("timestamp") and parse_timestamp(timestamp) <= parse_timestamp(state["timestamp"]))


def alert(kind: str, record: dict, timestamp: str, details: dict) -> dict:
    result = {"type": kind, "target": record["target"], "timestamp": timestamp, "details": details}
    result["id"] = sha256_value(result)
    return result
