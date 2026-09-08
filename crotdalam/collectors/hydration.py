"""Bounded extraction from public JSON script hydration, never JavaScript eval."""

import json
from bs4 import BeautifulSoup

MAX_HTML_BYTES = 5_000_000
MAX_SCRIPTS = 64
MAX_JSON_BYTES = 2_000_000
MAX_NODES = 100_000
MAX_DEPTH = 64


def objects(html: str):
    """Yield nested dicts from TikTok JSON scripts within shared walk budgets.

    Supports SIGI_STATE, __UNIVERSAL_DATA_FOR_REHYDRATION__, __NEXT_DATA__,
    and application/json scripts. Malformed scripts are skipped; resource
    limit violations raise ValueError instead of returning a partial match.
    """
    if not isinstance(html, str) or len(html.encode("utf-8")) > MAX_HTML_BYTES:
        raise ValueError("HTML must be text of at most 5 MB")
    soup = BeautifulSoup(html, "html.parser")
    scripts = soup.find_all("script")
    eligible = [s for s in scripts if s.get("type", "").lower() == "application/json"
                or s.get("id") in {"SIGI_STATE", "__UNIVERSAL_DATA_FOR_REHYDRATION__", "__NEXT_DATA__"}]
    if len(eligible) > MAX_SCRIPTS:
        raise ValueError("Too many JSON hydration scripts")
    found = []
    visited = 0
    for script in eligible:
        text = script.string or script.get_text()
        if len(text.encode("utf-8")) > MAX_JSON_BYTES:
            raise ValueError("Hydration script exceeds 2 MB")
        try:
            root = json.loads(text)
        except (ValueError, RecursionError):
            continue
        stack = [(root, 0)]
        while stack:
            node, depth = stack.pop()
            visited += 1
            if visited > MAX_NODES or depth > MAX_DEPTH:
                raise ValueError("Hydration traversal budget exceeded")
            if isinstance(node, dict):
                found.append(node)
                children = node.values()
            elif isinstance(node, list):
                children = node
            else:
                continue
            stack.extend((child, depth + 1) for child in children)
    return found
