#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Helper Utilities
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """Sanitize string for use as filename."""
    # Normalize unicode
    name = unicodedata.normalize("NFKD", name)
    
    # Remove invalid characters
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    
    # Replace spaces and special chars
    name = re.sub(r"[\s\-]+", "_", name)
    
    # Remove leading/trailing dots and spaces
    name = name.strip(". ")
    
    # Truncate
    if len(name) > max_length:
        name = name[:max_length]
    
    return name or "unnamed"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_number(n: Optional[int]) -> str:
    """Format number with K/M/B suffix."""
    if n is None:
        return "—"
    
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def extract_domain(url: str) -> Optional[str]:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc or None
    except Exception:
        return None


def is_valid_url(url: str) -> bool:
    """Check if string is valid URL."""
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )
    return bool(url_pattern.match(url))


def parse_proxy_url(proxy: str) -> dict:
    """Parse proxy URL into components."""
    from urllib.parse import urlparse
    
    parsed = urlparse(proxy)
    return {
        "scheme": parsed.scheme or "http",
        "host": parsed.hostname,
        "port": parsed.port,
        "username": parsed.username,
        "password": parsed.password,
    }
