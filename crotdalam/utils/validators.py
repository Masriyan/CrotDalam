"""Syntax checks only. These functions neither resolve nor fetch URLs.

The TikTok allowlist is not a general SSRF defense. HTTP callers must independently
restrict redirect destinations; a validated short URL may redirect elsewhere.
"""

import re
from urllib.parse import urlsplit


def validate_username(username: str) -> str:
    if not isinstance(username, str):
        raise ValueError("username must be a string")
    normalized = username.removeprefix("@")
    if not re.fullmatch(r"[A-Za-z0-9_](?:[A-Za-z0-9_.]{0,22}[A-Za-z0-9_])?", normalized):
        raise ValueError("invalid TikTok username (1-24 ASCII characters; no trailing dot)")
    return normalized


def validate_tiktok_url(url: str) -> str:
    if not isinstance(url, str) or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url) or "\\" in url:
        raise ValueError("invalid TikTok URL")
    try:
        parts = urlsplit(url)
        hosts = {"tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com"}
        if (parts.scheme != "https" or parts.hostname not in hosts
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 443)
                or parts.netloc.lower() not in hosts | {h + ":443" for h in hosts}):
            raise ValueError("URL must use HTTPS on an allowed TikTok hostname without credentials")
    except ValueError as exc:
        raise ValueError("invalid TikTok URL") from exc
    return url
