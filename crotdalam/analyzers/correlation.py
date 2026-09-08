"""Cross-account coordination indicators over a corpus. Offline, explainable.

Where BotDetector looks within one account, this looks *across* accounts for
the strongest signal of coordinated inauthentic behavior: the same normalized
caption, the same shared selector (link, handle, wallet), or the same
verbatim comment posted by distinct identities. It reports clusters and the
accounts in them; it never concludes that a cluster is a single operator.
"""

import hashlib
import re
from collections import defaultdict

from .common import rows, text_of
from .selectors import extract

MAX_RECORDS = 10_000
_WS = re.compile(r"\s+")


def _normalize_text(text):
    # Fold case and whitespace so trivial edits do not hide reuse; keep enough
    # that genuinely different captions stay distinct.
    return _WS.sub(" ", text.casefold().strip())


def _author(value):
    author = value.get("author")
    if isinstance(author, dict):
        return author.get("uniqueId") or author.get("id")
    return value.get("uniqueId") or (value.get("user") or {}).get("unique_id") or value.get("id") or value.get("cid")


class CoordinationAnalyzer:
    """analyze(list) -> clusters of accounts sharing content or selectors.

    A cluster is reported only when a normalized caption, a selector, or a
    verbatim comment is shared by at least `min_accounts` distinct identities
    (default 2). Weights are indicators, not proof of a single operator.
    """

    def __init__(self, min_accounts: int = 2, min_caption_length: int = 12):
        if isinstance(min_accounts, bool) or not isinstance(min_accounts, int) or min_accounts < 2:
            raise ValueError("min_accounts must be an integer >= 2")
        self.min_accounts = min_accounts
        self.min_caption_length = min_caption_length

    def analyze(self, data):
        values = rows(data)
        captions = defaultdict(set)        # text hash -> {authors}
        caption_text = {}
        selectors = defaultdict(set)       # (type, value) -> {authors}
        for value in values:
            author = _author(value)
            if author is None:
                continue
            author = str(author)
            text = text_of(value).strip()
            if len(text) >= self.min_caption_length:
                normalized = _normalize_text(text)
                digest = hashlib.sha256(normalized.encode()).hexdigest()
                captions[digest].add(author)
                caption_text.setdefault(digest, normalized[:200])
            for kind, items in extract(text).items():
                if kind in ("hashtag",):        # hashtags are too common to imply coordination
                    continue
                for item in items:
                    selectors[(kind, item)].add(author)

        shared_captions = [
            {"caption": caption_text[d], "accounts": sorted(a), "account_count": len(a), "weight": 30}
            for d, a in captions.items() if len(a) >= self.min_accounts]
        shared_selectors = [
            {"selector_type": k[0], "value": k[1], "accounts": sorted(a), "account_count": len(a), "weight": 25}
            for k, a in selectors.items() if len(a) >= self.min_accounts]
        shared_captions.sort(key=lambda c: (-c["account_count"], c["caption"]))
        shared_selectors.sort(key=lambda c: (-c["account_count"], c["value"]))

        # Accounts that co-occur in any shared cluster form a coordination set.
        clustered = defaultdict(set)
        for group in shared_captions + shared_selectors:
            for a in group["accounts"]:
                clustered[a].update(group["accounts"])
        components = _components({a: peers for a, peers in clustered.items()})

        return {"shared_captions": shared_captions, "shared_selectors": shared_selectors,
                "coordinated_account_sets": sorted((sorted(c) for c in components), key=lambda c: (-len(c), c)),
                "accounts_analyzed": len({str(_author(v)) for v in values if _author(v) is not None}),
                "min_accounts": self.min_accounts,
                "method": "offline_content_correlation", "is_probability": False,
                "uncertainty": [
                    "Shared content also arises from duets, reposts, quoting, templates and news events.",
                    "Distinct usernames do not prove distinct people, nor one operator; identity is unverified.",
                    "A partial corpus over-represents whatever it happened to capture."]}


def _components(adjacency):
    seen, out = set(), []
    for start in adjacency:
        if start in seen:
            continue
        stack, group = [start], set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            group.add(node)
            stack.extend(adjacency.get(node, ()) - seen)
        out.append(group)
    return out
