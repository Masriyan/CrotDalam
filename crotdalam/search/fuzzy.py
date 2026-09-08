"""Deterministic token-level edit-distance matching via bounded regex."""

import time
import regex
from .keyword import KeywordSearch, check_query
from ..collectors.base import validate_record


class FuzzySearch(KeywordSearch):
    """Local phrase matching with <=max_edits insertions/deletions/substitutions.

    Whole-word boundaries prevent tiny queries matching arbitrary substrings.
    max_edits is 0..3 and always less than query length. Timeout is explicit.
    """

    def __init__(self, records, max_edits: int = 1, timeout: float = 0.02):
        super().__init__(records)
        if isinstance(max_edits, bool) or not isinstance(max_edits, int) or not 0 <= max_edits <= 3:
            raise ValueError("max_edits must be 0..3")
        if not isinstance(timeout, (float, int)) or not 0 < timeout <= 0.1:
            raise ValueError("timeout must be in (0, 0.1] seconds")
        self.max_edits, self.timeout = max_edits, timeout

    def search(self, keyword: str, limit: int = 20) -> list[dict]:
        check_query(keyword, limit)
        if limit == 0:
            return []
        query = keyword.strip()
        edits = min(self.max_edits, len(query) - 1)
        pattern = regex.compile(r"(?<!\w)(?:" + regex.escape(query) + r"){e<=" + str(edits) + r"}(?!\w)", regex.IGNORECASE | regex.FULLCASE)
        result = []
        deadline = time.monotonic() + 2
        for record, text in zip(self.records, self.texts):
            budget = min(self.timeout, deadline - time.monotonic())
            if budget <= 0:
                raise ValueError("Fuzzy search total time budget exceeded")
            try:
                matched = pattern.search(text, timeout=budget)
            except TimeoutError as exc:
                raise ValueError("Fuzzy search timed out; narrow the query/corpus") from exc
            if matched:
                result.append(validate_record(record))
                if len(result) == limit:
                    break
        return result
