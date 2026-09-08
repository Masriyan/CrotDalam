"""Imported follower records; no unrestricted follower API."""
from .base import ImportedCollector


class FollowerCollector(ImportedCollector):
    kind = "follower"
