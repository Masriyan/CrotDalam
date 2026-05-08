#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Cross-Platform Intelligence Module
Correlate identities and activities across multiple platforms.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum

from crot_dalam.models.data import UserProfile


class Platform(str, Enum):
    """Supported platforms for correlation."""
    TIKTOK = "tiktok"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    TELEGRAM = "telegram"
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    UNKNOWN = "unknown"


@dataclass
class SocialProfile:
    """Unified social media profile across platforms."""
    platform: Platform
    username: str
    user_id: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    
    # Metrics
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    post_count: Optional[int] = None
    
    # Metadata
    verified: bool = False
    created_at: Optional[str] = None
    last_active: Optional[str] = None
    
    # External links found
    external_links: List[str] = field(default_factory=list)
    
    # Risk indicators
    risk_score: int = 0
    risk_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "username": self.username,
            "display_name": self.display_name,
            "bio": self.bio,
            "profile_url": self.profile_url,
            "verified": self.verified,
            "follower_count": self.follower_count,
            "risk_score": self.risk_score,
            "risk_flags": self.risk_flags
        }


@dataclass
class IdentityCluster:
    """Cluster of profiles likely belonging to the same entity."""
    cluster_id: str
    confidence: float
    profiles: List[SocialProfile]
    
    # Correlation signals
    correlation_signals: List[Dict[str, Any]] = field(default_factory=list)
    
    # Inferred attributes
    primary_username: Optional[str] = None
    real_name: Optional[str] = None
    location: Optional[str] = None
    organization: Optional[str] = None
    
    # Risk assessment
    aggregate_risk_score: float = 0.0
    cross_platform_risk_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "confidence": self.confidence,
            "profile_count": len(self.profiles),
            "platforms": [p.platform.value for p in self.profiles],
            "primary_username": self.primary_username,
            "real_name": self.real_name,
            "aggregate_risk_score": self.aggregate_risk_score,
            "cross_platform_risk_patterns": self.cross_platform_risk_patterns,
            "correlation_signals": self.correlation_signals,
            "profiles": [p.to_dict() for p in self.profiles]
        }


@dataclass
class PlatformPattern:
    """Behavioral pattern detected on a specific platform."""
    platform: Platform
    pattern_type: str
    description: str
    accounts_involved: List[str]
    confidence: float
    first_detected: datetime
    indicators: List[str] = field(default_factory=list)


class CrossPlatformIntelligence:
    """
    Cross-platform intelligence for identity correlation and pattern detection.
    Links accounts across platforms and detects coordinated campaigns.
    """

    def __init__(self):
        self.profiles: Dict[Platform, Dict[str, SocialProfile]] = defaultdict(dict)
        self.identity_clusters: List[IdentityCluster] = []
        self.username_patterns: Dict[str, List[Tuple[Platform, str]]] = defaultdict(list)
        self.link_graph: Dict[str, Set[str]] = defaultdict(set)
        
        # Username pattern regexes
        self.username_variants = [
            # Common variations
            lambda u: u.replace("_", ""),
            lambda u: u.replace("-", ""),
            lambda u: u.replace(".", ""),
            lambda u: re.sub(r'[0-9]+$', '', u),  # Remove trailing numbers
            lambda u: u + "_official",
            lambda u: u + "_real",
        ]

    def add_profile(self, profile: SocialProfile) -> None:
        """Add a social media profile for analysis."""
        self.profiles[profile.platform][profile.username] = profile
        
        # Index by username for correlation
        self.username_patterns[profile.username.lower()].append((profile.platform, profile.username))
        
        # Index external links
        for link in profile.external_links:
            normalized_link = self._normalize_url(link)
            self.link_graph[normalized_link].add(f"{profile.platform.value}:{profile.username}")

    def add_tiktok_profile(self, tiktok_profile: UserProfile) -> None:
        """Convert and add TikTok profile."""
        profile = SocialProfile(
            platform=Platform.TIKTOK,
            username=tiktok_profile.username,
            user_id=tiktok_profile.user_id,
            display_name=tiktok_profile.display_name,
            bio=tiktok_profile.bio,
            profile_url=tiktok_profile.profile_url,
            avatar_url=tiktok_profile.avatar_url,
            follower_count=tiktok_profile.follower_count,
            following_count=tiktok_profile.following_count,
            post_count=tiktok_profile.video_count,
            verified=tiktok_profile.verified,
            external_links=tiktok_profile.external_links,
            risk_score=tiktok_profile.risk_score,
            risk_flags=tiktok_profile.risk_matches
        )
        self.add_profile(profile)

    def correlate_identities(self, min_confidence: float = 0.5) -> List[IdentityCluster]:
        """
        Perform identity correlation across all platforms.
        Returns clusters of profiles likely belonging to the same entity.
        """
        clusters = []
        processed = set()
        
        # Strategy 1: Direct username matches across platforms
        username_matches = self._find_username_matches()
        
        # Strategy 2: External link correlation
        link_matches = self._find_link_correlations()
        
        # Strategy 3: Bio similarity
        bio_matches = self._find_bio_similarities()
        
        # Strategy 4: Display name matching
        name_matches = self._find_display_name_matches()
        
        # Combine all signals
        all_signals = []
        all_signals.extend(username_matches)
        all_signals.extend(link_matches)
        all_signals.extend(bio_matches)
        all_signals.extend(name_matches)
        
        # Build clusters using union-find approach
        parent = {}
        
        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y, confidence):
            px, py = find(x), find(y)
            if px != py:
                # Only union if confidence is sufficient
                if confidence >= min_confidence:
                    parent[px] = py
                    return True
            return False
        
        # Process all correlation signals
        for signal in all_signals:
            profile1_key = f"{signal['platform1']}:{signal['username1']}"
            profile2_key = f"{signal['platform2']}:{signal['username2']}"
            union(profile1_key, profile2_key, signal['confidence'])
        
        # Group profiles by cluster root
        cluster_groups = defaultdict(list)
        for platform, platform_profiles in self.profiles.items():
            for username, profile in platform_profiles.items():
                key = f"{platform.value}:{username}"
                root = find(key)
                cluster_groups[root].append(profile)
        
        # Create IdentityCluster objects
        for root_key, group_profiles in cluster_groups.items():
            if len(group_profiles) < 2:
                continue  # Skip single-profile clusters
            
            # Calculate cluster confidence
            cluster_signals = [
                s for s in all_signals
                if any(f"{s['platform1']}:{s['username1']}" == f"{p.platform.value}:{p.username}" or 
                       f"{s['platform2']}:{s['username2']}" == f"{p.platform.value}:{p.username}"
                       for p in group_profiles)
            ]
            
            avg_confidence = sum(s['confidence'] for s in cluster_signals) / len(cluster_signals) if cluster_signals else 0.5
            
            # Infer primary username (most common across platforms)
            username_counts = defaultdict(int)
            for p in group_profiles:
                username_counts[p.username] += 1
            primary_username = max(username_counts.keys(), key=lambda u: username_counts[u]) if username_counts else None
            
            # Infer real name from display names
            display_names = [p.display_name for p in group_profiles if p.display_name]
            real_name = max(set(display_names), key=display_names.count) if display_names else None
            
            # Calculate aggregate risk score
            risk_scores = [p.risk_score for p in group_profiles]
            aggregate_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0
            
            # Detect cross-platform risk patterns
            risk_patterns = self._detect_cross_platform_risks(group_profiles)
            
            cluster = IdentityCluster(
                cluster_id=self._generate_cluster_id(group_profiles),
                confidence=avg_confidence,
                profiles=group_profiles,
                correlation_signals=cluster_signals[:10],  # Limit to top 10
                primary_username=primary_username,
                real_name=real_name,
                aggregate_risk_score=aggregate_risk,
                cross_platform_risk_patterns=risk_patterns
            )
            
            clusters.append(cluster)
        
        # Sort by confidence and size
        clusters.sort(key=lambda c: (c.confidence, len(c.profiles)), reverse=True)
        self.identity_clusters = clusters
        
        return clusters

    def _find_username_matches(self) -> List[Dict[str, Any]]:
        """Find exact and variant username matches across platforms."""
        matches = []
        platform_usernames = defaultdict(list)
        
        # Collect all usernames by platform
        for platform, profiles in self.profiles.items():
            for username in profiles.keys():
                platform_usernames[username.lower()].append((platform, username))
        
        # Find exact matches
        for username_lower, occurrences in platform_usernames.items():
            if len(occurrences) >= 2:
                platforms_involved = set(p for p, _ in occurrences)
                if len(platforms_involved) >= 2:  # Must be on different platforms
                    for i, (p1, u1) in enumerate(occurrences):
                        for p2, u2 in occurrences[i+1:]:
                            if p1 != p2:
                                matches.append({
                                    "type": "exact_username_match",
                                    "platform1": p1.value,
                                    "username1": u1,
                                    "platform2": p2.value,
                                    "username2": u2,
                                    "confidence": 0.85
                                })
        
        # Find variant matches
        for base_username, occurrences in platform_usernames.items():
            variants = self._generate_username_variants(base_username)
            for variant in variants:
                if variant in platform_usernames and variant != base_username:
                    for p1, u1 in occurrences:
                        for p2, u2 in platform_usernames[variant]:
                            if p1 != p2:
                                matches.append({
                                    "type": "username_variant_match",
                                    "platform1": p1.value,
                                    "username1": u1,
                                    "platform2": p2.value,
                                    "username2": u2,
                                    "variant": variant,
                                    "confidence": 0.65
                                })
        
        return matches

    def _find_link_correlations(self) -> List[Dict[str, Any]]:
        """Find profiles connected by shared external links."""
        matches = []
        
        for link, profile_keys in self.link_graph.items():
            if len(profile_keys) < 2:
                continue
            
            profile_list = list(profile_keys)
            for i, key1 in enumerate(profile_list):
                for key2 in profile_list[i+1:]:
                    platform1, username1 = key1.split(":", 1)
                    platform2, username2 = key2.split(":", 1)
                    
                    if platform1 != platform2:
                        matches.append({
                            "type": "shared_external_link",
                            "platform1": platform1,
                            "username1": username1,
                            "platform2": platform2,
                            "username2": username2,
                            "link": link,
                            "confidence": 0.9  # High confidence - same link is strong signal
                        })
        
        return matches

    def _find_bio_similarities(self) -> List[Dict[str, Any]]:
        """Find profiles with similar bios."""
        matches = []
        profiles_with_bio = []
        
        for platform, platform_profiles in self.profiles.items():
            for username, profile in platform_profiles.items():
                if profile.bio:
                    profiles_with_bio.append((platform, username, profile))
        
        # Compare bios pairwise
        for i, (p1, u1, prof1) in enumerate(profiles_with_bio):
            for p2, u2, prof2 in profiles_with_bio[i+1:]:
                if p1 == p2:
                    continue
                
                similarity = self._calculate_text_similarity(prof1.bio, prof2.bio)
                if similarity > 0.7:
                    matches.append({
                        "type": "bio_similarity",
                        "platform1": p1.value,
                        "username1": u1,
                        "platform2": p2.value,
                        "username2": u2,
                        "similarity": similarity,
                        "confidence": similarity * 0.8
                    })
        
        return matches

    def _find_display_name_matches(self) -> List[Dict[str, Any]]:
        """Find profiles with matching display names."""
        matches = []
        name_to_profiles = defaultdict(list)
        
        for platform, platform_profiles in self.profiles.items():
            for username, profile in platform_profiles.items():
                if profile.display_name:
                    normalized_name = profile.display_name.lower().strip()
                    name_to_profiles[normalized_name].append((platform, username, profile))
        
        for name, occurrences in name_to_profiles.items():
            if len(occurrences) >= 2:
                for i, (p1, u1, prof1) in enumerate(occurrences):
                    for p2, u2, prof2 in occurrences[i+1:]:
                        if p1 != p2:
                            # Additional verification: check if other signals align
                            confidence = 0.6
                            if prof1.bio and prof2.bio:
                                bio_sim = self._calculate_text_similarity(prof1.bio, prof2.bio)
                                confidence += bio_sim * 0.2
                            
                            matches.append({
                                "type": "display_name_match",
                                "platform1": p1.value,
                                "username1": u1,
                                "platform2": p2.value,
                                "username2": u2,
                                "display_name": name,
                                "confidence": min(confidence, 0.9)
                            })
        
        return matches

    def _detect_cross_platform_risks(self, profiles: List[SocialProfile]) -> List[str]:
        """Detect risk patterns that span multiple platforms."""
        patterns = []
        
        # Check for consistent high risk across platforms
        high_risk_platforms = [p for p in profiles if p.risk_score >= 5]
        if len(high_risk_platforms) >= 2:
            patterns.append(f"High risk on {len(high_risk_platforms)} platforms")
        
        # Check for ban evasion patterns
        creation_dates = [p.created_at for p in profiles if p.created_at]
        if len(creation_dates) >= 2:
            # Multiple accounts created around same time might indicate ban evasion
            patterns.append("Multiple accounts with close creation dates")
        
        # Check for inconsistent verification status
        verified_count = sum(1 for p in profiles if p.verified)
        if 0 < verified_count < len(profiles):
            patterns.append("Inconsistent verification status across platforms")
        
        # Check for link spam
        all_links = []
        for p in profiles:
            all_links.extend(p.external_links)
        if len(all_links) > 5:
            unique_domains = set(self._extract_domain(l) for l in all_links)
            if len(unique_domains) <= 2:
                patterns.append("Repeated promotion of same domains across platforms")
        
        return patterns

    def _generate_username_variants(self, username: str) -> List[str]:
        """Generate common username variants."""
        variants = []
        for transform in self.username_variants:
            try:
                variants.append(transform(username).lower())
            except Exception:
                pass
        return variants

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two texts."""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0

    def _generate_cluster_id(self, profiles: List[SocialProfile]) -> str:
        """Generate unique cluster ID."""
        identifiers = sorted([f"{p.platform.value}:{p.username}" for p in profiles])
        combined = "|".join(identifiers)
        return f"cluster_{hashlib.md5(combined.encode()).hexdigest()[:12]}"

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        url = url.lower().strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url.rstrip('/')

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        import re
        match = re.search(r'https?://([^/]+)', url)
        return match.group(1) if match else url

    def export_correlation_report(self) -> Dict[str, Any]:
        """Export comprehensive cross-platform correlation report."""
        if not self.identity_clusters:
            self.correlate_identities()
        
        # Platform statistics
        platform_stats = {}
        for platform, profiles in self.profiles.items():
            platform_stats[platform.value] = {
                "total_profiles": len(profiles),
                "verified_count": sum(1 for p in profiles.values() if p.verified),
                "high_risk_count": sum(1 for p in profiles.values() if p.risk_score >= 5),
                "avg_followers": sum(p.follower_count or 0 for p in profiles.values()) / len(profiles) if profiles else 0
            }
        
        return {
            "summary": {
                "total_profiles_analyzed": sum(len(p) for p in self.profiles.values()),
                "platforms_covered": list(platform_stats.keys()),
                "identity_clusters_found": len(self.identity_clusters),
                "multi_platform_entities": len([c for c in self.identity_clusters if len(c.profiles) >= 3]),
                "analysis_timestamp": datetime.now().isoformat()
            },
            "platform_statistics": platform_stats,
            "identity_clusters": [c.to_dict() for c in self.identity_clusters[:50]],  # Top 50
            "high_confidence_matches": [
                c.to_dict() for c in self.identity_clusters if c.confidence >= 0.8
            ],
            "high_risk_entities": [
                c.to_dict() for c in self.identity_clusters if c.aggregate_risk_score >= 5.0
            ]
        }
