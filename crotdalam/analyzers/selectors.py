"""Extract pivotable selectors from record text. Offline; no resolution or fetch.

A selector is an identifier an investigator can pivot on: a URL, @mention,
#hashtag, email, phone number, crypto address or messaging-app handle. This
module only *finds* them in text already present in the corpus. It never
resolves a short link, queries WHOIS/DNS, or contacts any address it extracts.
Everything here is lexical pattern matching over supplied strings.
"""

import re
from collections import Counter

from .common import rows, text_of

MAX_TEXT = 100_000
# Deliberately conservative patterns: a false negative is safer here than a
# false positive that sends an investigator chasing a coincidence.
PATTERNS = {
    "url": re.compile(r"https?://[^\s<>\"'()]+", re.IGNORECASE),
    "mention": re.compile(r"(?<![\w.])@([A-Za-z0-9_.]{2,24})"),
    "hashtag": re.compile(r"(?<!\w)#([0-9]*[^\W\d_][\w]{0,63})", re.UNICODE),
    "email": re.compile(r"(?<![\w.])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,24}(?![\w.])"),
    # E.164-ish: optional +, 8-15 digits, tolerating spaces/dashes/dots/parens.
    "phone": re.compile(r"(?<![\w])\+?\(?\d[\d\s().-]{7,17}\d(?![\w])"),
    "btc": re.compile(r"(?<![A-Za-z0-9])(?:bc1[a-z0-9]{11,71}|[13][A-HJ-NP-Za-km-z1-9]{25,34})(?![A-Za-z0-9])"),
    "eth": re.compile(r"(?<![A-Za-z0-9])0x[a-fA-F0-9]{40}(?![A-Za-z0-9])"),
}
# Messaging handles are derived from extracted URLs, where they are unambiguous.
MESSAGING_HOSTS = {
    "t.me": "telegram", "telegram.me": "telegram", "wa.me": "whatsapp",
    "api.whatsapp.com": "whatsapp", "chat.whatsapp.com": "whatsapp_group",
    "signal.group": "signal", "discord.gg": "discord", "line.me": "line",
}
# Scam posts routinely write these without a scheme (e.g. "wa.me/628…").
MESSAGING_BARE = re.compile(
    r"(?<![\w.])(t\.me|telegram\.me|wa\.me|chat\.whatsapp\.com|signal\.group|discord\.gg|line\.me)/([^\s<>\"'()]+)",
    re.IGNORECASE)


def _digits_ok(candidate):
    digits = re.sub(r"\D", "", candidate)
    return 8 <= len(digits) <= 15


def extract(text):
    """Return {selector_type: sorted [values]} found in one text string."""
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if len(text) > MAX_TEXT:
        raise ValueError("Text exceeds 100000 characters")
    found = {}
    for name, pattern in PATTERNS.items():
        values = set()
        for match in pattern.finditer(text):
            value = match.group(0)
            if name == "phone" and not _digits_ok(value):
                continue
            if name in ("mention", "hashtag"):
                value = match.group(1)
            values.add(value.strip().rstrip(".,);"))
        if values:
            found[name] = sorted(values)
    # Derive messaging handles from any URL whose host is a known service.
    from urllib.parse import urlsplit
    messaging = set()
    for url in found.get("url", []):
        host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
        if host in MESSAGING_HOSTS:
            messaging.add(f"{MESSAGING_HOSTS[host]}:{urlsplit(url).path.strip('/') or '(root)'}")
    for host, path in MESSAGING_BARE.findall(text):
        host = host.lower()
        messaging.add(f"{MESSAGING_HOSTS[host]}:{path.strip('/').rstrip('.,);') or '(root)'}")
    if messaging:
        found["messaging"] = sorted(messaging)
    return found


class SelectorExtractor:
    """analyze(record|list) -> selectors with per-target attribution and counts.

    Reads only explicit text fields (see analyzers.common.text_of). Aggregates
    across the corpus so a value appearing under many targets is visible as a
    pivot. Nothing extracted is resolved, validated against a live service, or
    contacted.
    """

    def analyze(self, data):
        per_type = {}
        overall = Counter()
        by_target = {}
        for value in rows(data):
            selectors = extract(text_of(value))
            target = value.get("uniqueId") or value.get("id") or value.get("cid") or "(unattributed)"
            for name, items in selectors.items():
                bucket = per_type.setdefault(name, Counter())
                for item in items:
                    bucket[item] += 1
                    overall[name] += 1
                    by_target.setdefault(target, {}).setdefault(name, []).append(item)
        selectors = {name: [{"value": v, "count": c} for v, c in counter.most_common()]
                     for name, counter in per_type.items()}
        return {"selectors": selectors, "counts": dict(overall),
                "by_target": {t: {k: sorted(set(v)) for k, v in d.items()} for t, d in by_target.items()},
                "distinct": {name: len(counter) for name, counter in per_type.items()},
                "method": "offline_lexical_extraction",
                "uncertainty": [
                    "Lexical extraction only; nothing was resolved, validated or contacted.",
                    "A short link's final destination is unknown; a handle may be spoofed or reused.",
                    "Phone and crypto patterns match by shape and can yield false positives."]}
