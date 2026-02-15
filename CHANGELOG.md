# Changelog

All notable changes to CROT DALAM will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-02-14

### 🏗️ Enterprise-Grade Overhaul — Tactical OSINT Platform

#### Added

- **CAPTCHA Solver Module** (`core/captcha_solver.py`)
  - Auto-detection of slide puzzle, image rotation, click verify CAPTCHAs
  - Human-like physics solving (Bezier drag, rotation estimation)
  - External service fallback (2Captcha API)
  - Integrated into scraper navigation pipeline

- **Deep Profile Investigation** (`core/profiler.py`)
  - Credibility scoring (0-100) with engagement, follower anomaly detection
  - Bio risk scanning (suspicious patterns, wallet addresses, excessive URLs)
  - Account activity assessment and follower-following ratio analysis

- **Real-Time Monitoring Daemon** (`core/monitor.py`)
  - Scheduled background scans at configurable intervals
  - Telegram Bot API alerts with severity-based formatting
  - Discord webhook alerts with rich embeds
  - Persistent state deduplication (no duplicate alerts)
  - Clean shutdown support via threading

- **Circuit Breaker Pattern** in scraper
  - Auto-rotates identity after 5 consecutive failures
  - Prevents cascading failures during detection events

- **Retry with Exponential Backoff** decorator
  - Configurable retries, base delay, max delay, and jitter
  - Applied to `search_videos` for resilient search

- **New Risk Analysis Languages**
  - Japanese (financial scam, investment fraud, gambling)
  - Korean (financial scam, investment fraud, gambling)

- **New Risk Categories** (English)
  - Romance scam detection (gift cards, western union, etc.)
  - Impersonation detection (verified support, account recovery, etc.)

- **Expanded Entity Detection**
  - SOL, BNB, DOGE wallet address patterns
  - Additional URL shortener services (rb.gy, cutt.ly, is.gd)

#### Changed

- **GUI: Tactical Command Center** — complete redesign
  - Military-grade dark theme with tactical grid background
  - JetBrains Mono monospace typography for data display
  - Sidebar navigation (Dashboard, Scan, Results, History)
  - Real-time scan monitor with progress bars
  - Operation log console with timestamped entries
  - Risk badges with severity color coding
  - Toast notification system
  - Responsive layout for all screen sizes

- **Anti-Detection System** modernized to 2026 standards
  - Chrome 131/132, Firefox 134, Safari 18 user agents
  - Canvas noise injection with random RGBA perturbation
  - AudioContext fingerprint spoofing (custom sample rate + noise)
  - WebGL2 renderer/vendor spoofing
  - `navigator.webdriver` property deletion
  - New `rotate_identity()` method for session reset

- **Scraper Hardening**
  - CAPTCHA-aware navigation (`_navigate_with_captcha`)
  - Multiple search URL fallback for resilience
  - Enhanced scroll stagnation recovery (keyboard End, JS scroll)
  - Multiple CSS selector strategies for video collection
  - Download path now uses `resolve()` for absolute paths

- Bumped version to `3.0.0`

#### Fixed

- Race condition in active scan cleanup (threading.Lock + delayed cleanup)
- Scroll stagnation now recovers via keyboard End key and JS fallback
- Empty result handling with alternate URL fallback
- Download path handling returns resolved absolute path
- Missing `low_risk_count` added to `ScanResult` stats
- `VideoRecord.__repr__` added for better debugging

---

## [2.0.0] - 2026-02-03

### 🚀 Major Release — Complete Overhaul

#### Added

- **Modern Web GUI Dashboard**
  - Glassmorphism dark theme interface
  - Real-time progress via WebSocket
  - Interactive results table with filtering
  - Export controls (CSV, JSON, HTML)
  - Investigation queue management

- **Anti-Detection System**
  - Human-like behavior simulation (Bezier mouse curves, random delays)
  - Browser fingerprint rotation (viewport, timezone, WebGL)
  - Proxy pool rotation with health checking
  - Session/cookie persistence between runs
  - Adaptive rate limiting with jitter

- **Multi-Language Risk Detection**
  - Indonesian (expanded)
  - English (expanded)
  - Malay (new)
  - Vietnamese (new)
  - Thai (new)
  - Filipino (new)
  - Custom term support

- **New Features**
  - User profile deep analysis
  - Comment sentiment analysis
  - Mention extraction
  - Network/relationship mapping
  - Enhanced entity extraction (wallets, phones, emails)

- **Modular Package Structure**
  - `crot_dalam/core/` — Core scraping and analysis
  - `crot_dalam/gui/` — Web dashboard
  - `crot_dalam/models/` — Data classes
  - `crot_dalam/utils/` — Helpers and config

- **Documentation**
  - CONTRIBUTING.md
  - SECURITY.md
  - CHANGELOG.md
  - Comprehensive README with diagrams

#### Changed

- Refactored from single file to modular package
- Improved HTML report with dark theme and stats cards
- Enhanced error handling and resilience
- Better counter parsing (K, M, B suffixes)

#### Fixed

- Cookie banner handling for multiple languages
- Scroll stagnation detection
- Memory optimization for large scans

---

## [1.0.0] - 2025-10-03

### Added

- Initial release
- Keyword-based TikTok search
- Video metadata extraction
- Risk scoring (EN/ID)
- JSONL, CSV, HTML export
- Screenshot capture
- yt-dlp video downloads
- Archive.today snapshots
- Investigation modes (quick, moderate, deep, deeper)
- Hashtag pivoting
- Comment collection
