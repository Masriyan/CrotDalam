"""Imported hashtag records; no live hashtag enumeration."""
from .base import ImportedCollector


class HashtagCollector(ImportedCollector):
    kind = "hashtag"
