<p align="center">
  <img src="assets/banner.png" alt="CROT DALAM Banner" width="100%">
</p>

<h1 align="center">🔍 CROT DALAM v3.0</h1>

<p align="center">
  <strong>Collection & Reconnaissance Of TikTok — Discovery, Analysis, Logging, And Monitoring</strong>
</p>

<p align="center">
  <a href="#-features"><img src="https://img.shields.io/badge/Features-10-blue?style=for-the-badge" alt="Features"></a>
  <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick_Start-CLI%20%7C%20GUI-green?style=for-the-badge" alt="Quick Start"></a>
  <a href="#-anti--detection"><img src="https://img.shields.io/badge/Anti--Detection-2026-purple?style=for-the-badge" alt="Anti-Detection"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License"></a>
</p>

<p align="center">
  <em>Enterprise-grade TikTok OSINT platform with CAPTCHA bypass, anti-detection,<br>
  real-time monitoring, and tactical command center GUI. No API keys required.</em>
</p>

---

## 📋 Table of Contents

- [✨ Features](#-features)
- [🚀 Quick Start](#-quick-start)
- [🖥️ GUI Dashboard](#️-gui-dashboard)
- [⚡ CLI Usage](#-cli-usage)
- [🛡️ Anti-Detection](#️-anti-detection)
- [🔎 Risk Analysis](#-risk-analysis)
- [📊 Architecture](#-architecture)
- [🧠 How It Works](#-how-it-works)
- [📁 Output Files](#-output-files)
- [⚙️ Configuration](#️-configuration)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🎯 Core Capabilities

- **No API Keys Required** — Scrapes public TikTok pages
- **Keyword-Based Search** — Multiple keywords per scan
- **Video Metadata Extraction** — Full metrics & engagement
- **User Profile Analysis** — Deep profile reconnaissance
- **Comment Collection** — With sentiment analysis

</td>
<td width="50%">

### 🛡️ Protection & Stealth

- **Human-Like Behavior** — Bezier mouse movements
- **Fingerprint Rotation** — Viewport, timezone, WebGL
- **Proxy Pool Support** — Rotating proxy management
- **Session Persistence** — Cookie reuse across runs
- **Adaptive Rate Limiting** — Smart request throttling

</td>
</tr>
<tr>
<td>

### 📊 Analysis & Detection

- **Multi-Language Risk Scoring** — 6 languages supported
- **Entity Extraction** — Phones, wallets, emails, URLs
- **Sentiment Analysis** — Comment mood detection
- **Network Mapping** — Hashtag & mention graphs
- **Custom Risk Terms** — Add your own indicators

</td>
<td>

### 📦 Output & Evidence

- **Modern Web GUI** — Real-time dashboard
- **Multiple Export Formats** — JSONL, CSV, HTML
- **Screenshot Capture** — Full-page evidence
- **Video Downloads** — Via yt-dlp integration
- **Web Archive** — Archive.today snapshots

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Chromium (installed via Playwright)

### Installation

```bash
# Clone the repository
git clone https://github.com/Masriyan/CrotDalam.git
cd CrotDalam

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# (Optional) Install yt-dlp for video downloads
pip install yt-dlp
```

### First Run

```bash
# CLI Mode - Quick search
python -m crot_dalam.cli search "undian berhadiah" --mode quick --limit 10

# GUI Mode - Launch dashboard
python -m crot_dalam.cli gui
```

---

## 🖥️ GUI Dashboard

The modern web GUI provides a complete investigation management interface.

### Launch the Dashboard

```bash
python -m crot_dalam.cli gui --port 5000
```

Then open **http://localhost:5000** in your browser.

### Dashboard Features

```
┌─────────────────────────────────────────────────────────────────┐
│  🔍 CROT DALAM Dashboard                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  🚀 New Investigation                                    │   │
│  │  ┌─────────────────────────────────────────────────────┐│   │
│  │  │ Keywords: undian berhadiah, giveaway              ▼ ││   │
│  │  └─────────────────────────────────────────────────────┘│   │
│  │  Mode: [Deep ▼]   Limit: [60]   Locale: [en-US ▼]       │   │
│  │  ☑ Anti-Detection  ☐ Screenshots  ☐ Downloads          │   │
│  │                                    [🔍 Start]           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │    45    │ │    12    │ │     8    │ │   2m 35s │          │
│  │  Videos  │ │ HighRisk │ │ MedRisk  │ │ Duration │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Video ID  │ Description       │ Risk │ Engagement │ ...│   │
│  ├───────────┼───────────────────┼──────┼────────────┼────┤   │
│  │ 73829...  │ Transfer dulu...  │  8   │ ❤️ 12K     │ ...│   │
│  │ 82910...  │ Hadiah gratis...  │  5   │ ❤️ 8.2K    │ ...│   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Real-Time Updates

The dashboard uses WebSocket for live progress updates:

- Progress bar with percentage
- Live status messages
- Instant results on completion

---

## ⚡ CLI Usage

### Basic Search

```bash
# Single keyword search
python -m crot_dalam.cli search "crypto giveaway" --limit 50

# Multiple keywords
python -m crot_dalam.cli search "undian" "hadiah gratis" --limit 30 --locale id-ID

# Deep investigation mode
python -m crot_dalam.cli search "transfer dulu" --mode deep --limit 100
```

### Investigation Modes

| Mode       | Screenshots | Comments | Downloads | Archive | Pivot |
| ---------- | :---------: | :------: | :-------: | :-----: | :---: |
| `quick`    |     ❌      |    ❌    |    ❌     |   ❌    |  ❌   |
| `moderate` |     ✅      |    5     |    ❌     |   ❌    |  ❌   |
| `deep`     |     ✅      |    15    |    ✅     |   ✅    |   3   |
| `deeper`   |     ✅      |    30    |    ✅     |   ✅    |   5   |

### Full Options

```bash
python -m crot_dalam.cli search "keyword" \
  --mode deep \
  --limit 100 \
  --locale id-ID \
  --headless \
  --screenshot \
  --download \
  --archive \
  --comments 20 \
  --pivot-hashtags 5 \
  --antidetect \
  --aggressive \
  --proxy "http://user:pass@host:port" \
  --out "out/investigation_001"
```

### Risk Analysis (Standalone)

```bash
# Analyze text for risk indicators
python -m crot_dalam.cli analyze "Transfer dulu untuk klaim hadiah undian berhadiah"

# Output:
# Risk Score: 8
# Risk Level: HIGH
# Matches:
#   • transfer dulu (financial_scam, indonesian)
#   • undian berhadiah (financial_scam, indonesian)
#   • hadiah (financial_scam, indonesian)
```

---

## 🛡️ Anti-Detection

CROT DALAM implements comprehensive anti-detection to reduce TikTok bot detection.

### Features

```mermaid
flowchart LR
    subgraph AntiDetect["🛡️ Anti-Detection System"]
        A[Human Delays] --> B[Mouse Curves]
        B --> C[Fingerprint Rotation]
        C --> D[Proxy Rotation]
        D --> E[Session Persistence]
    end

    User --> AntiDetect --> TikTok
```

| Feature                  | Description                              |
| ------------------------ | ---------------------------------------- |
| **Human Delays**         | Log-normal distributed timing (0.5-3.0s) |
| **Bezier Mouse**         | Natural curved mouse movements           |
| **Natural Scroll**       | Variable speed with reading pauses       |
| **Fingerprint Rotation** | Random viewport, timezone, WebGL, UA     |
| **Proxy Pool**           | Health-checked rotating proxies          |
| **Session Cookies**      | Persistent login state                   |

### Configuration

```bash
# Standard anti-detection
python -m crot_dalam.cli search "keyword" --antidetect

# Aggressive mode (slower but stealthier)
python -m crot_dalam.cli search "keyword" --antidetect --aggressive
```

> ⚠️ **Note**: Anti-detection reduces but cannot guarantee 100% evasion. TikTok may still detect automated access.

---

## 🔎 Risk Analysis

### Supported Languages

| Language      | Categories | Example Terms                               |
| ------------- | ---------- | ------------------------------------------- |
| 🇮🇩 Indonesian | 7          | undian berhadiah, transfer dulu, slot gacor |
| 🇺🇸 English    | 5          | seed phrase, crypto double, verify wallet   |
| 🇲🇾 Malay      | 2          | hadiah percuma, bayar dahulu                |
| 🇻🇳 Vietnamese | 2          | trúng thưởng, đầu tư sinh lời               |
| 🇹🇭 Thai       | 2          | ถูกรางวัล, สล็อตเว็บตรง                     |
| 🇵🇭 Filipino   | 2          | libre Regalo, bayad muna                    |

### Risk Categories

- **Financial Scam** — Fake giveaways, lottery scams
- **Investment Fraud** — Crypto scams, fake ROI promises
- **Gambling** — Illegal online gambling promotion
- **Loan Scam** — Predatory lending, fake loans
- **Job Scam** — Work-from-home fraud
- **Contact Urgency** — Pressure to contact "admin"

### Entity Extraction

The tool automatically extracts:

- 📱 Phone numbers (Indonesian, international)
- 💳 Crypto wallets (BTC, ETH, TRX)
- 📧 Email addresses
- 💬 Telegram/WhatsApp links
- 🔗 Shortened URLs (bit.ly, etc.)

---

## 📊 Architecture

### Package Structure

```
CrotDalam/
├── crot_dalam/
│   ├── __init__.py          # Package init, version
│   ├── cli.py               # Typer CLI commands
│   ├── core/
│   │   ├── antidetect.py    # Anti-detection system
│   │   ├── scraper.py       # Playwright scraper
│   │   ├── risk_analyzer.py # Multi-language risk detection
│   │   └── exporters.py     # JSONL/CSV/HTML export
│   ├── gui/
│   │   ├── app.py           # Flask + WebSocket server
│   │   └── static/          # Frontend assets
│   ├── models/
│   │   └── data.py          # Dataclasses & schemas
│   └── utils/
│       ├── config.py        # Configuration management
│       └── helpers.py       # Utility functions
├── assets/
│   └── banner.png           # Project banner
├── requirements.txt
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
└── LICENSE
```

---

## 🧠 How It Works

### High-Level Flow

```mermaid
flowchart TD
    A[🎯 Start Investigation] --> B{Mode Selection}
    B --> |CLI| C[Parse Arguments]
    B --> |GUI| D[Flask Dashboard]

    C --> E[Configure Scan]
    D --> E

    E --> F[🚀 Launch Browser]
    F --> G[Apply Anti-Detection]
    G --> H[Accept Cookies]

    H --> I[Search Keywords]
    I --> J[Scroll & Collect URLs]

    J --> K{For Each Video}
    K --> L[Extract Metadata]
    L --> M[Analyze Risk]
    M --> N[Collect Comments]

    N --> O{Evidence Options}
    O --> |Screenshot| P[📸 Capture]
    O --> |Download| Q[📥 yt-dlp]
    O --> |Archive| R[🗄️ Archive.today]

    P --> S[Next Video]
    Q --> S
    R --> S
    S --> K

    K --> |Done| T[Export Results]
    T --> U[📄 JSONL]
    T --> V[📊 CSV]
    T --> W[🌐 HTML Report]

    W --> X[✅ Complete]
```

### Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant CLI as CLI/GUI
    participant AD as AntiDetect
    participant PW as Playwright
    participant TT as TikTok

    U->>CLI: search "keyword" --mode deep
    CLI->>AD: Initialize anti-detection
    AD->>AD: Generate fingerprint
    CLI->>PW: Launch browser

    loop For each keyword
        PW->>TT: GET /search?q=...
        AD->>PW: Human delay
        AD->>PW: Natural scroll
        PW-->>CLI: Video URLs
    end

    loop For each video
        PW->>TT: GET /video/...
        AD->>PW: Bezier mouse move
        PW-->>CLI: Metadata
        CLI->>CLI: Risk analysis
        opt Evidence
            PW->>PW: Screenshot
            CLI->>CLI: yt-dlp download
        end
    end

    CLI-->>U: Export JSONL, CSV, HTML
```

---

## 📁 Output Files

### Directory Structure

```
out/
├── crot_dalam.jsonl        # Structured JSON Lines
├── crot_dalam.csv          # Flat table for Excel/Sheets
├── crot_dalam.html         # Styled investigation report
├── screenshots/            # Full-page PNGs
│   ├── 7382918273.png
│   └── 8291038271.png
└── videos/                 # Downloaded videos
    ├── 7382918273.mp4
    └── 8291038271.mp4
```

### HTML Report Preview

The HTML report features:

- 🌙 Dark theme with glassmorphism
- 📊 Statistics cards (total, high/medium/low risk)
- 📋 Sortable results table
- 🔗 Clickable video links
- 🏷️ Risk level badges
- 📱 Responsive design

---

## ⚙️ Configuration

### Environment Variables

| Variable          | Description             | Default |
| ----------------- | ----------------------- | ------- |
| `CROT_DEBUG`      | Enable debug mode       | `false` |
| `CROT_HEADLESS`   | Run headless browser    | `true`  |
| `CROT_LOCALE`     | Browser locale          | `en-US` |
| `CROT_LIMIT`      | Default video limit     | `60`    |
| `CROT_ANTIDETECT` | Enable anti-detection   | `true`  |
| `CROT_PROXY_LIST` | Comma-separated proxies | —       |
| `CROT_GUI_PORT`   | GUI server port         | `5000`  |

### Config File

Create `~/.config/crot_dalam/config.json`:

```json
{
  "headless": true,
  "locale": "id-ID",
  "default_limit": 100,
  "antidetect_enabled": true,
  "antidetect_aggressive": false,
  "proxy_list": ["http://proxy1:8080", "http://proxy2:8080"]
}
```

---

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Contribute

```bash
# Fork & clone
git clone https://github.com/Masriyan/CrotDalam.git
cd CrotDalam

# Create branch
git checkout -b feature/my-feature

# Make changes, test, commit
git commit -m "Add my feature"

# Push & create PR
git push origin feature/my-feature
```

### Areas for Contribution

- 🌐 Additional language risk terms
- 🔧 Improved TikTok selectors
- 📊 New export formats
- 🧪 Test coverage
- 📚 Documentation

---

## 🔐 Security & Ethics

See [SECURITY.md](SECURITY.md) for full policy.

> ⚠️ **IMPORTANT**: This tool is for legitimate OSINT research only. Use responsibly and respect:
>
> - TikTok Terms of Service
> - Local laws and regulations
> - Privacy of individuals

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Made with ❤️ by sudo3rs</strong><br>
  <sub>For the security research community</sub>
</p>
