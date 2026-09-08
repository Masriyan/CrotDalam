"""Explainable automation indicators; never a definitive bot classification."""

from collections import Counter
from statistics import mean, pstdev
from .common import rows, text_of, utc_time, number, risk_result


class BotDetector:
    """Accept a profile dict with posts:list, or a list of activity records.

    Cadence requires >=10 timestamps and >=1h span. Repetition requires >=10
    nonempty texts. A list is assumed to belong to one account, not a network.
    """

    def analyze(self, data):
        values = rows(data)
        originals = data if isinstance(data, list) else [data]
        profile = values[0] if isinstance(data, dict) else {}
        if "posts" in profile:
            if not isinstance(profile["posts"], list):
                raise ValueError("posts must be a list")
            values = rows(profile["posts"])
            originals = profile["posts"]
        texts = [text_of(v).casefold().strip() for v in values]
        texts = [t for t in texts if t]
        times = sorted(t for v, original in zip(values, originals)
                       if (t := utc_time(v.get("createTime", v.get("timestamp", v.get("created_at", original.get("timestamp")))))) is not None)
        evidence = []
        if len(texts) >= 10:
            repeated_fraction = 1 - len(set(texts)) / len(texts)
            if repeated_fraction >= 0.7:
                evidence.append({"signal": "high_text_repetition", "weight": 30, "fraction": repeated_fraction,
                                 "most_common_count": Counter(texts).most_common(1)[0][1]})
        if len(times) >= 10:
            span = (times[-1] - times[0]).total_seconds()
            gaps = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
            if span >= 3600 and mean(gaps) > 0:
                cv = pstdev(gaps) / mean(gaps)
                if cv < 0.1:
                    evidence.append({"signal": "regular_posting_intervals", "weight": 25, "interval_cv": cv})
                rate = (len(times) - 1) * 86400 / span
                if rate > 100:
                    evidence.append({"signal": "high_observed_post_rate", "weight": 20, "posts_per_day": rate})
        stats = profile.get("stats", profile)
        if not isinstance(stats, dict):
            raise ValueError("stats must be a dictionary")
        following = number(stats.get("followingCount", stats.get("following")))
        followers = number(stats.get("followerCount", stats.get("followers")))
        if following is not None and followers is not None and following >= 1000 and following / max(1, followers) >= 50:
            evidence.append({"signal": "following_imbalance", "weight": 10, "following": following, "followers": followers})
        result = risk_result(sum(e["weight"] for e in evidence), evidence,
                             ["Scheduling tools and legitimate high-volume accounts can match these indicators.",
                              "Assumes supplied activity belongs to one account; identity and automation are unverified."])
        result.update({"text_sample_size": len(texts), "timestamp_sample_size": len(times),
                       "status": "assessed" if evidence or len(texts) >= 10 or len(times) >= 10 else "insufficient_data"})
        return result
