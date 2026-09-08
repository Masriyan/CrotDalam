"""Livestream values: is_live (bool), room_id, title, viewer_count.

Unknown is_live does not end a stream. First observation establishes a baseline.
"""

from .common import snapshot, stale, alert


class LivestreamMonitor:
    def __init__(self, db):
        self.db = db

    def check(self, record: dict) -> list[dict]:
        key, state, value, timestamp = snapshot(self.db, "livestream", record)
        if stale(state, timestamp):
            return []
        previous = state.get("value", {})
        alerts = []
        live = value.get("is_live")
        if isinstance(live, bool):
            if "is_live" in previous and live != previous["is_live"]:
                alerts.append(alert("livestream_started" if live else "livestream_ended", record, timestamp,
                                    {"before": previous["is_live"], "after": live}))
                previous = {"is_live": live}
            previous["is_live"] = live
            if live:
                room = value.get("room_id")
                if room is not None and "room_id" in previous and room != previous["room_id"]:
                    alerts.append(alert("livestream_room_changed", record, timestamp,
                                        {"before": previous["room_id"], "after": room}))
                    previous = {"is_live": True}
                for field in ("room_id", "title", "viewer_count"):
                    current = value.get(field)
                    valid = (isinstance(current, int) and not isinstance(current, bool) and current >= 0
                             if field == "viewer_count" else isinstance(current, str))
                    if valid:
                        if field in previous and current != previous[field]:
                            alerts.append(alert("livestream_" + field + "_changed", record, timestamp,
                                                {"before": previous[field], "after": current}))
                        previous[field] = current
        self.db.set_state(key, {"value": previous, "timestamp": timestamp})
        return alerts
