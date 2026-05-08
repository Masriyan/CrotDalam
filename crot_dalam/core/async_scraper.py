#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM - Enhanced Async Scraper Engine
Modern asyncio-based scraper with improved performance and resilience.
"""
from __future__ import annotations

import asyncio
import re
import time
import uuid
import functools
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

try:
    from playwright.async_api import (
        async_playwright,
        Page,
        BrowserContext,
        Browser,
        TimeoutError as PWTimeout,
        Error as PlaywrightError,
    )
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = Any
    BrowserContext = Any
    Browser = Any

from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# Import from crot_dalam modules
from crot_dalam.core.antidetect import AntiDetect, create_antidetect
from crot_dalam.core.risk_analyzer import RiskAnalyzer, SentimentAnalyzer
from crot_dalam.core.captcha_solver import CaptchaSolver, create_captcha_solver, CaptchaType
from crot_dalam.models.data import (
    VideoRecord,
    UserProfile,
    Comment,
    ScanConfig,
    ScanResult,
    ScanStatus,
    NetworkGraph,
)


# Regex patterns
_URL_RE = re.compile(r"https?://[^\s\"]+")
_HASHTAG_RE = re.compile(r"(?<!&)#(\w{2,64})", re.UNICODE)
_MENTION_RE = re.compile(r"@(\w{2,32})", re.UNICODE)
_VIDEO_URL_RE = re.compile(r"/(@[^/]+)/video/(\d+)")

# Counter suffix parsing
_KSUFFIX = {"k": 1_000, "K": 1_000, "m": 1_000_000, "M": 1_000_000, "b": 1_000_000_000, "B": 1_000_000_000}


@dataclass
class ScrapingStats:
    """Statistics for scraping session."""
    total_videos: int = 0
    total_profiles: int = 0
    total_comments: int = 0
    errors: int = 0
    retries: int = 0
    captchas_solved: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    
    @property
    def elapsed_seconds(self) -> float:
        return (datetime.now() - self.start_time).total_seconds()
    
    @property
    def videos_per_minute(self) -> float:
        if self.elapsed_seconds == 0:
            return 0.0
        return (self.total_videos / self.elapsed_seconds) * 60


class AsyncTikTokScraper:
    """
    Enhanced async TikTok scraper with improved performance,
    better error handling, and streaming capabilities.
    """
    
    def __init__(
        self,
        config: Optional[ScanConfig] = None,
        antidetect: Optional[AntiDetect] = None,
        risk_analyzer: Optional[RiskAnalyzer] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        stream_callback: Optional[Callable[[VideoRecord], None]] = None,
    ):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is required. Install with: pip install playwright && playwright install chromium"
            )
        
        self.config = config or ScanConfig(keywords=[])
        self.antidetect = antidetect or create_antidetect(
            aggressive=self.config.antidetect_aggressive,
            proxy_list=self.config.proxy_list,
        )
        self.risk_analyzer = risk_analyzer or RiskAnalyzer()
        self.progress_callback = progress_callback
        self.stream_callback = stream_callback
        
        # CAPTCHA solver integration
        self.captcha_solver = CaptchaSolver(antidetect=self.antidetect)
        
        # Runtime state
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._playwright = None
        self._stop_requested = False
        
        # Circuit breaker state
        self._consecutive_failures = 0
        self._max_consecutive_failures = 5
        
        # Statistics
        self.stats = ScrapingStats()
        
        # Results storage (for non-streaming mode)
        self._collected: List[VideoRecord] = []
        self._profiles: List[UserProfile] = []
        self._errors: List[Dict[str, str]] = []
    
    async def _retry_with_backoff(
        self,
        func: Callable,
        *args,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 15.0,
        exceptions: tuple = (Exception,),
        **kwargs
    ) -> Any:
        """Retry function with exponential backoff."""
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                self.stats.retries += 1
                if attempt == max_retries:
                    raise
                delay = min(base_delay * (2 ** attempt), max_delay)
                import random
                delay += delay * (0.5 * (2 * random.random() - 1))  # jitter
                rprint(f"[yellow]Retry {attempt + 1}/{max_retries} after {delay:.1f}s: {e}[/yellow]")
                await asyncio.sleep(delay)
        raise last_exception
    
    async def _launch_browser(self) -> None:
        """Launch browser with anti-detection settings."""
        self._playwright = await async_playwright().start()
        
        launch_args = {
            "headless": self.config.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        }
        
        # Add proxy if available
        proxy_url = self.antidetect.get_next_proxy()
        if proxy_url:
            launch_args["proxy"] = {"server": proxy_url}
        
        self._browser = await self._playwright.chromium.launch(**launch_args)
        
        # Get fingerprint-based context options
        context_options = self.antidetect.get_context_options()
        context_options["locale"] = self.config.locale
        
        if self.config.user_agent:
            context_options["user_agent"] = self.config.user_agent
        
        self._context = await self._browser.new_context(**context_options)
        self._context.set_default_timeout(20_000)
        
        # Apply fingerprint modifications
        if self.config.antidetect_enabled:
            await self.antidetect.apply_fingerprint_async(self._context)
        
        # Try to load existing session
        session_id = f"tiktok_{self.config.locale}"
        await self.antidetect.apply_session_async(self._context, session_id)
        
        self._page = await self._context.new_page()
    
    async def _navigate_with_captcha(
        self, 
        page: Page, 
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 30000,
    ) -> bool:
        """Navigate to URL with CAPTCHA detection and retry."""
        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout)
            await self.antidetect.human_delay_async(0.5, 0.2)
            
            # Check for CAPTCHA
            captcha_result = await self.captcha_solver.handle_captcha_async(page)
            if captcha_result.detected and not captcha_result.solved:
                # CAPTCHA detected but not solved — rotate identity
                rprint("[yellow]Rotating identity after CAPTCHA detection...[/yellow]")
                await self.antidetect.rotate_identity_async()
                await asyncio.sleep(2.0)
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                await self.captcha_solver.handle_captcha_async(page)
            
            self._handle_circuit_breaker(True)
            return True
        except Exception as e:
            self._handle_circuit_breaker(False)
            raise
    
    def _handle_circuit_breaker(self, success: bool) -> None:
        """Track consecutive failures and rotate identity if threshold reached."""
        if success:
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._max_consecutive_failures:
                rprint("[bold yellow]⚡ Circuit breaker triggered — rotating identity[/bold yellow]")
                self.antidetect.rotate_identity()
                self._consecutive_failures = 0
                time.sleep(3.0)
    
    async def _close_browser(self) -> None:
        """Close browser and save session."""
        if self._context:
            try:
                # Save session for reuse
                cookies = await self._context.cookies()
                session_id = f"tiktok_{self.config.locale}"
                await self.antidetect.save_session_async(session_id, cookies)
            except Exception:
                pass
            
            await self._context.close()
        
        if self._browser:
            await self._browser.close()
        
        if self._playwright:
            await self._playwright.stop()
    
    async def _accept_cookies(self, page: Page) -> None:
        """Accept cookie banners."""
        selectors = [
            'button:has-text("Accept all")',
            'button:has-text("Accept All")',
            'button:has-text("Terima semua")',
            'button:has-text("I agree")',
            'button:has-text("Allow all")',
            'button:has-text("AGREE")',
            'button[data-e2e="gdpr-accept-button"]',
        ]
        
        for sel in selectors:
            try:
                btn = page.locator(sel)
                count = await btn.count()
                if count > 0:
                    if self.config.antidetect_enabled:
                        box = await btn.first.bounding_box()
                        if box:
                            await self.antidetect.click_human_async(
                                page,
                                box["x"] + box["width"] / 2,
                                box["y"] + box["height"] / 2,
                            )
                    else:
                        await btn.first.click(timeout=2000)
                    await self.antidetect.human_delay_async(0.5, 0.2)
                    break
            except Exception:
                pass
    
    async def _close_popups(self, page: Page) -> None:
        """Close any popups or modals."""
        popup_selectors = [
            '[data-e2e="modal-close-inner-button"]',
            'button[aria-label="Close"]',
            'button:has-text("Not now")',
            'button:has-text("Maybe later")',
        ]
        
        for sel in popup_selectors:
            try:
                btn = page.locator(sel)
                count = await btn.count()
                if count > 0:
                    await btn.first.click(timeout=1000)
                    await self.antidetect.micro_delay_async()
            except Exception:
                pass
    
    def _text_or_none(self, text: Optional[str]) -> Optional[str]:
        """Safely extract text."""
        if not text:
            return None
        return text.strip()
    
    def _to_int_safe(self, s: Optional[str]) -> Optional[int]:
        """Parse counter string to integer (handles K, M, B suffixes)."""
        if not s:
            return None
        s = s.strip()
        if not s:
            return None
        
        try:
            m = re.match(r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+(?:\.[0-9]+)?)([kKmMbB]?)", s)
            if not m:
                return int(re.sub(r"[^0-9]", "", s) or 0)
            
            num, suf = m.groups()
            num = num.replace(",", "")
            val = float(num)
            if suf:
                val *= _KSUFFIX.get(suf, 1)
            return int(val)
        except Exception:
            return None
    
    def _extract_hashtags(self, text: Optional[str]) -> List[str]:
        """Extract hashtags from text."""
        if not text:
            return []
        return list(dict.fromkeys(m.group(1) for m in _HASHTAG_RE.finditer(text)))
    
    def _extract_mentions(self, text: Optional[str]) -> List[str]:
        """Extract @mentions from text."""
        if not text:
            return []
        return list(dict.fromkeys(m.group(1) for m in _MENTION_RE.finditer(text)))
    
    def _extract_urls(self, text: Optional[str]) -> List[str]:
        """Extract URLs from text."""
        if not text:
            return []
        return list(dict.fromkeys(re.findall(_URL_RE, text)))
    
    def _parse_video_id_from_url(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse username and video ID from URL."""
        try:
            m = re.search(_VIDEO_URL_RE, url)
            if not m:
                return None, None
            username = m.group(1).lstrip("@") if m.group(1) else None
            vid = m.group(2)
            return username, vid
        except Exception:
            return None, None
    
    async def _scroll_and_collect(
        self, 
        page: Page, 
        limit: int,
        per_scroll_wait: float = 1.2,
    ) -> List[str]:
        """Scroll search results and collect video URLs."""
        seen: Dict[str, None] = {}
        last_height = 0
        stale_count = 0
        
        # Multiple selector strategies for collecting video links
        video_selectors = [
            'a[href*="/video/"]',
            'div[data-e2e="search_top-item"] a',
            'div[class*="DivItemContainer"] a',
        ]
        
        while len(seen) < limit and stale_count < 7:
            # Collect video links with multiple selector fallback
            anchors = []
            for sel in video_selectors:
                try:
                    found = await page.locator(sel).evaluate_all(
                        "elements => elements.map(e => e.href)"
                    )
                    anchors.extend(found or [])
                except Exception:
                    continue
            
            for href in anchors:
                if "/video/" in href and re.search(_VIDEO_URL_RE, href):
                    seen[href] = None
                    if len(seen) >= limit:
                        break
            
            # Natural scrolling
            if self.config.antidetect_enabled:
                await self.antidetect.scroll_naturally_async(page, 800)
                await self.antidetect.human_delay_async(per_scroll_wait, 0.3)
            else:
                await page.mouse.wheel(0, 2000)
                await asyncio.sleep(per_scroll_wait)
            
            # Check for scroll stagnation
            try:
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    stale_count += 1
                    
                    # Enhanced stagnation recovery
                    if stale_count == 3:
                        try:
                            await page.keyboard.press("End")
                            await asyncio.sleep(1.0)
                        except Exception:
                            pass
                    elif stale_count == 5:
                        try:
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            await asyncio.sleep(1.5)
                        except Exception:
                            pass
                else:
                    stale_count = 0
                last_height = new_height
            except Exception:
                stale_count += 1
            
            # Check for CAPTCHA during scrolling
            if stale_count > 0 and stale_count % 2 == 0:
                await self.captcha_solver.handle_captcha_async(page)
            
            # Track action for anti-detection
            await self.antidetect.track_action_async()
        
        return list(seen.keys())[:limit]
    
    async def _extract_video_data(self, page: Page, video_url: str) -> Optional[VideoRecord]:
        """Extract comprehensive video data."""
        try:
            await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1.0)
            
            # Extract video information
            description_locator = page.locator('[data-e2e="video-desc"]')
            description = await description_locator.inner_text() if await description_locator.count() > 0 else ""
            
            # Extract stats
            like_locator = page.locator('[data-e2e="like-count"]')
            comment_locator = page.locator('[data-e2e="comment-count"]')
            share_locator = page.locator('[data-e2e="share-count"]')
            view_locator = page.locator('[data-e2e="views-count"]')
            
            likes = self._to_int_safe(await like_locator.inner_text() if await like_locator.count() > 0 else None)
            comments = self._to_int_safe(await comment_locator.inner_text() if await comment_locator.count() > 0 else None)
            shares = self._to_int_safe(await share_locator.inner_text() if await share_locator.count() > 0 else None)
            views = self._to_int_safe(await view_locator.inner_text() if await view_locator.count() > 0 else None)
            
            # Extract author info
            author_locator = page.locator('[data-e2e="video-author"]')
            author_name = await author_locator.inner_text() if await author_locator.count() > 0 else ""
            
            # Parse video ID
            username, video_id = self._parse_video_id_from_url(video_url)
            
            # Create video record
            video_record = VideoRecord(
                id=video_id or str(uuid.uuid4()),
                url=video_url,
                description=description or "",
                hashtags=self._extract_hashtags(description),
                mentions=self._extract_mentions(description),
                urls=self._extract_urls(description),
                author_username=username or author_name,
                author_display_name=author_name,
                like_count=likes or 0,
                comment_count=comments or 0,
                share_count=shares or 0,
                view_count=views or 0,
                collected_at=datetime.now(),
                locale=self.config.locale,
            )
            
            # Analyze risk
            risk_result = self.risk_analyzer.analyze_text(description or "")
            video_record.risk_score = risk_result.overall_risk
            video_record.risk_level = risk_result.risk_level
            video_record.risk_categories = risk_result.categories
            
            self.stats.total_videos += 1
            
            # Stream callback if provided
            if self.stream_callback:
                self.stream_callback(video_record)
            
            return video_record
            
        except Exception as e:
            self.stats.errors += 1
            self._errors.append({
                "type": "video_extraction",
                "url": video_url,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
            return None
    
    async def _collect_comments(self, page: Page, video_url: str, limit: int = 50) -> List[Comment]:
        """Collect comments from a video."""
        comments = []
        try:
            # Navigate to video if not already there
            if video_url not in page.url:
                await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1.0)
            
            # Click to show comments if needed
            comment_section = page.locator('[data-e2e="comment-list"]')
            if await comment_section.count() == 0:
                comment_btn = page.locator('[data-e2e="comment-count"]')
                if await comment_btn.count() > 0:
                    await comment_btn.first.click()
                    await asyncio.sleep(1.5)
            
            # Scroll to load comments
            for _ in range(5):
                await page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(0.5)
            
            # Extract comments
            comment_items = page.locator('[data-e2e="comment-item"]')
            count = await comment_items.count()
            
            for i in range(min(count, limit)):
                try:
                    item = comment_items.nth(i)
                    text_elem = item.locator('[data-e2e="comment-text"]')
                    author_elem = item.locator('[data-e2e="comment-author"]')
                    
                    text = await text_elem.inner_text() if await text_elem.count() > 0 else ""
                    author = await author_elem.inner_text() if await author_elem.count() > 0 else ""
                    
                    comment = Comment(
                        id=str(uuid.uuid4()),
                        text=text,
                        author=author,
                        collected_at=datetime.now(),
                    )
                    
                    # Analyze comment risk
                    risk_result = self.risk_analyzer.analyze_text(text)
                    comment.risk_score = risk_result.overall_risk
                    comment.risk_level = risk_result.risk_level
                    
                    comments.append(comment)
                    self.stats.total_comments += 1
                except Exception:
                    continue
            
        except Exception as e:
            self._errors.append({
                "type": "comment_collection",
                "url": video_url,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
        
        return comments
    
    async def run_scan(self) -> ScanResult:
        """Execute complete scan with enhanced error handling and streaming."""
        start_time = datetime.now()
        
        try:
            # Launch browser
            await self._launch_browser()
            
            if not self._page:
                raise RuntimeError("Failed to initialize page")
            
            # Accept cookies and close popups
            await self._accept_cookies(self._page)
            await self._close_popups(self._page)
            
            # Process each keyword
            all_videos: List[VideoRecord] = []
            
            for keyword in self.config.keywords:
                if self._stop_requested:
                    break
                
                rprint(f"\n[bold blue]🔍 Searching for: {keyword}[/bold blue]")
                
                # Build search URL
                search_url = f"https://www.tiktok.com/search?q={keyword.replace(' ', '%20')}&lang={self.config.locale}"
                
                # Navigate with CAPTCHA handling
                await self._retry_with_backoff(
                    self._navigate_with_captcha,
                    self._page,
                    search_url,
                    max_retries=3,
                )
                
                # Wait for content to load
                await asyncio.sleep(2.0)
                
                # Scroll and collect video URLs
                video_urls = await self._scroll_and_collect(
                    self._page,
                    limit=self.config.max_results,
                    per_scroll_wait=self.config.scroll_delay,
                )
                
                rprint(f"[green]✓ Found {len(video_urls)} videos[/green]")
                
                # Extract data from each video
                for idx, video_url in enumerate(video_urls, 1):
                    if self._stop_requested:
                        break
                    
                    if self.progress_callback:
                        self.progress_callback(keyword, idx, len(video_urls))
                    
                    # Extract video data with retry
                    video = await self._retry_with_backoff(
                        self._extract_video_data,
                        self._page,
                        video_url,
                        max_retries=2,
                        base_delay=0.5,
                    )
                    
                    if video:
                        all_videos.append(video)
                        
                        # Collect comments if enabled
                        if self.config.collect_comments and video.comment_count > 0:
                            comments = await self._collect_comments(
                                self._page,
                                video_url,
                                limit=min(50, video.comment_count),
                            )
                            video.comments = comments
                
                # Rotate identity between keywords
                if len(self.config.keywords) > 1:
                    await self.antidetect.rotate_identity_async()
                    await asyncio.sleep(2.0)
            
            # Compile results
            end_time = datetime.now()
            
            # Calculate aggregate statistics
            total_risk = sum(v.risk_score or 0 for v in all_videos)
            avg_risk = total_risk / len(all_videos) if all_videos else 0
            
            result = ScanResult(
                id=str(uuid.uuid4()),
                config=self.config,
                status=ScanStatus.COMPLETED if not self._stop_requested else ScanStatus.STOPPED,
                videos=all_videos,
                profiles=self._profiles,
                errors=self._errors,
                started_at=start_time,
                completed_at=end_time,
                total_videos=len(all_videos),
                total_errors=len(self._errors),
                average_risk_score=avg_risk,
            )
            
            rprint(f"\n[bold green]✅ Scan completed: {len(all_videos)} videos collected[/bold green]")
            rprint(f"[dim]Time elapsed: {(end_time - start_time).total_seconds():.1f}s[/dim]")
            rprint(f"[dim]Videos/minute: {self.stats.videos_per_minute:.1f}[/dim]")
            
            return result
            
        except Exception as e:
            rprint(f"[bold red]❌ Scan failed: {e}[/bold red]")
            self._errors.append({
                "type": "scan_failure",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
            
            return ScanResult(
                id=str(uuid.uuid4()),
                config=self.config,
                status=ScanStatus.FAILED,
                videos=[],
                profiles=[],
                errors=self._errors,
                started_at=start_time,
                completed_at=datetime.now(),
                total_videos=0,
                total_errors=len(self._errors),
            )
        
        finally:
            # Always close browser
            await self._close_browser()
    
    def request_stop(self) -> None:
        """Request graceful stop of scanning."""
        self._stop_requested = True
        rprint("[yellow]⏹️ Stop requested...[/yellow]")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current scraping statistics."""
        return {
            "total_videos": self.stats.total_videos,
            "total_profiles": self.stats.total_profiles,
            "total_comments": self.stats.total_comments,
            "errors": self.stats.errors,
            "retries": self.stats.retries,
            "captchas_solved": self.stats.captchas_solved,
            "elapsed_seconds": self.stats.elapsed_seconds,
            "videos_per_minute": self.stats.videos_per_minute,
        }


def create_async_scraper(
    config: Optional[ScanConfig] = None,
    **kwargs
) -> AsyncTikTokScraper:
    """Factory function to create async scraper instance."""
    return AsyncTikTokScraper(config=config, **kwargs)
