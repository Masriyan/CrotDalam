# Changelog

All notable changes to CROT DALAM will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
