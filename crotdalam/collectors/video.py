"""Public canonical TikTok video URL collector; no short-link resolution."""

from datetime import datetime, timezone
import re
from urllib.parse import urlsplit
from ..config.patterns import VIDEO_PATH_PATTERN
from .base import validate_record
from .hydration import objects


class VideoCollector:
    def __init__(self, engine):
        self.engine = engine

    async def collect(self, url: str) -> dict:
        try:
            parsed = urlsplit(url)
            match = re.fullmatch(VIDEO_PATH_PATTERN, parsed.path)
            valid = (parsed.scheme == "https" and parsed.hostname in {"www.tiktok.com", "tiktok.com"}
                     and parsed.port in (None, 443) and not parsed.username and not parsed.password and match)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("Invalid canonical TikTok video URL") from exc
        if not valid:
            raise ValueError("Use https://www.tiktok.com/@username/video/id; arbitrary hosts and short URLs unsupported")
        canonical = f"https://www.tiktok.com/@{match[1]}/video/{match[2]}"
        for node in objects(await self.engine.fetch(canonical)):
            if str(node.get("id", "")) != match[2] or not isinstance(node.get("video"), dict):
                continue
            value = {k: node[k] for k in ("id", "desc", "createTime", "author", "stats", "music", "video", "challenges") if k in node}
            value["availability"] = "public_hydration_only"
            return validate_record({"data_type": "video", "target": canonical, "value": value,
                                    "source_url": canonical, "timestamp": datetime.now(timezone.utc).isoformat()})
        raise ValueError("Public video hydration unavailable or target absent; restricted content is not bypassed")
