"""Collector protocols and bounded plain-dictionary record handling."""

from collections.abc import Iterable
import json
from typing import Protocol

MAX_RECORDS = 10_000
MAX_RECORD_BYTES = 1_000_000


class Engine(Protocol):
    async def fetch(self, url: str) -> str:
        """Return public page HTML; engine owns transport and redirect policy."""
        raise NotImplementedError

    async def collect(self, kind: str, target: str) -> dict:
        """Dispatch a collector and return a contract record."""
        raise NotImplementedError

    async def search(self, keyword: str, limit: int = 20) -> list[dict]:
        """Search an engine-supported source, returning contract records."""
        raise NotImplementedError


def validate_record(record: dict) -> dict:
    """Validate and detach a JSON-compatible record; preserve optional metadata."""
    if not isinstance(record, dict):
        raise ValueError("Each record must be a dictionary")
    if not isinstance(record.get("data_type"), str) or not record["data_type"]:
        raise ValueError("Record requires nonempty data_type")
    if not isinstance(record.get("target"), str) or not isinstance(record.get("value"), dict):
        raise ValueError("Record requires string target and dictionary value")
    try:
        encoded = json.dumps(record, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode("utf-8")) > MAX_RECORD_BYTES:
            raise ValueError("Record exceeds 1 MB")
        return json.loads(encoded)
    except (TypeError, RecursionError, OverflowError) as exc:
        raise ValueError("Record must be bounded JSON-compatible data") from exc


def import_records(records: Iterable[dict]) -> list[dict]:
    result = []
    for record in records:
        if len(result) >= MAX_RECORDS:
            raise ValueError("Corpus exceeds 10000 records")
        result.append(validate_record(record))
    return result


class ImportedCollector:
    """Local-only collection. Input is an iterable of contract records.

    collect(target) returns one envelope with value.records and value.count.
    None means no import supplied, not permission to attempt a private API.
    """

    kind = "imported"

    def __init__(self, records=None):
        if records is not None and hasattr(records, "fetch"):
            raise ValueError(f"{self.kind} supports imported records only, not an unrestricted API")
        self.records = None if records is None else import_records(records)

    async def collect(self, target: str) -> dict:
        if self.records is None:
            raise ValueError(f"{self.kind} requires imported local records; unrestricted API unsupported")
        if not isinstance(target, str):
            raise ValueError("target must be a string")
        matched = [validate_record(r) for r in self.records
                   if r["data_type"] == self.kind and r["target"].casefold() == target.casefold()]
        return {"data_type": self.kind, "target": target,
                "value": {"records": matched, "count": len(matched), "origin": "local_import"}}
