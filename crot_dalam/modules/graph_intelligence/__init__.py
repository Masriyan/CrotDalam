#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Graph Intelligence Module
Entity resolution, influence network mapping, and relationship discovery.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime

from crot_dalam.models.data import NetworkGraph, NetworkNode, NetworkEdge, VideoRecord, UserProfile


@dataclass
class Entity:
    """Represents a resolved entity (person, organization, campaign)."""
    entity_id: str
    entity_type: str  # "person", "organization", "campaign", "bot_network"
    confidence: float
    aliases: Set[str] = field(default_factory=set)
    associated_accounts: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

    def merge(self, other: Entity) -> None:
        """Merge another entity into this one."""
        self.aliases.update(other.aliases)
        self.associated_accounts.update(other.associated_accounts)
        self.metadata.update(other.metadata)
        if other.first_seen and (not self.first_seen or other.first_seen < self.first_seen):
            self.first_seen = other.first_seen
        if other.last_seen and (not self.last_seen or other.last_seen > self.last_seen):
            self.last_seen = other.last_seen


@dataclass
class InfluenceScore:
    """Calculated influence metrics for an entity."""
    account_id: str
    reach_score: float  # Based on followers, views
    engagement_score: float  # Based on likes, comments, shares
    authority_score: float  # Based on verification, mentions by others
    network_centrality: float  # Based on graph position
    overall_score: float
    risk_multiplier: float = 1.0

    def get_adjusted_score(self) -> float:
        """Get overall score adjusted by risk."""
        return self.overall_score * self.risk_multiplier


class GraphIntelligence:
    """
    Advanced graph intelligence for OSINT analysis.
    Performs entity resolution, network analysis, and influence mapping.
    """

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.graph = NetworkGraph()
        self.account_profiles: Dict[str, UserProfile] = {}
        self.video_records: Dict[str, VideoRecord] = {}

    def add_video(self, video: VideoRecord) -> None:
        """Add video record to the graph."""
        self.video_records[video.video_id] = video
        
        # Add user node
        if video.username:
            self.graph.add_node(
                node_id=f"user:{video.username}",
                node_type="user",
                label=f"@{video.username}",
                author_name=video.author_name,
                risk_score=video.risk_score
            )
            
            # Add video node
            self.graph.add_node(
                node_id=f"video:{video.video_id}",
                node_type="video",
                label=video.video_id[:12],
                risk_score=video.risk_score,
                views=video.view_count,
                likes=video.like_count
            )
            
            # Edge: user posted video
            self.graph.add_edge(
                source=f"user:{video.username}",
                target=f"video:{video.video_id}",
                edge_type="posted"
            )
        
        # Add hashtag nodes and edges
        for hashtag in video.hashtags:
            self.graph.add_node(
                node_id=f"hashtag:{hashtag}",
                node_type="hashtag",
                label=f"#{hashtag}",
                usage_count=1
            )
            if video.username:
                self.graph.add_edge(
                    source=f"user:{video.username}",
                    target=f"hashtag:{hashtag}",
                    edge_type="uses"
                )
        
        # Add mention edges
        for mention in video.mentions:
            self.graph.add_node(
                node_id=f"user:{mention}",
                node_type="user",
                label=f"@{mention}"
            )
            if video.username:
                self.graph.add_edge(
                    source=f"user:{video.username}",
                    target=f"user:{mention}",
                    edge_type="mentions"
                )

    def add_profile(self, profile: UserProfile) -> None:
        """Add user profile to the graph."""
        self.account_profiles[profile.username] = profile
        self.graph.add_node(
            node_id=f"user:{profile.username}",
            node_type="user",
            label=f"@{profile.display_name or profile.username}",
            follower_count=profile.follower_count,
            following_count=profile.following_count,
            verified=profile.verified,
            risk_score=profile.risk_score
        )

    def resolve_entities(self) -> List[Entity]:
        """
        Perform entity resolution to identify unique entities.
        Uses multiple signals: username patterns, bio similarity, external links.
        """
        resolved = []
        processed = set()

        for username, profile in self.account_profiles.items():
            if username in processed:
                continue

            # Create initial entity
            entity_id = self._generate_entity_id(username, profile)
            entity = Entity(
                entity_id=entity_id,
                entity_type="person",
                confidence=0.7,
                aliases={username},
                associated_accounts={username},
                first_seen=profile.scraped_at,
                last_seen=profile.scraped_at,
                metadata={
                    "bio": profile.bio,
                    "external_links": profile.external_links,
                    "display_name": profile.display_name
                }
            )

            # Find potential matches
            candidates = self._find_entity_matches(username, profile)
            
            for candidate_username, match_confidence in candidates:
                if candidate_username != username and candidate_username not in processed:
                    candidate_profile = self.account_profiles.get(candidate_username)
                    if candidate_profile:
                        entity.aliases.add(candidate_username)
                        entity.associated_accounts.add(candidate_username)
                        entity.confidence = max(entity.confidence, match_confidence)
                        processed.add(candidate_username)

            resolved.append(entity)
            processed.add(username)
            self.entities[entity.entity_id] = entity

        return resolved

    def _generate_entity_id(self, username: str, profile: UserProfile) -> str:
        """Generate unique entity ID based on profile characteristics."""
        key_parts = [
            profile.bio or "",
            "|".join(sorted(profile.external_links)),
            profile.display_name or ""
        ]
        key = ":".join(key_parts)
        hash_val = hashlib.sha256(key.encode()).hexdigest()[:16]
        return f"entity:{hash_val}"

    def _find_entity_matches(
        self, 
        username: str, 
        profile: UserProfile
    ) -> List[Tuple[str, float]]:
        """Find accounts that likely belong to the same entity."""
        matches = []
        
        for other_username, other_profile in self.account_profiles.items():
            if other_username == username:
                continue
            
            confidence = 0.0
            
            # Same external links
            common_links = set(profile.external_links) & set(other_profile.external_links)
            if common_links:
                confidence += 0.4 * min(len(common_links), 3)
            
            # Similar bio (simple Jaccard similarity)
            if profile.bio and other_profile.bio:
                bio_words1 = set(profile.bio.lower().split())
                bio_words2 = set(other_profile.bio.lower().split())
                if bio_words1 and bio_words2:
                    intersection = len(bio_words1 & bio_words2)
                    union = len(bio_words1 | bio_words2)
                    bio_similarity = intersection / union if union > 0 else 0
                    confidence += 0.3 * bio_similarity
            
            # Same display name
            if profile.display_name and profile.display_name == other_profile.display_name:
                confidence += 0.3
            
            if confidence >= 0.3:
                matches.append((other_username, min(confidence, 1.0)))

        return sorted(matches, key=lambda x: x[1], reverse=True)

    def calculate_influence_scores(self) -> Dict[str, InfluenceScore]:
        """Calculate influence scores for all accounts."""
        scores = {}
        
        # Pre-calculate graph centrality
        centrality = self._calculate_degree_centrality()
        
        for username, profile in self.account_profiles.items():
            # Reach score (0-1 normalized)
            max_followers = max((p.follower_count or 0) for p in self.account_profiles.values()) or 1
            reach_score = (profile.follower_count or 0) / max_followers
            
            # Engagement score
            total_engagement = (
                (profile.like_count or 0) + 
                (profile.follower_count or 0) * 0.1  # Estimate
            )
            max_engagement = max(
                (p.like_count or 0) + (p.follower_count or 0) * 0.1 
                for p in self.account_profiles.values()
            ) or 1
            engagement_score = total_engagement / max_engagement
            
            # Authority score
            authority_score = 0.0
            if profile.verified:
                authority_score += 0.5
            # Count mentions by others
            mention_count = sum(
                1 for v in self.video_records.values() 
                if v.username != username and username in v.mentions
            )
            authority_score += min(mention_count * 0.1, 0.5)
            
            # Network centrality
            network_centrality = centrality.get(f"user:{username}", 0.0)
            
            # Overall score (weighted average)
            overall_score = (
                reach_score * 0.3 +
                engagement_score * 0.3 +
                authority_score * 0.2 +
                network_centrality * 0.2
            )
            
            # Risk multiplier
            risk_multiplier = 1.0 + (profile.risk_score / 10.0)
            
            scores[username] = InfluenceScore(
                account_id=username,
                reach_score=reach_score,
                engagement_score=engagement_score,
                authority_score=authority_score,
                network_centrality=network_centrality,
                overall_score=overall_score,
                risk_multiplier=risk_multiplier
            )

        return scores

    def _calculate_degree_centrality(self) -> Dict[str, float]:
        """Calculate degree centrality for all nodes."""
        centrality = defaultdict(float)
        node_count = len(self.graph.nodes)
        
        if node_count <= 1:
            return centrality
        
        for edge in self.graph.edges:
            centrality[edge.source] += 1
            centrality[edge.target] += 1
        
        # Normalize
        for node_id in centrality:
            centrality[node_id] /= (node_count - 1)
        
        return dict(centrality)

    def detect_bot_networks(self) -> List[Dict[str, Any]]:
        """Detect potential bot networks based on behavior patterns."""
        networks = []
        
        # Group by similar posting patterns, external links, etc.
        link_groups = defaultdict(list)
        for username, profile in self.account_profiles.items():
            for link in profile.external_links:
                link_groups[link].append(username)
        
        # Identify clusters with shared infrastructure
        for link, accounts in link_groups.items():
            if len(accounts) >= 3:
                networks.append({
                    "type": "shared_infrastructure",
                    "indicator": f"shared_link:{link}",
                    "accounts": accounts,
                    "confidence": min(0.5 + len(accounts) * 0.1, 0.95),
                    "description": f"{len(accounts)} accounts sharing link: {link}"
                })
        
        # Detect coordinated behavior (similar hashtags, timing)
        hashtag_cooccurrence = defaultdict(set)
        for video in self.video_records.values():
            if video.username and len(video.hashtags) >= 2:
                for i, h1 in enumerate(video.hashtags):
                    for h2 in video.hashtags[i+1:]:
                        pair = tuple(sorted([h1, h2]))
                        hashtag_cooccurrence[pair].add(video.username)
        
        for (h1, h2), accounts in hashtag_cooccurrence.items():
            if len(accounts) >= 5:
                networks.append({
                    "type": "coordinated_hashtags",
                    "indicator": f"hashtag_pair:{h1},{h2}",
                    "accounts": list(accounts),
                    "confidence": min(0.4 + len(accounts) * 0.08, 0.9),
                    "description": f"{len(accounts)} accounts using same hashtag pair: #{h1} #{h2}"
                })

        return networks

    def build_influence_network(self, top_n: int = 20) -> NetworkGraph:
        """Build a subgraph of most influential accounts."""
        scores = self.calculate_influence_scores()
        top_accounts = sorted(
            scores.items(), 
            key=lambda x: x[1].get_adjusted_score(), 
            reverse=True
        )[:top_n]
        
        top_usernames = {acc for acc, _ in top_accounts}
        
        subgraph = NetworkGraph()
        
        # Add top nodes
        for username in top_usernames:
            if username in self.account_profiles:
                profile = self.account_profiles[username]
                subgraph.add_node(
                    node_id=f"user:{username}",
                    node_type="user",
                    label=f"@{username}",
                    influence_score=scores[username].overall_score,
                    verified=profile.verified
                )
        
        # Add edges between top accounts
        for edge in self.graph.edges:
            if edge.type == "mentions":
                src_user = edge.source.replace("user:", "")
                tgt_user = edge.target.replace("user:", "")
                if src_user in top_usernames and tgt_user in top_usernames:
                    subgraph.edges.append(edge)

        return subgraph

    def export_graph_data(self) -> Dict[str, Any]:
        """Export complete graph data for visualization."""
        entities = self.resolve_entities()
        scores = self.calculate_influence_scores()
        bot_networks = self.detect_bot_networks()
        
        return {
            "graph": self.graph.to_dict(),
            "entities": [
                {
                    "entity_id": e.entity_id,
                    "type": e.entity_type,
                    "confidence": e.confidence,
                    "aliases": list(e.aliases),
                    "account_count": len(e.associated_accounts),
                    "first_seen": e.first_seen,
                    "last_seen": e.last_seen
                }
                for e in entities
            ],
            "influence_scores": {
                k: {
                    "reach": v.reach_score,
                    "engagement": v.engagement_score,
                    "authority": v.authority_score,
                    "centrality": v.network_centrality,
                    "overall": v.overall_score,
                    "adjusted": v.get_adjusted_score()
                }
                for k, v in scores.items()
            },
            "detected_networks": bot_networks,
            "statistics": {
                "total_nodes": len(self.graph.nodes),
                "total_edges": len(self.graph.edges),
                "total_entities": len(entities),
                "total_accounts": len(self.account_profiles),
                "total_videos": len(self.video_records)
            },
            "generated_at": datetime.now().isoformat()
        }
