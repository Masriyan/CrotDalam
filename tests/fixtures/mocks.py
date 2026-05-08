#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM - Test Fixtures and Mocks
Provides mock objects and fixtures for testing without external dependencies.
"""
import pytest
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import MagicMock, AsyncMock, patch
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from crot_dalam.models.data import (
    VideoRecord,
    UserProfile,
    Comment,
    ScanConfig,
    ScanResult,
    ScanStatus,
)


# =============================================================================
# Mock Data Factories
# =============================================================================

def create_mock_video_record(
    video_id: str = "test_video_123",
    url: str = "https://www.tiktok.com/@testuser/video/123456789",
    description: str = "Test video description #hashtag @mention",
    username: str = "testuser",
    likes: int = 1000,
    comments: int = 50,
    shares: int = 25,
    views: int = 10000,
    risk_score: int = 3,
) -> VideoRecord:
    """Create a mock VideoRecord for testing."""
    return VideoRecord(
        video_id=video_id,
        url=url,
        username=username,
        author_name=username,
        description=description,
        hashtags=["hashtag"],
        mentions=["mention"],
        extracted_urls=[],
        like_count=likes,
        comment_count=comments,
        share_count=shares,
        view_count=views,
        risk_score=risk_score,
        risk_level="LOW" if risk_score < 3 else "MEDIUM" if risk_score < 6 else "HIGH",
        scraped_at=datetime.now().isoformat(),
    )


def create_mock_profile(
    username: str = "testuser",
    display_name: str = "Test User",
    followers: int = 5000,
    following: int = 500,
    videos: int = 100,
    likes: int = 50000,
) -> UserProfile:
    """Create a mock UserProfile for testing."""
    return UserProfile(
        username=username,
        display_name=display_name,
        bio="Test bio",
        followers_count=followers,
        following_count=following,
        video_count=videos,
        total_likes=likes,
        verified=False,
        private=False,
        collected_at=datetime.now(),
        locale="en",
    )


def create_mock_comment(
    comment_id: str = "comment_123",
    text: str = "Great video!",
    author: str = "commenter",
    risk_score: float = 0.1,
) -> Comment:
    """Create a mock Comment for testing."""
    return Comment(
        id=comment_id,
        text=text,
        author=author,
        collected_at=datetime.now(),
        risk_score=risk_score,
        risk_level="LOW" if risk_score < 0.5 else "MEDIUM" if risk_score < 0.7 else "HIGH",
    )


def create_mock_scan_config(
    keywords: List[str] = ["test"],
    max_results: int = 10,
    locale: str = "en",
    headless: bool = True,
    **kwargs
) -> ScanConfig:
    """Create a mock ScanConfig for testing."""
    return ScanConfig(
        keywords=keywords,
        max_results=max_results,
        locale=locale,
        headless=headless,
        collect_comments=kwargs.get("collect_comments", False),
        antidetect_enabled=kwargs.get("antidetect_enabled", True),
        antidetect_aggressive=kwargs.get("antidetect_aggressive", False),
        proxy_list=kwargs.get("proxy_list", []),
        user_agent=kwargs.get("user_agent", None),
        scroll_delay=kwargs.get("scroll_delay", 1.0),
        output_format=kwargs.get("output_format", "json"),
        output_dir=kwargs.get("output_dir", "./output"),
    )


def create_mock_scan_result(
    config: ScanConfig = None,
    videos: List[VideoRecord] = None,
    status: ScanStatus = ScanStatus.completed,
    total_videos: int = 10,
    total_errors: int = 0,
) -> ScanResult:
    """Create a mock ScanResult for testing."""
    config = config or create_mock_scan_config()
    videos = videos or [create_mock_video_record() for _ in range(total_videos)]
    
    return ScanResult(
        id="test_result_123",
        config=config,
        status=status,
        videos=videos,
        profiles=[],
        errors=[],
        started_at=datetime.now(),
        completed_at=datetime.now(),
        total_videos=total_videos,
        total_errors=total_errors,
        average_risk_score=0.3,
    )


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture
def mock_video():
    """Fixture providing a mock VideoRecord."""
    return create_mock_video_record()


@pytest.fixture
def mock_profile():
    """Fixture providing a mock UserProfile."""
    return create_mock_profile()


@pytest.fixture
def mock_comment():
    """Fixture providing a mock Comment."""
    return create_mock_comment()


@pytest.fixture
def mock_config():
    """Fixture providing a mock ScanConfig."""
    return create_mock_scan_config()


@pytest.fixture
def mock_scan_result():
    """Fixture providing a mock ScanResult."""
    return create_mock_scan_result()


@pytest.fixture
def sample_videos():
    """Fixture providing a list of sample VideoRecords."""
    return [
        create_mock_video_record(video_id=f"video_{i}", likes=i * 100)
        for i in range(1, 11)
    ]


@pytest.fixture
def sample_comments():
    """Fixture providing a list of sample Comments."""
    return [
        create_mock_comment(comment_id=f"comment_{i}", text=f"Comment {i}")
        for i in range(1, 6)
    ]


@pytest.fixture
def mock_page():
    """Fixture providing a mock Playwright Page."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.locator = MagicMock()
    page.evaluate = AsyncMock()
    page.keyboard = MagicMock()
    page.mouse = MagicMock()
    page.url = "https://www.tiktok.com/"
    return page


@pytest.fixture
def mock_browser_context():
    """Fixture providing a mock Playwright BrowserContext."""
    context = MagicMock()
    context.cookies = AsyncMock(return_value=[])
    context.set_default_timeout = MagicMock()
    context.new_page = MagicMock()
    return context


@pytest.fixture
def mock_browser():
    """Fixture providing a mock Playwright Browser."""
    browser = MagicMock()
    browser.close = AsyncMock()
    browser.new_context = MagicMock()
    return browser


@pytest.fixture
def mock_antidetect():
    """Fixture providing a mock AntiDetect instance."""
    antidetect = MagicMock()
    antidetect.get_next_proxy = MagicMock(return_value=None)
    antidetect.get_context_options = MagicMock(return_value={})
    antidetect.apply_fingerprint = MagicMock()
    antidetect.apply_fingerprint_async = AsyncMock()
    antidetect.apply_session = MagicMock()
    antidetect.apply_session_async = AsyncMock()
    antidetect.save_session = MagicMock()
    antidetect.save_session_async = AsyncMock()
    antidetect.rotate_identity = MagicMock()
    antidetect.rotate_identity_async = AsyncMock()
    antidetect.human_delay = MagicMock()
    antidetect.human_delay_async = AsyncMock()
    antidetect.micro_delay = MagicMock()
    antidetect.micro_delay_async = AsyncMock()
    antidetect.click_human = MagicMock()
    antidetect.click_human_async = AsyncMock()
    antidetect.scroll_naturally = MagicMock()
    antidetect.scroll_naturally_async = AsyncMock()
    antidetect.track_action = MagicMock()
    antidetect.track_action_async = AsyncMock()
    return antidetect


@pytest.fixture
def mock_risk_analyzer():
    """Fixture providing a mock RiskAnalyzer instance."""
    analyzer = MagicMock()
    analyzer.analyze_text = MagicMock(return_value=MagicMock(
        overall_risk=0.3,
        risk_level="LOW",
        categories=[],
        sentiment="neutral",
    ))
    return analyzer


@pytest.fixture
def mock_captcha_solver():
    """Fixture providing a mock CaptchaSolver instance."""
    solver = MagicMock()
    solver.handle_captcha = MagicMock(return_value=MagicMock(
        detected=False,
        solved=False,
        captcha_type=None,
    ))
    solver.handle_captcha_async = AsyncMock(return_value=MagicMock(
        detected=False,
        solved=False,
        captcha_type=None,
    ))
    return solver


# =============================================================================
# Context Managers for Patching
# =============================================================================

@pytest.fixture
def patch_playwright():
    """Context manager to patch Playwright imports."""
    with patch.dict('sys.modules', {
        'playwright': MagicMock(),
        'playwright.sync_api': MagicMock(),
        'playwright.async_api': MagicMock(),
    }):
        yield


@pytest.fixture
def patch_requests():
    """Context manager to patch requests library."""
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {})
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {})
        yield mock_get, mock_post


# =============================================================================
# Helper Functions
# =============================================================================

def assert_video_record_valid(video: VideoRecord):
    """Assert that a VideoRecord has valid structure."""
    assert video.id is not None
    assert video.url is not None
    assert isinstance(video.hashtags, list)
    assert isinstance(video.mentions, list)
    assert video.like_count >= 0
    assert video.comment_count >= 0
    assert video.share_count >= 0
    assert video.view_count >= 0
    assert isinstance(video.collected_at, datetime)


def assert_scan_result_valid(result: ScanResult):
    """Assert that a ScanResult has valid structure."""
    assert result.id is not None
    assert result.config is not None
    assert result.status in [ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.STOPPED]
    assert isinstance(result.videos, list)
    assert isinstance(result.errors, list)
    assert result.started_at is not None
    assert result.total_videos >= 0
    assert result.total_errors >= 0
