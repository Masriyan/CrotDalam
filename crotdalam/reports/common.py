"""Shared report contract and input validation."""

import json
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"
FIELDS = ("data_type", "target", "value", "source_url", "timestamp", "sha256")
# Mirrors the record contract in crotdalam.utils.models: only these are required.
REQUIRED = ("data_type", "target", "value")
OPTIONAL = ("source_url", "timestamp", "sha256")
UNKNOWN = "Not supplied"


def normalize(records):
    """Validate records against the storage contract; absent provenance stays absent.

    `source_url`, `timestamp` and `sha256` are optional because the database and
    collector contracts treat them as optional. Reports must show that a field was
    never supplied rather than inventing a value for it.
    """
    result = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Record {index} must be an object")
        missing = set(REQUIRED) - record.keys()
        if missing:
            raise ValueError(f"Record {index} missing fields: {', '.join(sorted(missing))}")
        if not isinstance(record["value"], dict):
            raise ValueError(f"Record {index}: value must be an object")
        for key in ("data_type", "target"):
            if not isinstance(record[key], str):
                raise ValueError(f"Record {index}: metadata must be strings")
        for key in OPTIONAL:
            if key in record and record[key] is not None and not isinstance(record[key], str):
                raise ValueError(f"Record {index}: {key} must be a string or null")
        result.append(json.loads(json.dumps(record, ensure_ascii=False, allow_nan=False)))
    return result


def envelope(records, case_id, analyst):
    return {"schema_version": SCHEMA_VERSION, "case_id": str(case_id),
            "analyst": str(analyst), "generated_at": datetime.now(timezone.utc).isoformat(),
            "records": normalize(records)}


def destination(output):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported or missing report schema_version")
        payload = payload.get("records")
    if not isinstance(payload, list):
        raise ValueError("Input must be a record array or a versioned report object")
    return normalize(payload)
