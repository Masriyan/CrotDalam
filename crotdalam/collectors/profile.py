"""Public TikTok profile hydration collector."""

from datetime import datetime, timezone
import re
from ..config.patterns import USERNAME_PATTERN
from .hydration import objects
from .base import validate_record


class ProfileCollector:
    def __init__(self, engine):
        self.engine = engine

    async def collect(self, username: str) -> dict:
        if not isinstance(username, str):
            raise ValueError("username must be text")
        username = username.removeprefix("@")
        if not re.fullmatch(USERNAME_PATTERN, username):
            raise ValueError("Invalid TikTok username")
        url = f"https://www.tiktok.com/@{username}"
        nodes = objects(await self.engine.fetch(url))
        profile_stats = {}
        for parent in nodes:
            if isinstance(parent.get("user"), dict):
                profile_stats[id(parent["user"])] = parent.get("stats", {})
            module = parent.get("UserModule")
            if isinstance(module, dict) and isinstance(module.get("users"), dict):
                stats = module.get("stats", {})
                for key, user in module["users"].items():
                    if isinstance(user, dict):
                        profile_stats[id(user)] = stats.get(key, stats.get(str(user.get("id", "")), {})) if isinstance(stats, dict) else {}
        for node in nodes:
            if str(node.get("uniqueId", "")).casefold() != username.casefold():
                continue
            # Match profile containers, not recommendation-video author stubs.
            if id(node) not in profile_stats:
                continue
            stats = profile_stats[id(node)]
            value = {k: node[k] for k in ("id", "uniqueId", "nickname", "signature", "verified", "privateAccount", "avatarLarger") if k in node}
            value["stats"] = stats if isinstance(stats, dict) else {}
            value["availability"] = "public_hydration_only"
            return validate_record({"data_type": "profile", "target": username, "value": value,
                                    "source_url": url, "timestamp": datetime.now(timezone.utc).isoformat()})
        raise ValueError("Public profile hydration unavailable or target absent; login, privacy or bot challenges are not bypassed")
