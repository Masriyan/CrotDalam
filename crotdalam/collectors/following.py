"""Imported following records; no unrestricted following API."""
from .base import ImportedCollector


class FollowingCollector(ImportedCollector):
    kind = "following"
