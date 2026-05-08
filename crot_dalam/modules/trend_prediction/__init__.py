#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Trend Prediction Module
AI-powered trend forecasting and viral content prediction.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from crot_dalam.models.data import VideoRecord, UserProfile


class TrendDirection(str, Enum):
    """Predicted trend direction."""
    EXPLODING = "exploding"  # Rapid growth expected
    RISING = "rising"  # Moderate growth
    STABLE = "stable"  # Maintaining current level
    DECLINING = "declining"  # Losing momentum
    EMERGING = "emerging"  # New pattern detected


@dataclass
class TrendSignal:
    """Individual signal contributing to trend prediction."""
    signal_type: str
    value: float
    weight: float
    description: str


@dataclass
class HashtagTrend:
    """Trend analysis for a hashtag."""
    hashtag: str
    current_usage: int
    growth_rate: float  # Percentage change per hour
    acceleration: float  # Change in growth rate
    predicted_peak: Optional[datetime] = None
    predicted_volume_24h: int = 0
    confidence: float = 0.0
    direction: TrendDirection = TrendDirection.STABLE
    related_hashtags: List[str] = field(default_factory=list)
    signals: List[TrendSignal] = field(default_factory=list)


@dataclass
class ViralPrediction:
    """Prediction for potential viral content."""
    video_id: str
    username: str
    current_views: int
    predicted_views_24h: int
    predicted_views_7d: int
    viral_probability: float  # 0-1
    time_to_viral: Optional[timedelta] = None
    key_factors: List[str] = field(default_factory=list)
    risk_indicators: List[str] = field(default_factory=list)


@dataclass
class CampaignPattern:
    """Detected coordinated campaign pattern."""
    pattern_id: str
    pattern_type: str  # "hashtag_campaign", "audio_trend", "challenge"
    participants: List[str]
    start_time: datetime
    growth_pattern: str  # "organic", "coordinated", "bot_amplified"
    confidence: float
    predicted_reach: int
    risk_score: float


class TrendPredictor:
    """
    AI-powered trend prediction engine.
    Analyzes patterns to forecast viral content and emerging trends.
    """

    def __init__(self, historical_window_hours: int = 72):
        self.historical_window = timedelta(hours=historical_window_hours)
        self.hashtag_history: Dict[str, List[Tuple[datetime, int]]] = defaultdict(list)
        self.video_metrics_history: Dict[str, List[Tuple[datetime, Dict[str, int]]]] = defaultdict(list)
        self.user_activity: Dict[str, List[datetime]] = defaultdict(list)

    def record_video(self, video: VideoRecord) -> None:
        """Record video metrics for trend analysis."""
        now = datetime.now()
        
        # Record hashtag usage
        for hashtag in video.hashtags:
            self.hashtag_history[hashtag].append((now, 1))
        
        # Record video metrics
        if video.video_id:
            metrics = {
                "views": video.view_count or 0,
                "likes": video.like_count or 0,
                "comments": video.comment_count or 0,
                "shares": video.share_count or 0
            }
            self.video_metrics_history[video.video_id].append((now, metrics))
        
        # Record user activity
        if video.username:
            self.user_activity[video.username].append(now)

    def analyze_hashtag_trends(
        self, 
        hashtags: Optional[List[str]] = None,
        top_n: int = 20
    ) -> List[HashtagTrend]:
        """Analyze and predict trends for hashtags."""
        if hashtags:
            target_hashtags = hashtags
        else:
            target_hashtags = list(self.hashtag_history.keys())
        
        trends = []
        
        for hashtag in target_hashtags[:top_n]:
            history = self.hashtag_history.get(hashtag, [])
            if len(history) < 2:
                continue
            
            # Sort by time
            history_sorted = sorted(history, key=lambda x: x[0])
            
            # Calculate metrics
            current_usage = len(history_sorted)
            
            # Time windows
            now = datetime.now()
            hour_ago = now - timedelta(hours=1)
            six_hours_ago = now - timedelta(hours=6)
            twenty_four_hours_ago = now - timedelta(hours=24)
            
            recent_1h = sum(1 for t, _ in history_sorted if t > hour_ago)
            recent_6h = sum(1 for t, _ in history_sorted if t > six_hours_ago)
            recent_24h = sum(1 for t, _ in history_sorted if t > twenty_four_hours_ago)
            
            # Growth rate (per hour)
            if recent_24h > 0:
                hourly_avg = recent_24h / 24.0
                growth_rate = ((recent_1h - hourly_avg) / max(hourly_avg, 1)) * 100
            else:
                growth_rate = 0.0
            
            # Acceleration
            if recent_6h > 0:
                avg_6h = recent_6h / 6.0
                prev_avg = (recent_24h - recent_6h) / 18.0 if recent_24h > recent_6h else avg_6h
                acceleration = ((avg_6h - prev_avg) / max(prev_avg, 1)) * 100
            else:
                acceleration = 0.0
            
            # Predict direction
            direction = self._classify_direction(growth_rate, acceleration)
            
            # Predict peak (simple exponential model)
            predicted_peak = None
            if growth_rate > 10 and acceleration > 0:
                # Estimate time to peak based on current acceleration
                hours_to_peak = max(1, int(100 / max(growth_rate, 1)))
                predicted_peak = now + timedelta(hours=hours_to_peak)
            
            # Predicted volume in next 24h
            if growth_rate > -50:
                predicted_volume_24h = int(recent_24h * (1 + growth_rate / 100) * 24)
            else:
                predicted_volume_24h = int(recent_24h * 0.5)
            
            # Confidence based on data quality
            confidence = min(0.9, 0.3 + (len(history_sorted) / 100) * 0.6)
            
            # Find related hashtags (co-occurrence)
            related = self._find_related_hashtags(hashtag)
            
            # Generate signals
            signals = self._generate_hashtag_signals(
                hashtag, growth_rate, acceleration, recent_1h, recent_24h
            )
            
            trends.append(HashtagTrend(
                hashtag=hashtag,
                current_usage=current_usage,
                growth_rate=growth_rate,
                acceleration=acceleration,
                predicted_peak=predicted_peak,
                predicted_volume_24h=predicted_volume_24h,
                confidence=confidence,
                direction=direction,
                related_hashtags=related[:5],
                signals=signals
            ))
        
        # Sort by growth rate and usage
        trends.sort(key=lambda t: t.growth_rate * math.log(t.current_usage + 1), reverse=True)
        return trends

    def predict_viral_videos(
        self,
        videos: List[VideoRecord],
        time_horizon_hours: int = 24
    ) -> List[ViralPrediction]:
        """Predict which videos are likely to go viral."""
        predictions = []
        
        for video in videos:
            if not video.video_id or not video.view_count:
                continue
            
            # Extract features
            engagement_rate = self._calculate_engagement_rate(video)
            velocity = self._calculate_velocity(video)
            account_authority = self._estimate_account_authority(video)
            
            # Viral probability model (simplified logistic function)
            features_score = (
                engagement_rate * 0.4 +
                min(velocity / 1000, 1.0) * 0.3 +
                account_authority * 0.2 +
                (1.0 if video.risk_score >= 5 else 0.0) * 0.1  # Controversial content spreads faster
            )
            
            viral_prob = 1 / (1 + math.exp(-5 * (features_score - 0.5)))
            
            # Predict views
            current_views = video.view_count or 0
            multiplier_24h = 1 + (viral_prob * 10 * (time_horizon_hours / 24))
            multiplier_7d = 1 + (viral_prob * 50)
            
            predicted_views_24h = int(current_views * multiplier_24h)
            predicted_views_7d = int(current_views * multiplier_7d)
            
            # Time to viral (if probable)
            time_to_viral = None
            if viral_prob > 0.7 and velocity > 0:
                views_needed = 100000  # Viral threshold
                if velocity > 0:
                    hours_needed = (views_needed - current_views) / velocity
                    if hours_needed > 0:
                        time_to_viral = timedelta(hours=hours_needed)
            
            # Key factors
            key_factors = []
            if engagement_rate > 0.1:
                key_factors.append("High engagement rate")
            if velocity > 1000:
                key_factors.append("Rapid view velocity")
            if account_authority > 0.7:
                key_factors.append("Authoritative account")
            if video.verified if hasattr(video, 'verified') else False:
                key_factors.append("Verified account")
            
            # Risk indicators
            risk_indicators = []
            if video.risk_score >= 7:
                risk_indicators.append("High risk content")
            if video.risk_level == "CRITICAL":
                risk_indicators.append("Critical risk level")
            
            predictions.append(ViralPrediction(
                video_id=video.video_id,
                username=video.username or "unknown",
                current_views=current_views,
                predicted_views_24h=predicted_views_24h,
                predicted_views_7d=predicted_views_7d,
                viral_probability=viral_prob,
                time_to_viral=time_to_viral,
                key_factors=key_factors,
                risk_indicators=risk_indicators
            ))
        
        # Sort by viral probability
        predictions.sort(key=lambda p: p.viral_probability, reverse=True)
        return predictions

    def detect_campaign_patterns(self) -> List[CampaignPattern]:
        """Detect coordinated campaign patterns."""
        campaigns = []
        
        # Analyze hashtag co-occurrence bursts
        hashtag_bursts = self._detect_hashtag_bursts()
        
        for burst_hashtags, start_time, participant_count in hashtag_bursts:
            if participant_count >= 5:
                # Determine growth pattern
                growth_pattern = self._classify_growth_pattern(burst_hashtags, start_time)
                
                # Calculate predicted reach
                avg_participants = participant_count
                predicted_reach = avg_participants * 1000  # Simplified estimate
                
                # Risk score based on coordination indicators
                risk_score = 0.0
                if growth_pattern == "coordinated":
                    risk_score += 0.5
                if growth_pattern == "bot_amplified":
                    risk_score += 0.8
                if len(burst_hashtags) <= 3:
                    risk_score += 0.2  # Focused messaging
                
                campaigns.append(CampaignPattern(
                    pattern_id=f"campaign_{start_time.strftime('%Y%m%d_%H%M')}",
                    pattern_type="hashtag_campaign",
                    participants=[],  # Would populate with actual usernames
                    start_time=start_time,
                    growth_pattern=growth_pattern,
                    confidence=min(0.9, 0.4 + participant_count * 0.05),
                    predicted_reach=predicted_reach,
                    risk_score=min(1.0, risk_score)
                ))
        
        return campaigns

    def _classify_direction(self, growth_rate: float, acceleration: float) -> TrendDirection:
        """Classify trend direction based on metrics."""
        if growth_rate > 100 and acceleration > 20:
            return TrendDirection.EXPLODING
        elif growth_rate > 30:
            return TrendDirection.RISING
        elif growth_rate > -10 and growth_rate <= 30:
            return TrendDirection.STABLE
        elif growth_rate <= -10 and growth_rate > -50:
            return TrendDirection.DECLINING
        elif growth_rate <= -50:
            return TrendDirection.DECLINING
        else:
            return TrendDirection.EMERGING

    def _find_related_hashtags(self, hashtag: str, limit: int = 10) -> List[str]:
        """Find hashtags that frequently co-occur."""
        cooccurrence = defaultdict(int)
        
        for vid_hashtags, _ in self.hashtag_history.values():
            pass  # Would need video-level data for accurate co-occurrence
        
        # Simplified: return empty for now
        return []

    def _generate_hashtag_signals(
        self,
        hashtag: str,
        growth_rate: float,
        acceleration: float,
        recent_1h: int,
        recent_24h: int
    ) -> List[TrendSignal]:
        """Generate explanatory signals for trend prediction."""
        signals = []
        
        if growth_rate > 100:
            signals.append(TrendSignal(
                signal_type="explosive_growth",
                value=growth_rate,
                weight=0.3,
                description=f"Usage increased {growth_rate:.0f}% in the last hour"
            ))
        
        if acceleration > 50:
            signals.append(TrendSignal(
                signal_type="accelerating",
                value=acceleration,
                weight=0.25,
                description=f"Growth rate accelerating by {acceleration:.0f}%"
            ))
        
        if recent_1h > recent_24h / 12 * 2:
            signals.append(TrendSignal(
                signal_type="spike_detected",
                value=recent_1h,
                weight=0.25,
                description=f"Unusual spike: {recent_1h} uses in last hour vs {recent_24h/24:.1f} avg"
            ))
        
        return signals

    def _calculate_engagement_rate(self, video: VideoRecord) -> float:
        """Calculate engagement rate for a video."""
        total_engagement = (
            (video.like_count or 0) +
            (video.comment_count or 0) * 2 +  # Comments weighted higher
            (video.share_count or 0) * 3  # Shares weighted highest
        )
        views = video.view_count or 1
        return total_engagement / views

    def _calculate_velocity(self, video: VideoRecord) -> float:
        """Calculate view velocity (views per hour)."""
        # Simplified: would need timestamp data
        return (video.view_count or 0) / 24.0

    def _estimate_account_authority(self, video: VideoRecord) -> float:
        """Estimate account authority score."""
        # Simplified heuristic
        score = 0.5  # Base score
        
        if video.like_count and video.like_count > 10000:
            score += 0.2
        if video.comment_count and video.comment_count > 1000:
            score += 0.1
        if video.risk_score < 3:
            score += 0.1
        
        return min(1.0, score)

    def _detect_hashtag_bursts(
        self,
        window_minutes: int = 60,
        min_participants: int = 5
    ) -> List[Tuple[List[str], datetime, int]]:
        """Detect sudden bursts of hashtag usage."""
        bursts = []
        now = datetime.now()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Group hashtags by time window
        hashtag_counts = defaultdict(int)
        for hashtag, history in self.hashtag_history.items():
            count = sum(1 for t, _ in history if t > window_start)
            if count >= min_participants:
                hashtag_counts[hashtag] = count
        
        # Identify bursts (hashtags with unusually high usage)
        if hashtag_counts:
            avg_count = sum(hashtag_counts.values()) / len(hashtag_counts)
            burst_hashtags = [
                h for h, c in hashtag_counts.items()
                if c > avg_count * 2
            ]
            
            if burst_hashtags:
                total_participants = sum(hashtag_counts[h] for h in burst_hashtags)
                bursts.append((burst_hashtags, window_start, total_participants))
        
        return bursts

    def _classify_growth_pattern(
        self,
        hashtags: List[str],
        start_time: datetime
    ) -> str:
        """Classify the growth pattern of a campaign."""
        # Simplified classification
        # In production, would analyze timing patterns, account ages, etc.
        
        duration = datetime.now() - start_time
        
        if duration.total_seconds() < 3600:  # Less than 1 hour
            return "coordinated"
        elif duration.total_seconds() < 86400:  # Less than 1 day
            return "organic"
        else:
            return "bot_amplified"

    def export_trend_report(
        self,
        videos: Optional[List[VideoRecord]] = None,
        include_predictions: bool = True
    ) -> Dict[str, Any]:
        """Export comprehensive trend analysis report."""
        hashtag_trends = self.analyze_hashtag_trends()
        campaigns = self.detect_campaign_patterns()
        
        report = {
            "summary": {
                "total_hashtags_tracked": len(self.hashtag_history),
                "trending_hashtags": len([t for t in hashtag_trends if t.direction in [TrendDirection.EXPLODING, TrendDirection.RISING]]),
                "active_campaigns": len(campaigns),
                "analysis_timestamp": datetime.now().isoformat()
            },
            "hashtag_trends": [
                {
                    "hashtag": t.hashtag,
                    "current_usage": t.current_usage,
                    "growth_rate": t.growth_rate,
                    "acceleration": t.acceleration,
                    "direction": t.direction.value,
                    "predicted_peak": t.predicted_peak.isoformat() if t.predicted_peak else None,
                    "predicted_volume_24h": t.predicted_volume_24h,
                    "confidence": t.confidence,
                    "related": t.related_hashtags,
                    "signals": [
                        {"type": s.signal_type, "description": s.description, "weight": s.weight}
                        for s in t.signals
                    ]
                }
                for t in hashtag_trends[:20]
            ],
            "campaigns": [
                {
                    "pattern_id": c.pattern_id,
                    "type": c.pattern_type,
                    "growth_pattern": c.growth_pattern,
                    "confidence": c.confidence,
                    "predicted_reach": c.predicted_reach,
                    "risk_score": c.risk_score,
                    "started": c.start_time.isoformat()
                }
                for c in campaigns
            ]
        }
        
        if include_predictions and videos:
            viral_predictions = self.predict_viral_videos(videos)
            report["viral_predictions"] = [
                {
                    "video_id": p.video_id,
                    "username": p.username,
                    "current_views": p.current_views,
                    "predicted_views_24h": p.predicted_views_24h,
                    "viral_probability": p.viral_probability,
                    "time_to_viral_hours": p.time_to_viral.total_seconds() / 3600 if p.time_to_viral else None,
                    "key_factors": p.key_factors,
                    "risk_indicators": p.risk_indicators
                }
                for p in viral_predictions[:10]
            ]
        
        return report
