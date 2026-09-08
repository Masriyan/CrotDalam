"""Time-bounded local regex matching using the third-party regex package."""

import time
import regex
from .keyword import KeywordSearch, check_query
from ..collectors.base import validate_record


class RegexSearch(KeywordSearch):
    """search(pattern, limit=20); 512-char pattern, 20 ms/record, 2 s total.

    Invalid expressions and timeouts raise ValueError, never partial results.
    Matching is case-sensitive; use inline (?i) when needed.
    """

    def __init__(self, records, timeout: float = 0.02):
        super().__init__(records)
        if not isinstance(timeout, (float, int)) or not 0 < timeout <= 0.1:
            raise ValueError("timeout must be in (0, 0.1] seconds")
        self.timeout = timeout

    def search(self, keyword: str, limit: int = 20) -> list[dict]:
        check_query(keyword, limit)
        try:
            pattern = regex.compile(keyword)
        except regex.error as exc:
            raise ValueError(f"Invalid regex: {exc}") from exc
        if limit == 0:
            return []
        result = []
        deadline = time.monotonic() + 2
        for record, text in zip(self.records, self.texts):
            budget = min(self.timeout, deadline - time.monotonic())
            if budget <= 0:
                raise ValueError("Regex search total time budget exceeded")
            try:
                matched = pattern.search(text, timeout=budget)
            except TimeoutError as exc:
                raise ValueError("Regex search timed out; narrow the pattern/corpus") from exc
            if matched:
                result.append(validate_record(record))
                if len(result) == limit:
                    break
        return result
