"""Hashtag values: video_count, view_count, video_ids, complete (boolean).

Removed IDs are reported only for explicitly complete snapshots. Partial results
merge into known IDs; absence of data is not evidence of deletion.
"""

from .common import snapshot, stale, alert


class HashtagMonitor:
    def __init__(self, db):
        self.db = db

    def check(self, record: dict) -> list[dict]:
        key, state, value, timestamp = snapshot(self.db, "hashtag", record)
        if stale(state, timestamp):
            return []
        previous = state.get("value", {})
        alerts = []
        for field in ("video_count", "view_count"):
            current = value.get(field)
            if isinstance(current, int) and not isinstance(current, bool) and current >= 0:
                if field in previous and current != previous[field]:
                    alerts.append(alert("hashtag_" + field + "_changed", record, timestamp,
                                        {"before": previous[field], "after": current, "delta": current - previous[field]}))
                previous[field] = current
        ids = value.get("video_ids")
        if isinstance(ids, list) and all(isinstance(i, str) and i for i in ids):
            current = set(ids)
            known = set(previous.get("video_ids", []))
            if "video_ids" in previous:
                added = sorted(current - known)
                removed = sorted(known - current) if value.get("complete") is True else []
                if added or removed:
                    alerts.append(alert("hashtag_videos_changed", record, timestamp,
                                        {"added": added, "removed_from_snapshot": removed}))
            previous["video_ids"] = sorted(current if value.get("complete") is True else known | current)
        self.db.set_state(key, {"value": previous, "timestamp": timestamp})
        return alerts
