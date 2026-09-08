"""Profile values: id/user_id/sec_uid, username, bio, follower_count.

Missing/null fields are unknown, never deletion. First observation is a baseline.
Spikes compare against the oldest retained sample in the event-time window.
"""

import math
from crotdalam.utils.helpers import parse_timestamp
from .common import snapshot, stale, alert


class ProfileMonitor:
    def __init__(self, db, *, follower_spike_threshold: int = 100,
                 follower_spike_ratio: float = 0.2, window_seconds: float = 3600):
        if (isinstance(follower_spike_threshold, bool) or not isinstance(follower_spike_threshold, int)
                or follower_spike_threshold < 1 or not math.isfinite(follower_spike_ratio)
                or follower_spike_ratio < 0 or not math.isfinite(window_seconds) or window_seconds <= 0):
            raise ValueError("invalid spike thresholds/window")
        self.db = db
        self.threshold = follower_spike_threshold
        self.ratio = follower_spike_ratio
        self.window = window_seconds

    def check(self, record: dict) -> list[dict]:
        key, state, value, timestamp = snapshot(self.db, "profile", record)
        if stale(state, timestamp):
            return []
        previous = state.get("value", {})
        alerts = []
        for field in ("username", "bio"):
            current = value.get(field)
            if isinstance(current, str):
                if field in previous and previous[field] != current:
                    alerts.append(alert("profile_" + field + "_changed", record, timestamp,
                                        {"before": previous[field], "after": current}))
                previous[field] = current
        now = parse_timestamp(timestamp).timestamp()
        samples = [s for s in state.get("samples", []) if 0 <= now - s[0] <= self.window]
        count = value.get("follower_count")
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            if samples:
                baseline = samples[0][1]
                delta = count - baseline
                if delta >= self.threshold and delta >= baseline * self.ratio:
                    alerts.append(alert("profile_follower_spike", record, timestamp,
                                        {"before": baseline, "after": count, "delta": delta,
                                         "window_seconds": self.window}))
                    samples = []
            samples.append([now, count])
        self.db.set_state(key, {"value": previous, "samples": samples, "timestamp": timestamp})
        return alerts
