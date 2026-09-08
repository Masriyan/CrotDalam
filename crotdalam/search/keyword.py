"""Casefolded literal matching over imported record values and targets."""

import json
from ..collectors.base import import_records, validate_record

MAX_TEXT = 100_000


def check_query(keyword, limit):
    if not isinstance(keyword, str) or not keyword.strip() or len(keyword) > 512:
        raise ValueError("Query must contain 1..512 characters and not be blank")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 1000:
        raise ValueError("limit must be an integer in 0..1000")


class KeywordSearch:
    """search(keyword, limit=20) -> detached contract records in corpus order.

    Maximum 10000 records, 100000 searchable characters per record. Oversize
    text is rejected, not silently truncated. No live TikTok search is implied.
    """

    def __init__(self, records):
        self.records = import_records(records)
        self.texts = []
        for record in self.records:
            text = record["target"] + " " + json.dumps(record["value"], ensure_ascii=False, sort_keys=True)
            if len(text) > MAX_TEXT:
                raise ValueError("Searchable record exceeds 100000 characters")
            self.texts.append(text)

    def search(self, keyword: str, limit: int = 20) -> list[dict]:
        check_query(keyword, limit)
        if limit == 0:
            return []
        query = keyword.casefold()
        result = []
        for record, text in zip(self.records, self.texts):
            if query in text.casefold():
                result.append(validate_record(record))
                if len(result) == limit:
                    break
        return result
