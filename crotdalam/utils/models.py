"""Records are ordinary JSON dictionaries, not ORM entities.

Two timestamps are kept deliberately distinct: `collected_at` is when the
evidence was observed at its source (the HAR entry's startedDateTime), while
`timestamp` is when the record entered this database. Conflating them would
make temporal analysis describe the analyst's import run, not the target.
"""

from typing import NotRequired, TypedDict

from .helpers import canonical_json, parse_timestamp


class Provenance(TypedDict, total=False):
    collector: str
    entry_index: int
    source_name: str
    source_sha256: str


class Record(TypedDict):
    data_type: str
    target: str
    value: dict
    source_url: NotRequired[str]
    collected_at: NotRequired[str]
    timestamp: NotRequired[str]
    sha256: NotRequired[str]
    provenance: NotRequired[Provenance]


def validate_record(record: dict) -> None:
    if not isinstance(record, dict):
        raise ValueError("record must be a dictionary")
    for field in ("data_type", "target"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"{field} must be a nonempty string")
    if not isinstance(record.get("value"), dict):
        raise ValueError("value must be a dictionary")
    if "source_url" in record and not isinstance(record["source_url"], str):
        raise ValueError("source_url must be a string")
    for field in ("timestamp", "collected_at"):
        if field in record:
            if not isinstance(record[field], str):
                raise ValueError(f"{field} must be a string")
            parse_timestamp(record[field])
    if "provenance" in record and not isinstance(record["provenance"], dict):
        raise ValueError("provenance must be a dictionary")
    canonical_json(record)
