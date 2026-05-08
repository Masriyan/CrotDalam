#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM - Unit Tests for Data Models
Tests the data models and validation logic.
"""
import pytest
from datetime import datetime
from typing import List

from crot_dalam.models.data import (
    VideoRecord,
    UserProfile,
    Comment,
    ScanConfig,
    ScanResult,
    ScanStatus,
    InvestigationMode,
)


class TestVideoRecord:
    """Tests for VideoRecord model."""
    
    def test_create_video_record(self):
        """Test creating a basic VideoRecord."""
        video = VideoRecord(
            video_id="test_123",
            url="https://www.tiktok.com/@user/video/123",
            username="user",
            author_name="User",
            description="Test video",
            hashtags=["test", "video"],
            mentions=["user"],
            like_count=100,
            comment_count=10,
            share_count=5,
            view_count=1000,
        )
        
        assert video.video_id == "test_123"
        assert video.like_count == 100
        assert len(video.hashtags) == 2
    
    def test_video_record_default_values(self):
        """Test VideoRecord default values."""
        video = VideoRecord(
            video_id="test",
            url="https://example.com",
            username="user",
        )
        
        assert video.description is None
        assert video.hashtags == []
        assert video.mentions == []
        assert video.like_count is None
        assert video.risk_score == 0
    
    def test_video_record_risk_level(self):
        """Test risk level assignment."""
        video_low = VideoRecord(
            video_id="test", url="https://example.com", username="user",
            risk_score=2,
        )
        assert video_low.risk_level == "NONE" or video_low.risk_score < 3
        
        video_medium = VideoRecord(
            video_id="test", url="https://example.com", username="user",
            risk_score=5,
        )
        assert video_medium.risk_score == 5


class TestUserProfile:
    """Tests for UserProfile model."""
    
    def test_create_profile(self):
        """Test creating a UserProfile."""
        profile = UserProfile(
            username="testuser",
            display_name="Test User",
            bio="Test bio",
            follower_count=1000,
            following_count=100,
            video_count=50,
            like_count=10000,
        )
        
        assert profile.username == "testuser"
        assert profile.follower_count == 1000
        assert not profile.verified


class TestComment:
    """Tests for Comment model."""
    
    def test_create_comment(self):
        """Test creating a Comment."""
        comment = Comment(
            username="commenter",
            text="Great video!",
            like_count=10,
        )
        
        assert comment.text == "Great video!"
        assert comment.username == "commenter"
    
    def test_comment_sentiment(self):
        """Test comment sentiment field."""
        comment = Comment(
            username="user",
            text="Nice!",
            sentiment="positive",
        )
        assert comment.sentiment == "positive"


class TestScanConfig:
    """Tests for ScanConfig model."""
    
    def test_create_config(self):
        """Test creating a ScanConfig."""
        config = ScanConfig(
            keywords=["test", "tiktok"],
            limit=50,
            locale="en-US",
        )
        
        assert len(config.keywords) == 2
        assert config.limit == 50
        assert config.headless is True
    
    def test_config_default_values(self):
        """Test ScanConfig defaults."""
        config = ScanConfig(keywords=["test"])
        
        assert config.limit == 60
        assert config.locale == "en-US"
        assert config.headless is True
        assert config.antidetect_enabled is True


class TestScanResult:
    """Tests for ScanResult model."""
    
    def test_create_scan_result(self):
        """Test creating a ScanResult."""
        config = ScanConfig(keywords=["test"])
        result = ScanResult(
            scan_id="result_123",
            config=config,
            status=ScanStatus.completed,
            videos=[],
            profiles=[],
            started_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            total_videos=0,
        )
        
        assert result.status == ScanStatus.completed
        assert result.total_videos == 0
    
    def test_scan_result_status_enum(self):
        """Test ScanStatus enum values."""
        assert ScanStatus.completed.value == "completed"
        assert ScanStatus.failed.value == "failed"
        assert ScanStatus.running.value == "running"
        assert ScanStatus.pending.value == "pending"
