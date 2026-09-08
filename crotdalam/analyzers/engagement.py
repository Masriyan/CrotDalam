"""Descriptive engagement, with explicit denominators and missingness."""

from .common import rows, number


class EngagementAnalyzer:
    """Accept raw/record dict or list; stats may be nested under stats.

    Recognizes TikTok diggCount/commentCount/shareCount/playCount/followerCount
    and likes/comments/shares/views/followers. All three interactions must be
    present to calculate rates. Rates may legitimately exceed 100 percent.
    """

    def analyze(self, data):
        output = []
        totals = {"interactions": 0.0, "views": 0.0}
        for value in rows(data):
            stats = value.get("stats", value)
            if not isinstance(stats, dict):
                raise ValueError("stats must be a dictionary")
            counts = {name: number(stats.get(name, stats.get(alias))) for name, alias in
                      (("likes", "diggCount"), ("comments", "commentCount"), ("shares", "shareCount"),
                       ("views", "playCount"), ("followers", "followerCount"))}
            missing = [k for k in ("likes", "comments", "shares") if counts[k] is None]
            interactions = None if missing else sum(counts[k] for k in ("likes", "comments", "shares"))
            item = {"counts": counts, "interactions": interactions, "missing_interactions": missing}
            for denominator in ("views", "followers"):
                item[f"rate_by_{denominator}_percent"] = (
                    100 * interactions / counts[denominator]
                    if interactions is not None and counts[denominator] not in (None, 0) else None)
            if item["rate_by_views_percent"] is not None:
                totals["interactions"] += interactions
                totals["views"] += counts["views"]
            output.append(item)
        return {"records": output, "sample_size": len(output),
                "weighted_rate_by_views_percent": 100 * totals["interactions"] / totals["views"] if totals["views"] else None,
                "uncertainty": ["Rates describe supplied counters only; authenticity and population representativeness are unknown."]}
