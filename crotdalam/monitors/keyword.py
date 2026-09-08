"""Case-insensitive substring matches in string values, deduplicated persistently.

One alert per keyword/content revision/target/type. Keys and metadata are not searched.
"""

from crotdalam.utils.helpers import sha256_value, utc_now
from crotdalam.utils.models import validate_record
from .common import alert


class KeywordMonitor:
    def __init__(self, db, keywords):
        if isinstance(keywords, str):
            raise ValueError("keywords must be an iterable of strings")
        self.db = db
        self.keywords = set()
        for keyword in keywords:
            if not isinstance(keyword, str) or not keyword.strip():
                raise ValueError("keywords must be nonempty strings")
            self.keywords.add(keyword.strip().casefold())

    def check(self, records) -> list[dict]:
        alerts = []
        for record in records:
            validate_record(record)
            stack = [record["value"]]
            strings = []
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    stack.extend(item.values())
                elif isinstance(item, list):
                    stack.extend(item)
                elif isinstance(item, str):
                    strings.append(item.casefold())
            for keyword in sorted(self.keywords):
                if not any(keyword in text for text in strings):
                    continue
                key = "keyword:" + sha256_value([record["data_type"], record["target"], record["value"], keyword])
                if self.db.get_state(key) is not None:
                    continue
                timestamp = record.get("timestamp", utc_now())
                item = alert("keyword_match", record, timestamp, {"keyword": keyword})
                self.db.set_state(key, {"alert_id": item["id"]})
                alerts.append(item)
        return alerts
