#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Deep User Profile Investigation Module
Provides credibility scoring, account age estimation, and engagement analysis.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from crot_dalam.models.data import UserProfile


@dataclass
class CredibilityReport:
    """User credibility assessment report."""
    username: str
    overall_score: float = 0.0       # 0-100
    credibility_level: str = "UNKNOWN"  # LOW / MEDIUM / HIGH / VERIFIED
    
    # Component scores
    engagement_ratio: float = 0.0
    follower_following_ratio: float = 0.0
    account_activity_score: float = 0.0
    bio_risk_score: float = 0.0
    
    # Flags
    flags: List[str] = field(default_factory=list)
    
    # Analysis details
    estimated_account_age: str = "unknown"
    engagement_quality: str = "unknown"
    follower_anomaly: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "username": self.username,
            "overall_score": self.overall_score,
            "credibility_level": self.credibility_level,
            "engagement_ratio": self.engagement_ratio,
            "follower_following_ratio": self.follower_following_ratio,
            "account_activity_score": self.account_activity_score,
            "bio_risk_score": self.bio_risk_score,
            "flags": self.flags,
            "estimated_account_age": self.estimated_account_age,
            "engagement_quality": self.engagement_quality,
            "follower_anomaly": self.follower_anomaly,
        }


class ProfileAnalyzer:
    """
    Deep profile analysis engine.
    
    Analyzes TikTok user profiles for credibility assessment,
    engagement anomalies, and suspicious patterns.
    """
    
    # Suspicious bio patterns
    _SUSPICIOUS_BIO_PATTERNS = [
        r"(?i)dm\s+me",
        r"(?i)link\s+in\s+bio",
        r"(?i)wa\.me",
        r"(?i)t\.me/",
        r"(?i)telegram",
        r"(?i)whatsapp",
        r"(?i)invest(?:ment|ing)?",
        r"(?i)earn\s+\$?\d+",
        r"(?i)make\s+money",
        r"(?i)free\s+(?:gift|cash|prize)",
        r"(?i)click\s+(?:here|link)",
        r"(?i)limited\s+(?:time|offer)",
        r"(?i)passive\s+income",
        r"(?i)crypto\s+(?:trading|signal)",
        r"(?i)forex\s+(?:trading|signal)",
        r"(?i)binary\s+option",
    ]
    
    # Wallet regex patterns
    _WALLET_PATTERNS = [
        r"\b(0x[a-fA-F0-9]{40})\b",           # ETH/ERC-20
        r"\b([13][a-km-zA-HJ-NP-Z1-9]{25,34})\b",  # BTC
        r"\b(bc1[a-zA-HJ-NP-Z0-9]{39,59})\b",      # BTC Bech32
        r"\b(T[A-Za-z1-9]{33})\b",                   # TRX
        r"\b([1-9A-HJ-NP-Za-km-z]{32,44})\b",       # SOL (base58)
    ]
    
    def analyze_profile(self, profile: UserProfile) -> CredibilityReport:
        """
        Perform deep credibility analysis on a user profile.
        Returns a comprehensive credibility report.
        """
        report = CredibilityReport(username=profile.username)
        
        # 1. Follower/following ratio analysis
        report.follower_following_ratio = self._analyze_follower_ratio(
            profile.follower_count, profile.following_count
        )
        
        # 2. Engagement analysis
        report.engagement_ratio = self._analyze_engagement(
            profile.follower_count, profile.like_count, profile.video_count
        )
        
        # 3. Bio analysis
        report.bio_risk_score = self._analyze_bio(profile.bio, report.flags)
        
        # 4. Account activity assessment
        report.account_activity_score = self._assess_activity(
            profile.video_count, profile.like_count
        )
        
        # 5. Follower anomaly detection
        report.follower_anomaly = self._detect_follower_anomaly(
            profile.follower_count, profile.following_count,
            profile.like_count, profile.video_count
        )
        if report.follower_anomaly:
            report.flags.append("FOLLOWER_ANOMALY_DETECTED")
        
        # 6. Verified account boost
        verified_boost = 20.0 if profile.verified else 0.0
        
        # Calculate overall credibility score (0-100)
        raw_score = (
            report.follower_following_ratio * 0.20
            + report.engagement_ratio * 0.25
            + report.account_activity_score * 0.20
            + (100 - report.bio_risk_score) * 0.15
            + (0 if report.follower_anomaly else 20) * 1.0
            + verified_boost
        )
        
        report.overall_score = round(max(0, min(100, raw_score)), 1)
        
        # Determine credibility level
        if profile.verified:
            report.credibility_level = "VERIFIED"
        elif report.overall_score >= 70:
            report.credibility_level = "HIGH"
        elif report.overall_score >= 40:
            report.credibility_level = "MEDIUM"
        else:
            report.credibility_level = "LOW"
        
        # Set engagement quality
        if report.engagement_ratio >= 5:
            report.engagement_quality = "excellent"
        elif report.engagement_ratio >= 2:
            report.engagement_quality = "good"
        elif report.engagement_ratio >= 0.5:
            report.engagement_quality = "average"
        else:
            report.engagement_quality = "poor"
        
        return report
    
    def _analyze_follower_ratio(
        self, followers: Optional[int], following: Optional[int]
    ) -> float:
        """Analyze follower-to-following ratio. Returns score 0-100."""
        if not followers or not following:
            return 50.0  # Neutral if data unavailable
        
        if following == 0:
            return 90.0 if followers > 100 else 50.0
        
        ratio = followers / following
        
        # Very high ratio = likely authentic creator
        if ratio > 10:
            return 90.0
        elif ratio > 3:
            return 75.0
        elif ratio > 1:
            return 60.0
        elif ratio > 0.5:
            return 45.0
        else:
            # Following way more than followers — potentially bot-like
            return 25.0
    
    def _analyze_engagement(
        self, followers: Optional[int], likes: Optional[int],
        videos: Optional[int]
    ) -> float:
        """Analyze engagement quality. Returns score 0-100."""
        if not followers or followers == 0:
            return 30.0
        
        # Likes per follower
        likes = likes or 0
        likes_per_follower = likes / followers
        
        # Average likes per video
        videos = videos or 1
        avg_likes_per_video = likes / max(videos, 1)
        
        # Engagement rate estimation
        engagement_rate = avg_likes_per_video / followers * 100 if followers > 0 else 0
        
        if engagement_rate > 5:
            return 90.0
        elif engagement_rate > 2:
            return 75.0
        elif engagement_rate > 0.5:
            return 55.0
        elif engagement_rate > 0.1:
            return 35.0
        else:
            return 15.0
    
    def _analyze_bio(self, bio: Optional[str], flags: List[str]) -> float:
        """Analyze bio for suspicious content. Returns risk score 0-100."""
        if not bio:
            return 0.0
        
        suspicious_count = 0
        for pattern in self._SUSPICIOUS_BIO_PATTERNS:
            if re.search(pattern, bio):
                suspicious_count += 1
                flags.append(f"BIO_SUSPICIOUS: {pattern}")
        
        # Check for wallet addresses
        for pattern in self._WALLET_PATTERNS:
            if re.search(pattern, bio):
                suspicious_count += 2
                flags.append("BIO_CONTAINS_WALLET_ADDRESS")
                break
        
        # Check for excessive URLs
        url_count = len(re.findall(r"https?://\S+", bio))
        if url_count > 2:
            suspicious_count += 1
            flags.append("BIO_EXCESSIVE_URLS")
        
        return min(100, suspicious_count * 15)
    
    def _assess_activity(
        self, videos: Optional[int], likes: Optional[int]
    ) -> float:
        """Assess account activity level. Returns score 0-100."""
        videos = videos or 0
        likes = likes or 0
        
        if videos >= 50 and likes >= 1000:
            return 90.0
        elif videos >= 20 and likes >= 500:
            return 70.0
        elif videos >= 5 and likes >= 100:
            return 50.0
        elif videos >= 1:
            return 30.0
        else:
            return 10.0
    
    def _detect_follower_anomaly(
        self, followers: Optional[int], following: Optional[int],
        likes: Optional[int], videos: Optional[int]
    ) -> bool:
        """Detect anomalous follower patterns (purchased followers, bots)."""
        if not followers or followers < 100:
            return False
        
        likes = likes or 0
        videos = videos or 0
        
        # Very high followers but almost no likes — bot followers
        if followers > 10000 and likes < followers * 0.01:
            return True
        
        # Many followers but no content
        if followers > 5000 and videos < 3:
            return True
        
        # Extreme ratio without verification (could be mass follow-back)
        following = following or 0
        if following > 0 and followers / following > 100 and videos < 5:
            return True
        
        return False
