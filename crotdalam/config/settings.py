"""Local configuration. Secrets are referenced by variable name, never stored.

`Settings` is a frozen dataclass so `dataclasses.replace` produces explicit
copies and `asdict` is safe to print. `from_env` reads `CROTDALAM_*` variables
and validates every value; an invalid variable raises rather than falling back
to a silent default. No value here enables network access on its own.
"""

from dataclasses import dataclass, replace
import math
import os

PREFIX = "CROTDALAM_"
MAX_CONCURRENCY = 32


@dataclass(frozen=True)
class Settings:
    corpus: str | None = None
    database: str = "data/db/crotdalam.sqlite"
    output_dir: str = "data/exports"
    concurrency: int = 4
    request_timeout: float = 30.0
    case_id: str = "UNASSIGNED"
    analyst: str = "Not specified"
    encryption_key_env: str | None = None

    def __post_init__(self):
        if isinstance(self.concurrency, bool) or not isinstance(self.concurrency, int) \
                or not 1 <= self.concurrency <= MAX_CONCURRENCY:
            raise ValueError(f"concurrency must be an integer in 1..{MAX_CONCURRENCY}")
        if isinstance(self.request_timeout, bool) or not isinstance(self.request_timeout, (int, float)) \
                or not math.isfinite(self.request_timeout) or not 0 < self.request_timeout <= 600:
            raise ValueError("request_timeout must be a finite number in (0, 600] seconds")
        for field in ("database", "output_dir", "case_id", "analyst"):
            if not isinstance(getattr(self, field), str) or not getattr(self, field).strip():
                raise ValueError(f"{field} must be a nonempty string")
        for field in ("corpus", "encryption_key_env"):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field} must be a nonempty string or None")

    @classmethod
    def from_env(cls, environ=None):
        """Build settings from CROTDALAM_* variables; unset variables keep defaults."""
        environ = os.environ if environ is None else environ
        values = {}
        for field, cast in (("corpus", str), ("database", str), ("output_dir", str),
                            ("concurrency", int), ("request_timeout", float),
                            ("case_id", str), ("analyst", str), ("encryption_key_env", str)):
            raw = environ.get(PREFIX + field.upper())
            if raw is None or raw == "":
                continue
            try:
                values[field] = cast(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{PREFIX}{field.upper()} is not a valid {cast.__name__}") from exc
        return cls(**values)

    def encryption_key(self, environ=None):
        """Read the key from its named variable. The key itself is never stored."""
        if self.encryption_key_env is None:
            return None
        environ = os.environ if environ is None else environ
        key = environ.get(self.encryption_key_env)
        if not key:
            raise ValueError(f"{self.encryption_key_env} is set as the key variable but is empty")
        return key

    def with_overrides(self, **overrides):
        """Apply only the overrides that were actually supplied (not None)."""
        return replace(self, **{k: v for k, v in overrides.items() if v is not None})
