"""UTC activity distributions from observed timestamps, not location inference."""

from collections import Counter
from statistics import median
from .common import rows, utc_time


class TemporalAnalyzer:
    """Accept dict/list; timestamp, createTime or created_at on value/record.

    Aware ISO strings and Unix seconds only. Duplicate times are retained;
    naive/invalid/missing times are counted as excluded, never assumed local.
    """

    def analyze(self, data):
        values = rows(data)
        originals = data if isinstance(data, list) else [data]
        times = []
        excluded = 0
        for value, original in zip(values, originals):
            raw = next((value[k] for k in ("createTime", "created_at", "timestamp") if k in value),
                       original.get("collected_at", original.get("timestamp")))
            parsed = utc_time(raw)
            if parsed is None:
                excluded += 1
            else:
                times.append(parsed)
        times.sort()
        hours = Counter(t.hour for t in times)
        weekdays = Counter(t.weekday() for t in times)
        days = Counter(t.date().isoformat() for t in times)
        gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
        return {"timezone": "UTC", "valid_count": len(times), "excluded_count": excluded,
                "hour_counts": {str(h): hours[h] for h in range(24)},
                "weekday_counts": {str(d): weekdays[d] for d in range(7)},
                "daily_counts": dict(sorted(days.items())),
                "first_seen": times[0].isoformat() if times else None,
                "last_seen": times[-1].isoformat() if times else None,
                "median_interval_seconds": median(gaps) if gaps else None,
                "duplicate_timestamp_count": len(times) - len(set(times)),
                "peak_hour_utc": min(hours, key=lambda h: (-hours[h], h)) if hours else None,
                "uncertainty": ["Observation times may be collection times; UTC activity cannot establish location or automation."]}
