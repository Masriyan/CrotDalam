#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Real-Time Monitoring & Alert Module
Scheduled scans with Telegram and Discord alert integration.
"""
from __future__ import annotations

import json
import time
import threading
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests
from rich import print as rprint

from crot_dalam.models.data import MonitorConfig, ScanConfig, ScanResult


class AlertChannel:
    """Base class for alert delivery channels."""
    
    def send(self, title: str, message: str, severity: str = "info") -> bool:
        raise NotImplementedError


class TelegramAlert(AlertChannel):
    """Send alerts via Telegram Bot API."""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_base = f"https://api.telegram.org/bot{bot_token}"
    
    def send(self, title: str, message: str, severity: str = "info") -> bool:
        """Send alert message via Telegram."""
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "warning": "🟡",
            "info": "🔵",
        }
        
        emoji = severity_emoji.get(severity, "🔵")
        text = f"{emoji} *{title}*\n\n{message}"
        
        try:
            resp = requests.post(
                f"{self.api_base}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            return resp.status_code == 200
        except Exception as e:
            rprint(f"[red]Telegram alert failed: {e}[/red]")
            return False


class DiscordAlert(AlertChannel):
    """Send alerts via Discord webhook."""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send(self, title: str, message: str, severity: str = "info") -> bool:
        """Send alert message via Discord webhook."""
        color_map = {
            "critical": 0xFF0000,
            "high": 0xFF8C00,
            "warning": 0xFFD700,
            "info": 0x0099FF,
        }
        
        embed = {
            "title": title,
            "description": message,
            "color": color_map.get(severity, 0x0099FF),
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "CROT DALAM Monitor"},
        }
        
        try:
            resp = requests.post(
                self.webhook_url,
                json={"embeds": [embed]},
                timeout=15,
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            rprint(f"[red]Discord alert failed: {e}[/red]")
            return False


class Monitor:
    """
    Real-time monitoring daemon.
    
    Runs scheduled scans at configurable intervals and sends
    alerts via Telegram/Discord when high-risk content is found.
    """
    
    def __init__(
        self,
        config: MonitorConfig,
        scan_factory: Optional[Callable[[ScanConfig], Any]] = None,
        state_dir: Optional[Path] = None,
    ):
        self.config = config
        self.scan_factory = scan_factory
        self.state_dir = state_dir or Path("monitor_state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        # Alert channels
        self._channels: List[AlertChannel] = []
        self._setup_channels()
        
        # State
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._iteration = 0
        self._seen_videos: set = set()
        
        # Load persistent state
        self._load_state()
    
    def _setup_channels(self) -> None:
        """Configure alert channels from monitor config."""
        if (self.config.alert_telegram_bot_token and 
            self.config.alert_telegram_chat_id):
            self._channels.append(TelegramAlert(
                bot_token=self.config.alert_telegram_bot_token,
                chat_id=self.config.alert_telegram_chat_id,
            ))
            rprint("[green]✓ Telegram alerts configured[/green]")
        
        if self.config.alert_webhook_url:
            self._channels.append(DiscordAlert(
                webhook_url=self.config.alert_webhook_url,
            ))
            rprint("[green]✓ Discord alerts configured[/green]")
    
    def _load_state(self) -> None:
        """Load previously seen video IDs to avoid duplicate alerts."""
        state_file = self.state_dir / "seen_videos.json"
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    self._seen_videos = set(json.load(f))
            except Exception:
                self._seen_videos = set()
    
    def _save_state(self) -> None:
        """Persist seen video IDs."""
        state_file = self.state_dir / "seen_videos.json"
        try:
            # Keep only last 10000 entries to prevent unbounded growth
            recent = list(self._seen_videos)[-10000:]
            with open(state_file, "w") as f:
                json.dump(recent, f)
        except Exception as e:
            rprint(f"[yellow]Failed to save monitor state: {e}[/yellow]")
    
    def _generate_video_hash(self, video_id: str, url: str) -> str:
        """Generate unique hash for deduplication."""
        return hashlib.sha256(f"{video_id}:{url}".encode()).hexdigest()[:16]
    
    def send_alert(self, title: str, message: str, severity: str = "info") -> None:
        """Send alert to all configured channels."""
        for channel in self._channels:
            try:
                channel.send(title, message, severity)
            except Exception as e:
                rprint(f"[yellow]Alert channel error: {e}[/yellow]")
    
    def _run_iteration(self) -> Optional[ScanResult]:
        """Execute a single monitoring iteration."""
        self._iteration += 1
        rprint(f"\n[bold cyan]═══ Monitor Iteration #{self._iteration} ═══[/bold cyan]")
        rprint(f"[dim]{datetime.now().isoformat()}[/dim]")
        
        if not self.scan_factory:
            rprint("[red]No scan factory configured[/red]")
            return None
        
        # Build scan config
        scan_config = self.config.scan_config or ScanConfig(
            keywords=self.config.keywords,
            limit=30,
            headless=True,
            antidetect_enabled=True,
        )
        
        if not scan_config.keywords:
            scan_config.keywords = self.config.keywords
        
        try:
            scraper = self.scan_factory(scan_config)
            result = scraper.run_scan()
            
            # Process new findings
            new_high_risk = []
            for video in result.videos:
                vid_hash = self._generate_video_hash(video.video_id, video.url)
                if vid_hash not in self._seen_videos:
                    self._seen_videos.add(vid_hash)
                    if video.risk_score >= 5:
                        new_high_risk.append(video)
            
            # Send alerts for new high-risk findings
            if new_high_risk and self.config.alert_on_high_risk:
                self._send_risk_alert(new_high_risk)
            
            # Save state
            self._save_state()
            
            rprint(f"[green]Iteration complete: {result.total_videos} videos, "
                   f"{len(new_high_risk)} new high-risk[/green]")
            
            return result
            
        except Exception as e:
            rprint(f"[red]Monitor iteration failed: {e}[/red]")
            self.send_alert(
                "⚠️ Monitor Error",
                f"Iteration #{self._iteration} failed: {str(e)}",
                severity="warning",
            )
            return None
    
    def _send_risk_alert(self, high_risk_videos: list) -> None:
        """Send alert for new high-risk findings."""
        count = len(high_risk_videos)
        
        details = []
        for v in high_risk_videos[:5]:  # Limit to 5 in alert
            details.append(
                f"• @{v.username or 'unknown'} | Risk: {v.risk_score} | "
                f"{(v.description or '')[:80]}..."
            )
        
        message = (
            f"Found {count} new high-risk video(s)\n\n"
            + "\n".join(details)
        )
        
        if count > 5:
            message += f"\n\n...and {count - 5} more"
        
        self.send_alert(
            f"🚨 High Risk Content Detected ({count})",
            message,
            severity="critical" if count >= 3 else "high",
        )
    
    def start(self) -> None:
        """Start monitoring in background thread."""
        if self._running:
            rprint("[yellow]Monitor already running[/yellow]")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        rprint("[bold green]✓ Monitor started[/bold green]")
        
        # Send startup alert
        self.send_alert(
            "🟢 Monitor Started",
            f"Monitoring keywords: {', '.join(self.config.keywords)}\n"
            f"Interval: {self.config.interval_minutes} min",
            severity="info",
        )
    
    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        rprint("[bold yellow]Monitor stopping...[/bold yellow]")
        
        self.send_alert(
            "🔴 Monitor Stopped",
            f"Completed {self._iteration} iterations",
            severity="info",
        )
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            # Check max iterations
            if (self.config.max_iterations > 0 and 
                self._iteration >= self.config.max_iterations):
                rprint("[cyan]Max iterations reached, stopping[/cyan]")
                self._running = False
                break
            
            self._run_iteration()
            
            if self._running:
                rprint(f"[dim]Next scan in {self.config.interval_minutes} minutes...[/dim]")
                # Sleep in small increments to allow clean shutdown
                for _ in range(self.config.interval_minutes * 60):
                    if not self._running:
                        break
                    time.sleep(1)
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def iteration_count(self) -> int:
        return self._iteration
    
    def get_status(self) -> Dict[str, Any]:
        """Get current monitor status."""
        return {
            "running": self._running,
            "iteration": self._iteration,
            "seen_videos": len(self._seen_videos),
            "channels": len(self._channels),
            "keywords": self.config.keywords,
            "interval_minutes": self.config.interval_minutes,
        }
