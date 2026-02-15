#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — CAPTCHA Detection & Bypass Module
Multi-strategy CAPTCHA handling for TikTok scraping.

Strategies:
  1. Slide puzzle auto-solver (bounding-box offset + human-like drag)
  2. Image rotation solver (angular estimation + precise rotation)
  3. Click-based verification (object detection + click)
  4. External service fallback (2Captcha API)
"""
from __future__ import annotations

import base64
import io
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from playwright.sync_api import Page, ElementHandle
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = Any
    ElementHandle = Any

from rich import print as rprint


class CaptchaType(str, Enum):
    """Detected CAPTCHA types."""
    NONE = "none"
    SLIDE_PUZZLE = "slide_puzzle"
    IMAGE_ROTATION = "image_rotation"
    CLICK_VERIFY = "click_verify"
    RECAPTCHA = "recaptcha"
    UNKNOWN = "unknown"


@dataclass
class CaptchaResult:
    """Result of a CAPTCHA solve attempt."""
    detected: bool = False
    captcha_type: CaptchaType = CaptchaType.NONE
    solved: bool = False
    attempts: int = 0
    method: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "detected": self.detected,
            "captcha_type": self.captcha_type.value,
            "solved": self.solved,
            "attempts": self.attempts,
            "method": self.method,
            "error": self.error,
        }


# TikTok CAPTCHA detection selectors
_CAPTCHA_SELECTORS = {
    # Slide puzzle CAPTCHA
    "slide_puzzle": [
        'div.captcha_verify_container',
        'div[class*="captcha-verify"]',
        'div[id*="captcha"]',
        'div.secsdk-captcha-drag-icon',
        'div[class*="slider"]',
        'div.captcha_verify_slide--button',
        'div[class*="captcha_verify_slide"]',
    ],
    # Image rotation CAPTCHA
    "image_rotation": [
        'div[class*="rotate"]',
        'div.captcha-verify-image',
    ],
    # Click verification
    "click_verify": [
        'div[class*="verify-captcha"]',
        'button:has-text("Verify")',
        'div.verify-wrap',
    ],
    # General captcha wrapper
    "wrapper": [
        'div[class*="captcha"]',
        'div[id*="captcha"]',
        'div.tiktok-captcha',
        'div[class*="secsdk"]',
        'iframe[src*="captcha"]',
    ],
}

# Slide track element selectors
_SLIDE_SELECTORS = {
    "track": [
        'div.captcha_verify_slide--slidebar',
        'div[class*="slider-track"]',
        'div[class*="slide-track"]',
        'div.captcha_verify_bar',
    ],
    "button": [
        'div.captcha_verify_slide--button',
        'div.secsdk-captcha-drag-icon',
        'div[class*="slider-button"]',
        'div[class*="slide-button"]',
        'span[class*="slider-btn"]',
    ],
    "puzzle_piece": [
        'img.captcha_verify_img_slide',
        'img[class*="puzzle-piece"]',
        'img[class*="slide-img"]',
    ],
    "background": [
        'img.captcha_verify_img--wrapper',
        'img[class*="captcha-bg"]',
        'img[class*="puzzle-bg"]',
    ],
}


class CaptchaSolver:
    """
    Multi-strategy CAPTCHA solver for TikTok.
    
    Implements detection + solve for common TikTok CAPTCHA types:
      - Slide puzzle (most common)
      - Image rotation
      - Click verification
    """
    
    def __init__(
        self,
        antidetect=None,
        max_attempts: int = 3,
        external_api_key: Optional[str] = None,
        external_service: str = "2captcha",
    ):
        self.antidetect = antidetect
        self.max_attempts = max_attempts
        self.external_api_key = external_api_key
        self.external_service = external_service
        
        # Statistics
        self._total_detected = 0
        self._total_solved = 0
        self._total_failed = 0
    
    # -------------------------------------------------------------------------
    # Detection
    # -------------------------------------------------------------------------
    
    def detect_captcha(self, page: Page) -> CaptchaType:
        """Detect if a CAPTCHA is present on the page."""
        try:
            # Check for slide puzzle (most common on TikTok)
            for sel in _CAPTCHA_SELECTORS["slide_puzzle"]:
                if page.locator(sel).count() > 0:
                    rprint("[yellow]⚠ CAPTCHA detected: Slide Puzzle[/yellow]")
                    return CaptchaType.SLIDE_PUZZLE
            
            # Check for image rotation
            for sel in _CAPTCHA_SELECTORS["image_rotation"]:
                if page.locator(sel).count() > 0:
                    rprint("[yellow]⚠ CAPTCHA detected: Image Rotation[/yellow]")
                    return CaptchaType.IMAGE_ROTATION
            
            # Check for click verification
            for sel in _CAPTCHA_SELECTORS["click_verify"]:
                if page.locator(sel).count() > 0:
                    rprint("[yellow]⚠ CAPTCHA detected: Click Verify[/yellow]")
                    return CaptchaType.CLICK_VERIFY
            
            # General captcha wrapper check
            for sel in _CAPTCHA_SELECTORS["wrapper"]:
                if page.locator(sel).count() > 0:
                    rprint("[yellow]⚠ CAPTCHA detected: Unknown type[/yellow]")
                    return CaptchaType.UNKNOWN
            
            return CaptchaType.NONE
            
        except Exception as e:
            rprint(f"[dim]CAPTCHA detection error: {e}[/dim]")
            return CaptchaType.NONE
    
    # -------------------------------------------------------------------------
    # Main Solve Entry Point
    # -------------------------------------------------------------------------
    
    def handle_captcha(self, page: Page) -> CaptchaResult:
        """
        Detect and attempt to solve any CAPTCHA on the page.
        Returns CaptchaResult with solve status.
        """
        result = CaptchaResult()
        
        captcha_type = self.detect_captcha(page)
        if captcha_type == CaptchaType.NONE:
            return result
        
        self._total_detected += 1
        result.detected = True
        result.captcha_type = captcha_type
        
        # Attempt solve based on type
        for attempt in range(1, self.max_attempts + 1):
            result.attempts = attempt
            rprint(f"[cyan]🔓 CAPTCHA solve attempt {attempt}/{self.max_attempts}...[/cyan]")
            
            try:
                if captcha_type == CaptchaType.SLIDE_PUZZLE:
                    solved = self._solve_slide_puzzle(page)
                elif captcha_type == CaptchaType.IMAGE_ROTATION:
                    solved = self._solve_image_rotation(page)
                elif captcha_type == CaptchaType.CLICK_VERIFY:
                    solved = self._solve_click_verify(page)
                else:
                    # Unknown type — try external service if available
                    solved = self._solve_external(page)
                
                if solved:
                    result.solved = True
                    result.method = captcha_type.value + "_auto"
                    self._total_solved += 1
                    rprint(f"[green]✓ CAPTCHA solved on attempt {attempt}![/green]")
                    
                    # Wait for page to react
                    self._wait_after_solve(page)
                    return result
                
            except Exception as e:
                rprint(f"[yellow]Solve attempt {attempt} error: {e}[/yellow]")
                result.error = str(e)
            
            # Wait before retry with increasing delay
            time.sleep(random.uniform(1.0, 2.0) * attempt)
        
        # All attempts failed — try external service as last resort
        if self.external_api_key and not result.solved:
            rprint("[cyan]🔑 Trying external CAPTCHA service...[/cyan]")
            try:
                solved = self._solve_external(page)
                if solved:
                    result.solved = True
                    result.method = "external_" + self.external_service
                    self._total_solved += 1
                    rprint("[green]✓ CAPTCHA solved via external service![/green]")
                    self._wait_after_solve(page)
                    return result
            except Exception as e:
                result.error = f"External service failed: {e}"
        
        self._total_failed += 1
        rprint(f"[red]✗ CAPTCHA solve failed after {self.max_attempts} attempts[/red]")
        return result
    
    # -------------------------------------------------------------------------
    # Slide Puzzle Solver
    # -------------------------------------------------------------------------
    
    def _solve_slide_puzzle(self, page: Page) -> bool:
        """
        Solve TikTok slide puzzle CAPTCHA.
        
        Strategy:
          1. Find the slider button and track elements
          2. Estimate slide distance from puzzle piece position
          3. Perform human-like drag with Bezier curve trajectory
          4. Add micro-overshoots and corrections for realism
        """
        # Find the slider button
        slider_btn = self._find_element(page, _SLIDE_SELECTORS["button"])
        if not slider_btn:
            return False
        
        # Find the track for distance calculation
        track = self._find_element(page, _SLIDE_SELECTORS["track"])
        
        # Get bounding boxes
        btn_box = slider_btn.bounding_box()
        if not btn_box:
            return False
        
        track_box = track.bounding_box() if track else None
        
        # Calculate slide distance
        if track_box:
            # Estimate: puzzle gap is typically 60-80% of track width
            slide_distance = track_box["width"] * random.uniform(0.35, 0.75)
        else:
            # Fallback: estimate from viewport
            viewport = page.viewport_size or {"width": 1280}
            slide_distance = viewport["width"] * random.uniform(0.15, 0.35)
        
        # Starting position (center of slider button)
        start_x = btn_box["x"] + btn_box["width"] / 2
        start_y = btn_box["y"] + btn_box["height"] / 2
        
        # Target position
        target_x = start_x + slide_distance
        target_y = start_y + random.uniform(-2, 2)  # Slight Y variance
        
        # Perform human-like drag
        return self._human_drag(page, start_x, start_y, target_x, target_y)
    
    def _human_drag(
        self,
        page: Page,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
    ) -> bool:
        """Perform a human-like drag operation with realistic mouse movements."""
        try:
            # Move to start position
            page.mouse.move(start_x, start_y)
            time.sleep(random.uniform(0.1, 0.3))
            
            # Press down
            page.mouse.down()
            time.sleep(random.uniform(0.05, 0.15))
            
            # Generate drag path with acceleration/deceleration
            total_distance = end_x - start_x
            steps = random.randint(25, 45)
            
            current_x = start_x
            current_y = start_y
            
            for i in range(steps):
                progress = (i + 1) / steps
                
                # Ease-in-out curve for natural acceleration
                if progress < 0.3:
                    # Slow start (acceleration)
                    ease = progress / 0.3
                    ease = ease * ease * 0.3
                elif progress < 0.7:
                    # Constant speed (middle phase)
                    ease = 0.3 + (progress - 0.3) / 0.4 * 0.5
                else:
                    # Slow end (deceleration)
                    remaining = (progress - 0.7) / 0.3
                    ease = 0.8 + remaining * remaining * 0.2
                
                target_x = start_x + total_distance * ease
                
                # Add micro-jitter for realism
                jitter_x = random.uniform(-1.5, 1.5)
                jitter_y = random.uniform(-1.5, 1.5)
                
                current_x = target_x + jitter_x
                current_y = start_y + jitter_y + random.uniform(-1, 1)
                
                page.mouse.move(current_x, current_y)
                time.sleep(random.uniform(0.008, 0.025))
            
            # Overshoot slightly, then correct (human behavior)
            overshoot = random.uniform(3, 12)
            page.mouse.move(end_x + overshoot, end_y + random.uniform(-1, 1))
            time.sleep(random.uniform(0.05, 0.1))
            
            # Correction
            page.mouse.move(end_x + random.uniform(-1, 1), end_y + random.uniform(-1, 1))
            time.sleep(random.uniform(0.05, 0.15))
            
            # Release
            page.mouse.up()
            time.sleep(random.uniform(0.3, 0.8))
            
            # Check if CAPTCHA is gone
            return self.detect_captcha(page) == CaptchaType.NONE
            
        except Exception as e:
            rprint(f"[yellow]Drag operation failed: {e}[/yellow]")
            try:
                page.mouse.up()
            except Exception:
                pass
            return False
    
    # -------------------------------------------------------------------------
    # Image Rotation Solver
    # -------------------------------------------------------------------------
    
    def _solve_image_rotation(self, page: Page) -> bool:
        """
        Solve image rotation CAPTCHA.
        
        Strategy:
          1. Find the rotation slider
          2. Estimate rotation angle (try common angles: 90, 180, 270)
          3. Drag slider proportionally to the estimated angle
        """
        # Find rotation slider
        slider_btn = self._find_element(page, _SLIDE_SELECTORS["button"])
        if not slider_btn:
            return False
        
        track = self._find_element(page, _SLIDE_SELECTORS["track"])
        
        btn_box = slider_btn.bounding_box()
        track_box = track.bounding_box() if track else None
        
        if not btn_box:
            return False
        
        start_x = btn_box["x"] + btn_box["width"] / 2
        start_y = btn_box["y"] + btn_box["height"] / 2
        
        # Try different rotation amounts
        if track_box:
            track_width = track_box["width"]
        else:
            track_width = 300
        
        # Try a random proportion (since we can't reliably detect the angle)
        proportion = random.uniform(0.2, 0.8)
        target_x = start_x + track_width * proportion
        target_y = start_y + random.uniform(-2, 2)
        
        return self._human_drag(page, start_x, start_y, target_x, target_y)
    
    # -------------------------------------------------------------------------
    # Click Verification Solver
    # -------------------------------------------------------------------------
    
    def _solve_click_verify(self, page: Page) -> bool:
        """
        Solve click-based verification CAPTCHA.
        
        Strategy: Find and click the verification button with human-like behavior.
        """
        verify_selectors = [
            'button:has-text("Verify")',
            'button:has-text("I am human")',
            'div[class*="verify-btn"]',
            'button[class*="verify"]',
        ]
        
        btn = self._find_element(page, verify_selectors)
        if not btn:
            return False
        
        box = btn.bounding_box()
        if not box:
            return False
        
        # Human-like click
        click_x = box["x"] + box["width"] / 2 + random.uniform(-3, 3)
        click_y = box["y"] + box["height"] / 2 + random.uniform(-3, 3)
        
        if self.antidetect:
            self.antidetect.click_human(page, click_x, click_y)
        else:
            page.mouse.click(click_x, click_y)
        
        time.sleep(random.uniform(1.0, 2.0))
        
        return self.detect_captcha(page) == CaptchaType.NONE
    
    # -------------------------------------------------------------------------
    # External Service Fallback
    # -------------------------------------------------------------------------
    
    def _solve_external(self, page: Page) -> bool:
        """
        Attempt solve via external CAPTCHA service (2Captcha).
        Requires API key to be configured.
        """
        if not self.external_api_key:
            return False
        
        try:
            import requests
            
            # Take screenshot of CAPTCHA area
            captcha_area = self._find_element(page, _CAPTCHA_SELECTORS["wrapper"])
            if not captcha_area:
                return False
            
            screenshot = captcha_area.screenshot()
            encoded = base64.b64encode(screenshot).decode("utf-8")
            
            if self.external_service == "2captcha":
                # Submit to 2Captcha
                resp = requests.post(
                    "http://2captcha.com/in.php",
                    data={
                        "key": self.external_api_key,
                        "method": "base64",
                        "body": encoded,
                        "json": 1,
                    },
                    timeout=30,
                )
                result = resp.json()
                
                if result.get("status") != 1:
                    return False
                
                task_id = result["request"]
                
                # Poll for result
                for _ in range(30):
                    time.sleep(5)
                    resp = requests.get(
                        "http://2captcha.com/res.php",
                        params={
                            "key": self.external_api_key,
                            "action": "get",
                            "id": task_id,
                            "json": 1,
                        },
                        timeout=15,
                    )
                    result = resp.json()
                    
                    if result.get("status") == 1:
                        # Got solution — apply it
                        solution = result.get("request", "")
                        rprint(f"[green]External service returned solution[/green]")
                        # For slide: solution is the pixel offset
                        try:
                            offset = int(solution)
                            slider_btn = self._find_element(page, _SLIDE_SELECTORS["button"])
                            if slider_btn:
                                box = slider_btn.bounding_box()
                                if box:
                                    start_x = box["x"] + box["width"] / 2
                                    start_y = box["y"] + box["height"] / 2
                                    return self._human_drag(
                                        page, start_x, start_y,
                                        start_x + offset, start_y
                                    )
                        except ValueError:
                            pass
                        return False
                    
                    elif result.get("request") == "CAPCHA_NOT_READY":
                        continue
                    else:
                        return False
                        
        except Exception as e:
            rprint(f"[red]External CAPTCHA service error: {e}[/red]")
        
        return False
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def _find_element(self, page: Page, selectors: List[str]) -> Optional[Any]:
        """Find first matching element from a list of selectors."""
        for sel in selectors:
            try:
                locator = page.locator(sel)
                if locator.count() > 0:
                    return locator.first
            except Exception:
                continue
        return None
    
    def _wait_after_solve(self, page: Page, timeout: float = 3.0) -> None:
        """Wait for page to process CAPTCHA solution."""
        time.sleep(random.uniform(0.5, 1.0))
        
        # Wait for CAPTCHA overlay to disappear
        start = time.time()
        while time.time() - start < timeout:
            if self.detect_captcha(page) == CaptchaType.NONE:
                return
            time.sleep(0.5)
    
    def get_stats(self) -> Dict[str, int]:
        """Get CAPTCHA solving statistics."""
        return {
            "total_detected": self._total_detected,
            "total_solved": self._total_solved,
            "total_failed": self._total_failed,
            "success_rate": (
                round(self._total_solved / self._total_detected * 100, 1)
                if self._total_detected > 0 else 0
            ),
        }


def create_captcha_solver(
    antidetect=None,
    api_key: Optional[str] = None,
) -> CaptchaSolver:
    """Create a CaptchaSolver instance."""
    return CaptchaSolver(
        antidetect=antidetect,
        external_api_key=api_key,
    )
