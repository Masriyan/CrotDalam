"""Imported comment records; no unrestricted comments API."""
from .base import ImportedCollector


class CommentCollector(ImportedCollector):
    kind = "comment"
