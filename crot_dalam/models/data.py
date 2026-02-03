#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Data Models
Dataclasses and schemas for TikTok OSINT data.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class InvestigationMode(str, Enum):
    """Investigation depth modes."""
    quick = "quick"
    moderate = "moderate"
    deep = "deep"
    deeper = "deeper"


class ScanStatus(str, Enum):
    """Scan status enum."""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


@dataclass
class VideoRecord:
    """Complete video metadata record."""
    # Core identifiers
    video_id: str
    url: str
    username: Optional[str] = None
    author_name: Optional[str] = None
    
    # Content
    description: Optional[str] = None
    upload_date: Optional[str] = None
    
    # Engagement metrics
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None
    view_count: Optional[int] = None
    
    # Extracted data
    hashtags: List[str] = field(default_factory=list)
    comments: List[Dict[str, str]] = field(default_factory=list)
    extracted_urls: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    
    # Risk analysis
    risk_score: int = 0
    risk_level: str = "NONE"
    risk_matches: List[str] = field(default_factory=list)
    risk_categories: Dict[str, int] = field(default_factory=dict)
    
    # Investigation context
    keyword_searched: Optional[str] = None
    scraped_at: Optional[str] = None
    
    # Evidence paths
    screenshot_path: Optional[str] = None
    video_path: Optional[str] = None
    archive_url: Optional[str] = None
    
    # Sentiment (for comments)
    sentiment_summary: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_row(self) -> Dict[str, Any]:
        """Convert to flat row for CSV export."""
        d = self.to_dict()
        d["hashtags"] = ", ".join(self.hashtags)
        d["risk_matches"] = ", ".join(self.risk_matches)
        d["extracted_urls"] = ", ".join(self.extracted_urls)
        d["mentions"] = ", ".join(self.mentions)
        d["comments"] = json.dumps(self.comments, ensure_ascii=False) if self.comments else ""
        d["risk_categories"] = json.dumps(self.risk_categories) if self.risk_categories else ""
        d["sentiment_summary"] = json.dumps(self.sentiment_summary) if self.sentiment_summary else ""
        return d
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoRecord":
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class UserProfile:
    """TikTok user profile data."""
    username: str
    user_id: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    
    # Metrics
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    like_count: Optional[int] = None
    video_count: Optional[int] = None
    
    # Profile details
    verified: bool = False
    private: bool = False
    avatar_url: Optional[str] = None
    profile_url: Optional[str] = None
    
    # External links
    external_links: List[str] = field(default_factory=list)
    
    # Risk analysis
    risk_score: int = 0
    risk_matches: List[str] = field(default_factory=list)
    
    # Scrape metadata
    scraped_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()
        if not self.profile_url and self.username:
            self.profile_url = f"https://www.tiktok.com/@{self.username}"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Comment:
    """Individual comment data."""
    username: str
    text: str
    like_count: Optional[int] = None
    reply_count: Optional[int] = None
    timestamp: Optional[str] = None
    
    # Analysis
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    is_promotional: bool = False
    mentions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScanConfig:
    """Scan configuration."""
    keywords: List[str]
    mode: InvestigationMode = InvestigationMode.quick
    limit: int = 60
    
    # Browser settings
    headless: bool = True
    locale: str = "en-US"
    user_agent: Optional[str] = None
    proxy: Optional[str] = None
    
    # Features
    screenshot: bool = False
    download: bool = False
    web_archive: bool = False
    comments_limit: int = 0
    pivot_hashtags: int = 0
    
    # Anti-detection
    antidetect_enabled: bool = True
    antidetect_aggressive: bool = False
    proxy_list: List[str] = field(default_factory=list)
    
    # Output
    output_base: str = "out/crot_dalam"
    
    def apply_mode_presets(self) -> None:
        """Apply mode-based presets."""
        if self.mode == InvestigationMode.moderate:
            self.screenshot = True
            self.comments_limit = max(self.comments_limit, 5)
        elif self.mode == InvestigationMode.deep:
            self.screenshot = True
            self.download = True
            self.web_archive = True
            self.comments_limit = max(self.comments_limit, 15)
            self.pivot_hashtags = max(self.pivot_hashtags, 3)
        elif self.mode == InvestigationMode.deeper:
            self.screenshot = True
            self.download = True
            self.web_archive = True
            self.comments_limit = max(self.comments_limit, 30)
            self.pivot_hashtags = max(self.pivot_hashtags, 5)
            self.antidetect_aggressive = True


@dataclass
class ScanResult:
    """Complete scan result."""
    scan_id: str
    status: ScanStatus
    config: ScanConfig
    
    # Results
    videos: List[VideoRecord] = field(default_factory=list)
    profiles: List[UserProfile] = field(default_factory=list)
    
    # Statistics
    total_videos: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    
    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    # Output paths
    output_jsonl: Optional[str] = None
    output_csv: Optional[str] = None
    output_html: Optional[str] = None
    
    # Errors
    errors: List[Dict[str, str]] = field(default_factory=list)
    
    def calculate_stats(self) -> None:
        """Calculate statistics from videos."""
        self.total_videos = len(self.videos)
        self.high_risk_count = sum(1 for v in self.videos if v.risk_score >= 5)
        self.medium_risk_count = sum(1 for v in self.videos if 2 <= v.risk_score < 5)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "status": self.status.value,
            "total_videos": self.total_videos,
            "high_risk_count": self.high_risk_count,
            "medium_risk_count": self.medium_risk_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "output_jsonl": self.output_jsonl,
            "output_csv": self.output_csv,
            "output_html": self.output_html,
            "errors": self.errors,
        }


@dataclass
class MonitorConfig:
    """Real-time monitoring configuration."""
    keywords: List[str]
    usernames: List[str] = field(default_factory=list)
    
    # Schedule
    interval_minutes: int = 30
    max_iterations: int = -1  # -1 = infinite
    
    # Alerts
    alert_on_high_risk: bool = True
    alert_webhook_url: Optional[str] = None
    alert_telegram_bot_token: Optional[str] = None
    alert_telegram_chat_id: Optional[str] = None
    
    # Options
    scan_config: Optional[ScanConfig] = None


@dataclass
class NetworkNode:
    """Node in relationship network."""
    id: str
    type: str  # "user", "hashtag", "video"
    label: str
    weight: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NetworkEdge:
    """Edge in relationship network."""
    source: str
    target: str
    type: str  # "uses_hashtag", "mentions", "comments_on"
    weight: int = 1


@dataclass
class NetworkGraph:
    """Relationship network graph."""
    nodes: List[NetworkNode] = field(default_factory=list)
    edges: List[NetworkEdge] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
        }
    
    def add_node(self, node_id: str, node_type: str, label: str, **metadata) -> None:
        """Add a node if not exists."""
        for n in self.nodes:
            if n.id == node_id:
                n.weight += 1
                return
        self.nodes.append(NetworkNode(id=node_id, type=node_type, label=label, metadata=metadata))
    
    def add_edge(self, source: str, target: str, edge_type: str) -> None:
        """Add an edge, incrementing weight if exists."""
        for e in self.edges:
            if e.source == source and e.target == target and e.type == edge_type:
                e.weight += 1
                return
        self.edges.append(NetworkEdge(source=source, target=target, type=edge_type))
