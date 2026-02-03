#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — TikTok Scraper Engine
Enhanced Playwright-based scraper with anti-detection integration.
"""
from __future__ import annotations

import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import requests

try:
    from playwright.sync_api import (
        sync_playwright,
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

from crot_dalam.core.antidetect import AntiDetect, create_antidetect
from crot_dalam.core.risk_analyzer import RiskAnalyzer, SentimentAnalyzer
from crot_dalam.core.exporters import Exporter
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


class TikTokScraper:
    """
    Enhanced TikTok scraper with anti-detection and comprehensive data extraction.
    """
    
    def __init__(
        self,
        config: Optional[ScanConfig] = None,
        antidetect: Optional[AntiDetect] = None,
        risk_analyzer: Optional[RiskAnalyzer] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
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
        
        # Runtime state
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._playwright = None
        
        # Results
        self._collected: List[VideoRecord] = []
        self._profiles: List[UserProfile] = []
        self._errors: List[Dict[str, str]] = []
    
    # -------------------------------------------------------------------------
    # Browser Management
    # -------------------------------------------------------------------------
    
    def _launch_browser(self) -> None:
        """Launch browser with anti-detection settings."""
        self._playwright = sync_playwright().start()
        
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
        
        self._browser = self._playwright.chromium.launch(**launch_args)
        
        # Get fingerprint-based context options
        context_options = self.antidetect.get_context_options()
        context_options["locale"] = self.config.locale
        
        if self.config.user_agent:
            context_options["user_agent"] = self.config.user_agent
        
        self._context = self._browser.new_context(**context_options)
        self._context.set_default_timeout(20_000)
        
        # Apply fingerprint modifications
        if self.config.antidetect_enabled:
            self.antidetect.apply_fingerprint(self._context)
        
        # Try to load existing session
        session_id = f"tiktok_{self.config.locale}"
        self.antidetect.apply_session(self._context, session_id)
        
        self._page = self._context.new_page()
    
    def _close_browser(self) -> None:
        """Close browser and save session."""
        if self._context:
            try:
                # Save session for reuse
                cookies = self._context.cookies()
                session_id = f"tiktok_{self.config.locale}"
                self.antidetect.save_session(session_id, cookies)
            except Exception:
                pass
            
            self._context.close()
        
        if self._browser:
            self._browser.close()
        
        if self._playwright:
            self._playwright.stop()
    
    # -------------------------------------------------------------------------
    # Cookie & Login Handling
    # -------------------------------------------------------------------------
    
    def _accept_cookies(self, page: Page) -> None:
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
                if btn and btn.count() > 0:
                    if self.config.antidetect_enabled:
                        # Human-like click
                        box = btn.first.bounding_box()
                        if box:
                            self.antidetect.click_human(
                                page,
                                box["x"] + box["width"] / 2,
                                box["y"] + box["height"] / 2,
                            )
                    else:
                        btn.first.click(timeout=2000)
                    self.antidetect.human_delay(0.5, 0.2)
                    break
            except Exception:
                pass
    
    def _close_popups(self, page: Page) -> None:
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
                if btn and btn.count() > 0:
                    btn.first.click(timeout=1000)
                    self.antidetect.micro_delay()
            except Exception:
                pass
    
    # -------------------------------------------------------------------------
    # Text Extraction Helpers
    # -------------------------------------------------------------------------
    
    def _text_or_none(self, locator) -> Optional[str]:
        """Safely extract text from a locator."""
        try:
            if locator and locator.count() > 0:
                return locator.first.inner_text().strip()
        except Exception:
            pass
        return None
    
    def _attr_or_none(self, locator, attr: str) -> Optional[str]:
        """Safely extract attribute from a locator."""
        try:
            if locator and locator.count() > 0:
                return locator.first.get_attribute(attr)
        except Exception:
            pass
        return None
    
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
    
    # -------------------------------------------------------------------------
    # Search & Collection
    # -------------------------------------------------------------------------
    
    def _scroll_and_collect(
        self, 
        page: Page, 
        limit: int,
        per_scroll_wait: float = 1.2,
    ) -> List[str]:
        """Scroll search results and collect video URLs."""
        seen: Dict[str, None] = {}
        last_height = 0
        stale_count = 0
        
        while len(seen) < limit and stale_count < 5:
            # Collect video links
            try:
                anchors = page.locator('a[href*="/video/"]').evaluate_all(
                    "elements => elements.map(e => e.href)"
                )
            except Exception:
                anchors = []
            
            for href in anchors or []:
                if "/video/" in href and re.search(_VIDEO_URL_RE, href):
                    seen[href] = None
                    if len(seen) >= limit:
                        break
            
            # Natural scrolling
            if self.config.antidetect_enabled:
                self.antidetect.scroll_naturally(page, 800)
                self.antidetect.human_delay(per_scroll_wait, 0.3)
            else:
                page.mouse.wheel(0, 2000)
                time.sleep(per_scroll_wait)
            
            # Check for scroll stagnation
            try:
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    stale_count += 1
                else:
                    stale_count = 0
                last_height = new_height
            except Exception:
                stale_count += 1
            
            # Track action for anti-detection
            self.antidetect.track_action()
        
        return list(seen.keys())
    
    def search_videos(self, query: str, limit: int) -> List[str]:
        """Search TikTok and collect video URLs."""
        encoded_query = requests.utils.quote(query)
        url = f"https://www.tiktok.com/search?q={encoded_query}"
        
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            self.antidetect.human_delay(1.0, 0.3)
            
            self._accept_cookies(self._page)
            self._close_popups(self._page)
            
            # Wait for content to load
            self.antidetect.human_delay(1.5, 0.5)
            
            urls = self._scroll_and_collect(self._page, limit)
            rprint(f"[cyan]Collected[/cyan] {len(urls)} video URLs for query: [bold]{query}[/bold]")
            return urls
            
        except PWTimeout as e:
            rprint(f"[yellow]Timeout during search: {e}[/yellow]")
            return []
        except Exception as e:
            rprint(f"[red]Error during search: {e}[/red]")
            self._errors.append({"type": "search", "query": query, "error": str(e)})
            return []
    
    # -------------------------------------------------------------------------
    # Video Metadata Extraction
    # -------------------------------------------------------------------------
    
    def _expand_comments(self, page: Page, desired: int) -> None:
        """Expand comment section."""
        if desired <= 0:
            return
        
        try:
            for _ in range(5):
                more = page.locator('button:has-text("View more")')
                if more and more.count() > 0:
                    more.first.click()
                    self.antidetect.human_delay(0.6, 0.2)
                else:
                    break
        except Exception:
            pass
    
    def _collect_comments(self, page: Page, limit: int) -> List[Comment]:
        """Collect comments from video page."""
        if limit <= 0:
            return []
        
        comments: List[Comment] = []
        try:
            cards = page.locator('[data-e2e="comment-list"] [data-e2e="comment-item"]')
            n = min(cards.count(), limit)
            
            for i in range(n):
                card = cards.nth(i)
                user = self._text_or_none(card.locator('[data-e2e="comment-username"]'))
                text = self._text_or_none(card.locator('[data-e2e="comment-content"]'))
                
                if text:
                    # Analyze sentiment
                    sentiment_result = SentimentAnalyzer.analyze(text)
                    
                    comments.append(Comment(
                        username=user or "",
                        text=text,
                        sentiment=sentiment_result["sentiment"],
                        sentiment_score=sentiment_result["score"],
                        mentions=self._extract_mentions(text),
                    ))
        except Exception:
            pass
        
        return comments
    
    def extract_video_metadata(self, url: str) -> Optional[VideoRecord]:
        """Extract complete metadata from a video page."""
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            self.antidetect.human_delay(0.8, 0.3)
            
            self._accept_cookies(self._page)
            self._close_popups(self._page)
            
            # Extract description with multiple selector attempts
            desc = (
                self._text_or_none(self._page.locator('[data-e2e="video-desc"]'))
                or self._text_or_none(self._page.locator('h1[data-e2e="video-desc"]'))
                or self._text_or_none(self._page.locator('div[data-e2e="browse-video-desc"]'))
            )
            
            # Extract author
            author_name = (
                self._text_or_none(self._page.locator('[data-e2e="browse-author-name"]'))
                or self._text_or_none(self._page.locator('[data-e2e="user-card-username"]'))
            )
            
            # Extract metrics
            like_count = self._to_int_safe(
                self._text_or_none(self._page.locator('[data-e2e="like-count"]'))
            )
            comment_count = self._to_int_safe(
                self._text_or_none(self._page.locator('[data-e2e="comment-count"]'))
            )
            share_count = self._to_int_safe(
                self._text_or_none(self._page.locator('[data-e2e="share-count"]'))
            )
            view_count = self._to_int_safe(
                self._text_or_none(self._page.locator('[data-e2e="view-count"]'))
            )
            
            # Extract date
            upload_date = self._attr_or_none(self._page.locator("time"), "datetime")
            
            # Extract hashtags, mentions, URLs
            hashtags = self._extract_hashtags(desc)
            mentions = self._extract_mentions(desc)
            extracted_urls = self._extract_urls(desc)
            
            # Collect comments
            self._expand_comments(self._page, self.config.comments_limit)
            comments = self._collect_comments(self._page, self.config.comments_limit)
            
            # Parse URL
            username, video_id = self._parse_video_id_from_url(url)
            
            # Risk analysis
            risk_result = self.risk_analyzer.analyze(desc)
            
            # Calculate comment sentiment summary
            sentiment_summary = None
            if comments:
                pos = sum(1 for c in comments if c.sentiment == "positive")
                neg = sum(1 for c in comments if c.sentiment == "negative")
                sentiment_summary = {
                    "total": len(comments),
                    "positive": pos,
                    "negative": neg,
                    "neutral": len(comments) - pos - neg,
                }
            
            return VideoRecord(
                video_id=video_id or "",
                url=url,
                username=username,
                author_name=author_name,
                description=desc,
                upload_date=upload_date,
                like_count=like_count,
                comment_count=comment_count,
                share_count=share_count,
                view_count=view_count,
                hashtags=sorted(set(hashtags)),
                comments=[c.to_dict() for c in comments],
                extracted_urls=extracted_urls,
                mentions=mentions,
                risk_score=risk_result.score,
                risk_level=risk_result.level.name,
                risk_matches=[m.term for m in risk_result.matches],
                risk_categories=risk_result.categories,
                sentiment_summary=sentiment_summary,
            )
            
        except PWTimeout as e:
            rprint(f"[yellow]Timeout on {url}: {e}[/yellow]")
        except Exception as e:
            rprint(f"[red]Error extracting {url}: {e}[/red]")
            self._errors.append({"type": "extract", "url": url, "error": str(e)})
        
        return None
    
    # -------------------------------------------------------------------------
    # User Profile Extraction
    # -------------------------------------------------------------------------
    
    def extract_user_profile(self, username: str) -> Optional[UserProfile]:
        """Extract user profile data."""
        url = f"https://www.tiktok.com/@{username}"
        
        try:
            self._page.goto(url, wait_until="domcontentloaded")
            self.antidetect.human_delay(1.0, 0.3)
            
            self._accept_cookies(self._page)
            
            display_name = self._text_or_none(
                self._page.locator('[data-e2e="user-title"]')
            )
            bio = self._text_or_none(
                self._page.locator('[data-e2e="user-bio"]')
            )
            
            follower_count = self._to_int_safe(
                self._text_or_none(self._page.locator('[data-e2e="followers-count"]'))
            )
            following_count = self._to_int_safe(
                self._text_or_none(self._page.locator('[data-e2e="following-count"]'))
            )
            like_count = self._to_int_safe(
                self._text_or_none(self._page.locator('[data-e2e="likes-count"]'))
            )
            
            # Check verification
            verified = self._page.locator('[data-e2e="verify-badge"]').count() > 0
            
            # Risk analysis on bio
            risk_result = self.risk_analyzer.analyze(bio)
            
            return UserProfile(
                username=username,
                display_name=display_name,
                bio=bio,
                follower_count=follower_count,
                following_count=following_count,
                like_count=like_count,
                verified=verified,
                risk_score=risk_result.score,
                risk_matches=[m.term for m in risk_result.matches],
            )
            
        except Exception as e:
            rprint(f"[red]Error extracting profile @{username}: {e}[/red]")
            self._errors.append({"type": "profile", "username": username, "error": str(e)})
        
        return None
    
    # -------------------------------------------------------------------------
    # Evidence Collection
    # -------------------------------------------------------------------------
    
    def _take_screenshot(self, record: VideoRecord, base_path: Path) -> Optional[str]:
        """Take screenshot of current page."""
        try:
            shot_dir = base_path.parent / "screenshots"
            shot_dir.mkdir(parents=True, exist_ok=True)
            png_path = shot_dir / f"{record.video_id or 'unknown'}.png"
            self._page.screenshot(path=str(png_path), full_page=True)
            return str(png_path)
        except Exception as e:
            rprint(f"[yellow]Screenshot failed: {e}[/yellow]")
            return None
    
    def _download_video(self, url: str, base_path: Path) -> Optional[str]:
        """Download video using yt-dlp."""
        try:
            import subprocess
            dl_dir = base_path.parent / "videos"
            dl_dir.mkdir(parents=True, exist_ok=True)
            
            out_tpl = str(dl_dir / "%(id)s.%(ext)s")
            result = subprocess.run(
                ["yt-dlp", "--no-warnings", "--no-playlist", "-o", out_tpl, url],
                capture_output=True,
                text=True,
            )
            
            if result.returncode == 0:
                rprint(f"[green]Downloaded:[/green] {url}")
                return str(dl_dir)
            else:
                rprint(f"[yellow]yt-dlp failed: {result.stderr}[/yellow]")
        except Exception as e:
            rprint(f"[yellow]Download error: {e}[/yellow]")
        
        return None
    
    def _archive_url(self, url: str) -> Optional[str]:
        """Submit URL to Archive.today."""
        try:
            resp = requests.post(
                "https://archive.today/submit/",
                data={"url": url},
                timeout=20,
                headers={"User-Agent": self.antidetect.get_fingerprint().user_agent},
            )
            
            loc = resp.headers.get("Content-Location") or resp.headers.get("Location")
            if loc:
                return loc
            
            m = re.search(r"https?://archive\.(?:today|is|ph)/[\w/\-]+", resp.text)
            return m.group(0) if m else None
        except Exception:
            return None
    
    # -------------------------------------------------------------------------
    # Main Scan Methods
    # -------------------------------------------------------------------------
    
    def run_scan(self) -> ScanResult:
        """Run complete scan based on configuration."""
        scan_id = str(uuid.uuid4())[:8]
        started_at = datetime.now().isoformat()
        
        result = ScanResult(
            scan_id=scan_id,
            status=ScanStatus.running,
            config=self.config,
            started_at=started_at,
        )
        
        try:
            self._launch_browser()
            
            all_urls: List[str] = []
            searched_keywords: List[str] = []
            
            # Search phase
            for keyword in self.config.keywords:
                searched_keywords.append(keyword)
                urls = self.search_videos(keyword, self.config.limit)
                all_urls.extend(urls)
                
                # Polite pause between searches
                if self.config.antidetect_enabled:
                    self.antidetect.human_delay(2.0, 0.5)
            
            # Hashtag pivoting
            if self.config.pivot_hashtags > 0:
                rprint("[bold cyan]Pivoting by top hashtags…[/bold cyan]")
                hashtag_counts: Dict[str, int] = {}
                
                # Quick scan for hashtags
                for u in all_urls[:min(len(all_urls), 20)]:
                    try:
                        self._page.goto(u, wait_until="domcontentloaded")
                        desc = self._text_or_none(self._page.locator('[data-e2e="video-desc"]'))
                        for tag in self._extract_hashtags(desc):
                            hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1
                    except Exception:
                        continue
                    self.antidetect.human_delay(0.5, 0.2)
                
                # Search top hashtags
                top_tags = sorted(hashtag_counts.items(), key=lambda x: -x[1])[:self.config.pivot_hashtags]
                for tag, _ in top_tags:
                    q = f"#{tag}"
                    searched_keywords.append(q)
                    urls = self.search_videos(q, max(10, self.config.limit // 2))
                    all_urls.extend(urls)
            
            # Deduplicate URLs
            seen = set()
            final_urls: List[str] = []
            for u in all_urls:
                if u not in seen:
                    seen.add(u)
                    final_urls.append(u)
            
            rprint(f"[bold]Total unique URLs to process:[/bold] {len(final_urls)}")
            
            # Process each video
            base_path = Path(self.config.output_base)
            base_path.parent.mkdir(parents=True, exist_ok=True)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
            ) as progress:
                task = progress.add_task("Processing videos...", total=len(final_urls))
                
                for idx, url in enumerate(final_urls, 1):
                    record = self.extract_video_metadata(url)
                    
                    if record:
                        record.keyword_searched = ", ".join(searched_keywords)
                        
                        # Evidence collection
                        if self.config.screenshot:
                            record.screenshot_path = self._take_screenshot(record, base_path)
                        
                        if self.config.download:
                            record.video_path = self._download_video(url, base_path)
                        
                        if self.config.web_archive:
                            archive_result = self._archive_url(url)
                            if archive_result:
                                record.archive_url = archive_result
                                rprint(f"[green]Archived:[/green] {archive_result}")
                        
                        self._collected.append(record)
                    
                    progress.update(task, advance=1)
                    
                    # Callback for GUI progress
                    if self.progress_callback:
                        self.progress_callback("processing", idx, len(final_urls))
                    
                    # Polite delay
                    if self.config.antidetect_enabled:
                        self.antidetect.human_delay(0.5, 0.2)
            
            # Export results
            exporter = Exporter(self.config.output_base)
            paths = exporter.export_all(self._collected, searched_keywords, self.config.mode.value)
            
            result.videos = self._collected
            result.output_jsonl = str(paths["jsonl"])
            result.output_csv = str(paths["csv"])
            result.output_html = str(paths["html"])
            result.status = ScanStatus.completed
            result.calculate_stats()
            
        except Exception as e:
            result.status = ScanStatus.failed
            self._errors.append({"type": "scan", "error": str(e)})
            rprint(f"[red]Scan failed: {e}[/red]")
            
        finally:
            self._close_browser()
            result.completed_at = datetime.now().isoformat()
            result.errors = self._errors
            
            if result.started_at and result.completed_at:
                start = datetime.fromisoformat(result.started_at)
                end = datetime.fromisoformat(result.completed_at)
                result.duration_seconds = (end - start).total_seconds()
        
        return result
    
    def get_collected_videos(self) -> List[VideoRecord]:
        """Get collected videos."""
        return self._collected
    
    def get_errors(self) -> List[Dict[str, str]]:
        """Get error log."""
        return self._errors


# -------------------------------------------------------------------------
# Network Graph Builder
# -------------------------------------------------------------------------

class NetworkBuilder:
    """Build relationship networks from scan results."""
    
    @staticmethod
    def build_from_videos(videos: List[VideoRecord]) -> NetworkGraph:
        """Build network graph from video records."""
        graph = NetworkGraph()
        
        for video in videos:
            # Add user node
            if video.username:
                graph.add_node(
                    f"user_{video.username}",
                    "user",
                    f"@{video.username}",
                    video_count=1,
                )
            
            # Add hashtag nodes and edges
            for tag in video.hashtags:
                graph.add_node(f"hashtag_{tag}", "hashtag", f"#{tag}")
                if video.username:
                    graph.add_edge(f"user_{video.username}", f"hashtag_{tag}", "uses_hashtag")
            
            # Add mention edges
            for mention in video.mentions:
                graph.add_node(f"user_{mention}", "user", f"@{mention}")
                if video.username:
                    graph.add_edge(f"user_{video.username}", f"user_{mention}", "mentions")
        
        return graph
