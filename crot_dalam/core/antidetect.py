#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Anti-Detection Module
Human-like behavior simulation to avoid TikTok bot detection.
"""
from __future__ import annotations

import math
import random
import time
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

try:
    from playwright.sync_api import Page, BrowserContext
except ImportError:
    Page = Any
    BrowserContext = Any


@dataclass
class ProxyConfig:
    """Proxy configuration with health tracking."""
    url: str
    failures: int = 0
    last_used: float = 0.0
    is_healthy: bool = True
    
    def mark_failure(self):
        self.failures += 1
        if self.failures >= 3:
            self.is_healthy = False
    
    def mark_success(self):
        self.failures = 0
        self.is_healthy = True
        self.last_used = time.time()


@dataclass 
class FingerprintProfile:
    """Browser fingerprint configuration."""
    viewport_width: int
    viewport_height: int
    timezone_id: str
    locale: str
    color_scheme: str
    user_agent: str
    webgl_vendor: str
    webgl_renderer: str
    platform: str
    
    @classmethod
    def random(cls) -> "FingerprintProfile":
        """Generate a random realistic fingerprint."""
        viewports = [
            (1920, 1080), (1366, 768), (1440, 900), (1536, 864),
            (1280, 720), (1600, 900), (2560, 1440), (1280, 800),
        ]
        timezones = [
            "Asia/Jakarta", "Asia/Singapore", "Asia/Bangkok", "Asia/Manila",
            "America/New_York", "America/Los_Angeles", "Europe/London",
            "Asia/Tokyo", "Asia/Seoul", "Australia/Sydney",
        ]
        locales = ["en-US", "en-GB", "id-ID", "th-TH", "vi-VN", "fil-PH", "ms-MY"]
        platforms = ["Win32", "MacIntel", "Linux x86_64"]
        webgl_configs = [
            ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Ti Direct3D11)"),
            ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11)"),
            ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 580 Series Direct3D11)"),
            ("Apple Inc.", "Apple M1 Pro"),
            ("Intel Inc.", "Intel Iris OpenGL Engine"),
        ]
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]
        
        vw, vh = random.choice(viewports)
        webgl = random.choice(webgl_configs)
        
        return cls(
            viewport_width=vw,
            viewport_height=vh,
            timezone_id=random.choice(timezones),
            locale=random.choice(locales),
            color_scheme=random.choice(["light", "dark"]),
            user_agent=random.choice(user_agents),
            webgl_vendor=webgl[0],
            webgl_renderer=webgl[1],
            platform=random.choice(platforms),
        )


class AntiDetect:
    """
    Anti-detection system for TikTok scraping.
    Implements human-like behavior simulation.
    """
    
    def __init__(
        self,
        min_delay: float = 0.5,
        max_delay: float = 3.0,
        mouse_speed: float = 1.0,
        enable_fingerprint_rotation: bool = True,
        proxy_list: Optional[List[str]] = None,
        session_dir: Optional[Path] = None,
    ):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.mouse_speed = mouse_speed
        self.enable_fingerprint_rotation = enable_fingerprint_rotation
        self.session_dir = session_dir or Path("sessions")
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # Proxy management
        self.proxies: List[ProxyConfig] = []
        if proxy_list:
            for url in proxy_list:
                self.proxies.append(ProxyConfig(url=url))
        self._proxy_index = 0
        
        # Current fingerprint
        self._fingerprint: Optional[FingerprintProfile] = None
        
        # Action tracking for natural behavior
        self._action_count = 0
        self._session_start = time.time()
    
    # -------------------------------------------------------------------------
    # Delay & Timing
    # -------------------------------------------------------------------------
    
    def human_delay(self, base: float = 1.0, jitter: float = 0.5) -> float:
        """
        Generate a human-like delay with natural variance.
        Uses a log-normal distribution for more realistic timing.
        """
        # Log-normal distribution creates more natural timing variance
        mu = math.log(base)
        sigma = jitter * 0.5
        delay = random.lognormvariate(mu, sigma)
        
        # Clamp to reasonable bounds
        delay = max(self.min_delay, min(self.max_delay, delay))
        
        # Occasionally add a longer pause (simulating distraction)
        if random.random() < 0.05:  # 5% chance
            delay += random.uniform(1.0, 3.0)
        
        time.sleep(delay)
        return delay
    
    def micro_delay(self) -> None:
        """Very short delay between rapid actions."""
        time.sleep(random.uniform(0.05, 0.2))
    
    def thinking_pause(self) -> None:
        """Longer pause simulating human thinking/reading."""
        time.sleep(random.uniform(2.0, 5.0))
    
    # -------------------------------------------------------------------------
    # Mouse Movement
    # -------------------------------------------------------------------------
    
    def _bezier_curve(
        self, 
        start: Tuple[float, float], 
        end: Tuple[float, float], 
        control_points: int = 2
    ) -> List[Tuple[float, float]]:
        """
        Generate points along a Bezier curve for natural mouse movement.
        """
        points = [start]
        
        # Generate random control points for natural curves
        controls = []
        for _ in range(control_points):
            cx = random.uniform(min(start[0], end[0]), max(start[0], end[0]))
            cy = random.uniform(min(start[1], end[1]), max(start[1], end[1]))
            # Add some variance outside the direct path
            cx += random.uniform(-50, 50)
            cy += random.uniform(-50, 50)
            controls.append((cx, cy))
        
        all_points = [start] + controls + [end]
        
        # Calculate bezier curve points
        steps = int(30 / self.mouse_speed)
        for t in range(1, steps + 1):
            t_norm = t / steps
            point = self._de_casteljau(all_points, t_norm)
            points.append(point)
        
        return points
    
    def _de_casteljau(
        self, 
        points: List[Tuple[float, float]], 
        t: float
    ) -> Tuple[float, float]:
        """De Casteljau's algorithm for Bezier curve calculation."""
        if len(points) == 1:
            return points[0]
        
        new_points = []
        for i in range(len(points) - 1):
            x = (1 - t) * points[i][0] + t * points[i + 1][0]
            y = (1 - t) * points[i][1] + t * points[i + 1][1]
            new_points.append((x, y))
        
        return self._de_casteljau(new_points, t)
    
    def mouse_move_human(
        self, 
        page: Page, 
        target_x: float, 
        target_y: float,
        start_x: Optional[float] = None,
        start_y: Optional[float] = None,
    ) -> None:
        """
        Move mouse to target position using human-like Bezier curve path.
        """
        try:
            # Get current position or use random start
            if start_x is None or start_y is None:
                viewport = page.viewport_size or {"width": 1280, "height": 800}
                start_x = random.uniform(0, viewport["width"])
                start_y = random.uniform(0, viewport["height"])
            
            # Generate curve path
            path = self._bezier_curve((start_x, start_y), (target_x, target_y))
            
            # Move along path with variable speed
            for i, (x, y) in enumerate(path):
                # Variable speed - slower at start and end
                progress = i / len(path)
                speed_factor = 1 - (4 * (progress - 0.5) ** 2)  # Parabolic
                delay = random.uniform(0.01, 0.03) * (1 + speed_factor)
                
                page.mouse.move(x, y)
                time.sleep(delay)
                
        except Exception:
            # Fallback to direct move
            page.mouse.move(target_x, target_y)
    
    def click_human(self, page: Page, x: float, y: float) -> None:
        """Human-like click with movement and natural timing."""
        self.mouse_move_human(page, x, y)
        self.micro_delay()
        
        # Small position jitter before click
        jitter_x = x + random.uniform(-2, 2)
        jitter_y = y + random.uniform(-2, 2)
        page.mouse.click(jitter_x, jitter_y)
        
        self.micro_delay()
    
    # -------------------------------------------------------------------------
    # Scrolling
    # -------------------------------------------------------------------------
    
    def scroll_naturally(
        self, 
        page: Page, 
        distance: int = 500,
        direction: str = "down"
    ) -> None:
        """
        Scroll with human-like patterns - variable speed and occasional pauses.
        """
        total_scrolled = 0
        direction_mult = 1 if direction == "down" else -1
        
        while total_scrolled < abs(distance):
            # Variable chunk size
            chunk = random.randint(50, 200)
            chunk = min(chunk, abs(distance) - total_scrolled)
            
            # Scroll
            page.mouse.wheel(0, chunk * direction_mult)
            total_scrolled += chunk
            
            # Variable pause between scroll chunks
            time.sleep(random.uniform(0.05, 0.15))
            
            # Occasional longer pause (reading)
            if random.random() < 0.1:
                time.sleep(random.uniform(0.5, 1.5))
        
        # Final settling pause
        time.sleep(random.uniform(0.3, 0.8))
    
    def scroll_to_bottom_naturally(self, page: Page, max_scrolls: int = 20) -> None:
        """Scroll to bottom with natural behavior patterns."""
        last_height = 0
        scroll_count = 0
        
        while scroll_count < max_scrolls:
            # Get current scroll height
            try:
                current_height = page.evaluate("document.body.scrollHeight")
            except Exception:
                break
            
            if current_height == last_height:
                # Try one more time with delay
                self.thinking_pause()
                try:
                    current_height = page.evaluate("document.body.scrollHeight")
                except Exception:
                    break
                if current_height == last_height:
                    break
            
            last_height = current_height
            
            # Natural scroll amount
            scroll_amount = random.randint(300, 800)
            self.scroll_naturally(page, scroll_amount)
            
            # Occasional pause to "read" content
            if random.random() < 0.2:
                self.thinking_pause()
            else:
                self.human_delay(0.8, 0.3)
            
            scroll_count += 1
    
    # -------------------------------------------------------------------------
    # Fingerprint Management
    # -------------------------------------------------------------------------
    
    def get_fingerprint(self, rotate: bool = False) -> FingerprintProfile:
        """Get current fingerprint, optionally rotating to a new one."""
        if self._fingerprint is None or rotate:
            self._fingerprint = FingerprintProfile.random()
        return self._fingerprint
    
    def apply_fingerprint(self, context: BrowserContext) -> None:
        """Apply fingerprint modifications to browser context."""
        fp = self.get_fingerprint()
        
        # Note: Some fingerprint aspects need to be set at context creation
        # This applies runtime modifications
        try:
            # Emulate timezone
            context.set_geolocation({"latitude": 0, "longitude": 0})
            
            # Add scripts to modify navigator properties
            context.add_init_script(f"""
                Object.defineProperty(navigator, 'platform', {{
                    get: () => '{fp.platform}'
                }});
                
                Object.defineProperty(navigator, 'language', {{
                    get: () => '{fp.locale}'
                }});
                
                Object.defineProperty(navigator, 'languages', {{
                    get: () => ['{fp.locale}', 'en']
                }});
                
                // WebGL fingerprint spoofing
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                    if (parameter === 37445) return '{fp.webgl_vendor}';
                    if (parameter === 37446) return '{fp.webgl_renderer}';
                    return getParameter.call(this, parameter);
                }};
            """)
        except Exception:
            pass  # Silently fail if fingerprint spoofing not possible
    
    def get_context_options(self) -> Dict[str, Any]:
        """Get browser context options with fingerprint applied."""
        fp = self.get_fingerprint(rotate=self.enable_fingerprint_rotation)
        
        return {
            "user_agent": fp.user_agent,
            "viewport": {"width": fp.viewport_width, "height": fp.viewport_height},
            "locale": fp.locale,
            "timezone_id": fp.timezone_id,
            "color_scheme": fp.color_scheme,
        }
    
    # -------------------------------------------------------------------------
    # Proxy Management
    # -------------------------------------------------------------------------
    
    def get_next_proxy(self) -> Optional[str]:
        """Get next healthy proxy from the pool with round-robin rotation."""
        if not self.proxies:
            return None
        
        # Find next healthy proxy
        attempts = 0
        while attempts < len(self.proxies):
            proxy = self.proxies[self._proxy_index]
            self._proxy_index = (self._proxy_index + 1) % len(self.proxies)
            
            if proxy.is_healthy:
                proxy.last_used = time.time()
                return proxy.url
            
            attempts += 1
        
        # All proxies unhealthy, reset and try again
        for p in self.proxies:
            p.is_healthy = True
            p.failures = 0
        
        return self.proxies[0].url if self.proxies else None
    
    def mark_proxy_failure(self, proxy_url: str) -> None:
        """Mark a proxy as failed."""
        for p in self.proxies:
            if p.url == proxy_url:
                p.mark_failure()
                break
    
    def mark_proxy_success(self, proxy_url: str) -> None:
        """Mark a proxy as successful."""
        for p in self.proxies:
            if p.url == proxy_url:
                p.mark_success()
                break
    
    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------
    
    def _get_session_file(self, session_id: str) -> Path:
        """Get session file path."""
        safe_id = hashlib.md5(session_id.encode()).hexdigest()[:16]
        return self.session_dir / f"session_{safe_id}.json"
    
    def save_session(self, session_id: str, cookies: List[Dict]) -> None:
        """Save session cookies for later reuse."""
        session_file = self._get_session_file(session_id)
        data = {
            "cookies": cookies,
            "saved_at": time.time(),
            "fingerprint": self._fingerprint.__dict__ if self._fingerprint else None,
        }
        with open(session_file, "w") as f:
            json.dump(data, f)
    
    def load_session(self, session_id: str) -> Optional[Dict]:
        """Load previously saved session."""
        session_file = self._get_session_file(session_id)
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, "r") as f:
                data = json.load(f)
            
            # Check if session is not too old (24 hours)
            if time.time() - data.get("saved_at", 0) > 86400:
                session_file.unlink()
                return None
            
            return data
        except Exception:
            return None
    
    def apply_session(self, context: BrowserContext, session_id: str) -> bool:
        """Apply saved session to browser context."""
        session = self.load_session(session_id)
        if not session:
            return False
        
        try:
            context.add_cookies(session.get("cookies", []))
            
            # Restore fingerprint if available
            fp_data = session.get("fingerprint")
            if fp_data:
                self._fingerprint = FingerprintProfile(**fp_data)
            
            return True
        except Exception:
            return False
    
    # -------------------------------------------------------------------------
    # Behavior Tracking
    # -------------------------------------------------------------------------
    
    def track_action(self) -> None:
        """Track an action for behavior analysis."""
        self._action_count += 1
        
        # Occasionally take a longer break (simulating human behavior)
        if self._action_count % 50 == 0:
            self.thinking_pause()
        
        # Check for session duration breaks
        session_duration = time.time() - self._session_start
        if session_duration > 1800:  # 30 minutes
            # Take a break and reset
            self.thinking_pause()
            self.thinking_pause()
            self._session_start = time.time()
    
    def should_take_break(self) -> bool:
        """Determine if a break should be taken based on activity."""
        session_duration = time.time() - self._session_start
        
        # Random chance based on session length
        break_probability = min(0.1, session_duration / 36000)  # Max 10% at 1 hour
        return random.random() < break_probability
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def randomize_typing(self, page: Page, text: str, selector: str) -> None:
        """Type text with human-like timing variations."""
        element = page.locator(selector)
        element.click()
        self.micro_delay()
        
        for char in text:
            element.type(char, delay=random.randint(50, 150))
            
            # Occasional pause between characters
            if random.random() < 0.05:
                time.sleep(random.uniform(0.2, 0.5))
        
        self.micro_delay()
    
    def simulate_reading(self, page: Page, content_length: int = 500) -> None:
        """Simulate reading by scrolling and pausing."""
        # Estimate reading time (200 words per minute average)
        words = content_length / 5  # Approximate words
        read_time = (words / 200) * 60  # Seconds
        read_time = min(read_time, 30)  # Cap at 30 seconds
        
        # Break reading into chunks with scrolling
        chunks = max(1, int(read_time / 5))
        for _ in range(chunks):
            time.sleep(random.uniform(3, 7))
            if random.random() < 0.5:
                self.scroll_naturally(page, random.randint(100, 300))


# Convenience functions
def create_antidetect(
    aggressive: bool = False,
    proxy_list: Optional[List[str]] = None,
) -> AntiDetect:
    """Create an AntiDetect instance with common configurations."""
    if aggressive:
        return AntiDetect(
            min_delay=0.5,  # Reduced from 1.0
            max_delay=3.0,  # Reduced from 5.0
            mouse_speed=0.7,
            enable_fingerprint_rotation=True,
            proxy_list=proxy_list,
        )
    else:
        return AntiDetect(
            min_delay=0.1,  # Reduced from 0.3
            max_delay=1.0,  # Reduced from 2.0
            mouse_speed=1.5,
            enable_fingerprint_rotation=False,
            proxy_list=proxy_list,
        )
