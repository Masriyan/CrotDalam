# 🎯 CROT DALAM v4.1 - 30-Day Sprint Plan

## Prioritas: Fondasi & Testing (Week 1-4)

---

## 📋 Week 1-2: CI/CD & Logging Infrastructure

### Task 1.1: Setup GitHub Actions CI/CD
**File**: `.github/workflows/ci.yml`

```yaml
name: CROT Dalam CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Lint with flake8
      run: |
        flake8 crot_dalam --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 crot_dalam --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
    
    - name: Test with pytest
      run: |
        pytest tests/ --cov=crot_dalam --cov-report=xml --cov-report=html
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        files: ./coverage.xml
        flags: unittests
        name: codecov-umbrella

  security-scan:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Run Bandit security scan
      run: |
        pip install bandit
        bandit -r crot_dalam/ -f json -o bandit-report.json
    
    - name: Run Safety check
      run: |
        pip install safety
        safety check -r requirements.txt --json > safety-report.json

  build-docker:
    needs: [test, security-scan]
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    
    - name: Login to Docker Hub
      uses: docker/login-action@v3
      with:
        username: ${{ secrets.DOCKERHUB_USERNAME }}
        password: ${{ secrets.DOCKERHUB_TOKEN }}
    
    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: |
          crotdalam/crot-dalam:latest
          crotdalam/crot-dalam:${{ github.sha }}
```

### Task 1.2: Implement Structured Logging
**File**: `crot_dalam/core/logger.py`

```python
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
from pathlib import Path

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False, default=str)

def setup_logging(
    log_level: str = "INFO",
    log_file: str = "logs/crot_dalam.log",
    console_output: bool = True,
    json_format: bool = True
) -> logging.Logger:
    """
    Setup structured logging for CROT DALAM
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        console_output: Enable console output
        json_format: Use JSON format for logs
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("crot_dalam")
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Create logs directory
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # File handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

# Usage example in modules:
# from crot_dalam.core.logger import get_logger
# logger = get_logger(__name__)
# logger.info("Scan started", extra={"extra_fields": {"profile_id": "123"}})

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module"""
    return logging.getLogger(f"crot_dalam.{name}")
```

### Task 1.3: Pytest Fixtures & Mocks
**File**: `tests/conftest.py`

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Generator, Dict, Any
import asyncio

# Sample test data fixtures
@pytest.fixture
def sample_profile() -> Dict[str, Any]:
    return {
        "user_id": "123456789",
        "username": "test_user",
        "nickname": "Test User",
        "follower_count": 1000,
        "following_count": 500,
        "video_count": 50,
        "verified": False,
        "bio": "Test bio",
        "avatar_url": "https://example.com/avatar.jpg"
    }

@pytest.fixture
def sample_video() -> Dict[str, Any]:
    return {
        "video_id": "987654321",
        "description": "Test video #fyp",
        "create_time": 1234567890,
        "duration": 15,
        "play_count": 5000,
        "like_count": 500,
        "comment_count": 50,
        "share_count": 25,
        "hashtags": ["fyp", "test"],
        "music": {
            "title": "Test Song",
            "author": "Test Artist"
        }
    }

@pytest.fixture
def mock_playwright_page():
    """Mock Playwright page object"""
    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.click = AsyncMock()
    page.type = AsyncMock()
    page.evaluate = AsyncMock(return_value={})
    page.screenshot = AsyncMock()
    return page

@pytest.fixture
def mock_browser_context():
    """Mock Browser context"""
    context = MagicMock()
    context.new_page = AsyncMock(return_value=mock_playwright_page())
    context.close = AsyncMock()
    return context

@pytest.fixture
def mock_browser():
    """Mock Browser"""
    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=mock_browser_context())
    browser.close = AsyncMock()
    return browser

@pytest.fixture
def mock_scraper(mock_browser):
    """Mock TikTokScraper with dependencies"""
    with patch('crot_dalam.scraper.TikTokScraper') as mock:
        instance = mock.return_value
        instance.browser = mock_browser
        instance.scrape_profile = AsyncMock(return_value=sample_profile())
        instance.scrape_video = AsyncMock(return_value=sample_video())
        yield instance

# Async test helper
@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Risk analysis fixtures
@pytest.fixture
def sample_risk_result() -> Dict[str, Any]:
    return {
        "risk_score": 75,
        "risk_level": "HIGH",
        "categories": {
            "scam": 0.8,
            "hate_speech": 0.1,
            "misinformation": 0.6,
            "adult_content": 0.0
        },
        "flags": ["suspicious_links", "aggressive_promotion"],
        "confidence": 0.85
    }

# Graph intelligence fixtures
@pytest.fixture
def sample_network_data() -> Dict[str, Any]:
    return {
        "nodes": [
            {"id": "user1", "type": "account", "influence_score": 0.9},
            {"id": "user2", "type": "account", "influence_score": 0.7},
            {"id": "user3", "type": "account", "influence_score": 0.3}
        ],
        "edges": [
            {"source": "user1", "target": "user2", "type": "follows"},
            {"source": "user2", "target": "user3", "type": "follows"}
        ]
    }
```

### Task 1.4: Database Schema Design
**File**: `crot_dalam/database/schema.sql`

```sql
-- CROT DALAM Database Schema
-- Version: 4.1

-- Profiles table
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    nickname TEXT,
    follower_count INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    video_count INTEGER DEFAULT 0,
    verified BOOLEAN DEFAULT FALSE,
    bio TEXT,
    avatar_url TEXT,
    risk_score REAL,
    risk_level TEXT,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Videos table
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT UNIQUE NOT NULL,
    profile_id TEXT NOT NULL,
    description TEXT,
    create_time INTEGER,
    duration INTEGER,
    play_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    risk_score REAL,
    risk_level TEXT,
    FOREIGN KEY (profile_id) REFERENCES profiles(user_id),
    INDEX idx_profile_id (profile_id),
    INDEX idx_create_time (create_time)
);

-- Hashtags table
CREATE TABLE IF NOT EXISTS hashtags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    usage_count INTEGER DEFAULT 0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Video-Hashtag relationship
CREATE TABLE IF NOT EXISTS video_hashtags (
    video_id TEXT NOT NULL,
    hashtag_id INTEGER NOT NULL,
    PRIMARY KEY (video_id, hashtag_id),
    FOREIGN KEY (video_id) REFERENCES videos(video_id),
    FOREIGN KEY (hashtag_id) REFERENCES hashtags(id)
);

-- Risk assessments table
CREATE TABLE IF NOT EXISTS risk_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL, -- 'profile' or 'video'
    entity_id TEXT NOT NULL,
    risk_score REAL NOT NULL,
    risk_level TEXT NOT NULL,
    categories TEXT, -- JSON format
    flags TEXT, -- JSON format
    confidence REAL,
    assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_id) REFERENCES profiles(user_id) ON DELETE CASCADE,
    INDEX idx_entity (entity_type, entity_id)
);

-- Scan sessions table
CREATE TABLE IF NOT EXISTS scan_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    query_type TEXT NOT NULL,
    query_value TEXT NOT NULL,
    total_profiles INTEGER DEFAULT 0,
    total_videos INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running', -- running, completed, failed
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Graph relationships table
CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL, -- follows, mentions, collaborates
    strength REAL DEFAULT 1.0,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id, relationship_type)
);

-- Trend data table
CREATE TABLE IF NOT EXISTS trends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hashtag TEXT NOT NULL,
    trend_score REAL NOT NULL,
    velocity REAL, -- rate of change
    predicted_viral BOOLEAN DEFAULT FALSE,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_hashtag (hashtag),
    INDEX idx_recorded_at (recorded_at)
);

-- Audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    user_id TEXT,
    entity_type TEXT,
    entity_id TEXT,
    details TEXT, -- JSON format
    ip_address TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_profiles_username ON profiles(username);
CREATE INDEX IF NOT EXISTS idx_profiles_risk ON profiles(risk_score);
CREATE INDEX IF NOT EXISTS idx_videos_risk ON videos(risk_score);
CREATE INDEX IF NOT EXISTS idx_trends_score ON trends(trend_score DESC);
```

---

## 📋 Week 3-4: Testing & Docker

### Task 2.1: Unit Tests Structure
**Directory**: `tests/unit/`

```
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_scraper.py
│   ├── test_risk_analyzer.py
│   ├── test_graph_intelligence.py
│   ├── test_trend_prediction.py
│   ├── test_cross_platform.py
│   └── test_geospatial.py
├── integration/
│   ├── test_end_to_end.py
│   └── test_database.py
└── load/
    └── test_concurrent_scans.py
```

### Task 2.2: Example Test File
**File**: `tests/unit/test_graph_intelligence.py`

```python
import pytest
from crot_dalam.modules.graph_intelligence import GraphIntelligence

class TestGraphIntelligence:
    
    def test_add_profile(self, sample_profile):
        """Test adding a profile to the graph"""
        gi = GraphIntelligence()
        gi.add_profile(sample_profile)
        
        assert len(gi.nodes) == 1
        assert sample_profile['user_id'] in gi.nodes
    
    def test_resolve_entities(self, sample_profile):
        """Test entity resolution"""
        gi = GraphIntelligence()
        gi.add_profile(sample_profile)
        
        # Add duplicate with slight variation
        duplicate = sample_profile.copy()
        duplicate['username'] = sample_profile['username'].upper()
        gi.add_profile(duplicate)
        
        entities = gi.resolve_entities(threshold=0.9)
        
        # Should resolve to single entity
        assert len(entities) == 1
    
    def test_calculate_influence_scores(self, sample_network_data):
        """Test influence score calculation"""
        gi = GraphIntelligence()
        
        # Load network data
        for node in sample_network_data['nodes']:
            gi.add_node(node['id'], node)
        
        for edge in sample_network_data['edges']:
            gi.add_edge(edge['source'], edge['target'], edge['type'])
        
        scores = gi.calculate_influence_scores()
        
        assert 'user1' in scores
        assert scores['user1'] > scores['user3']  # user1 should have higher influence
    
    def test_detect_bot_network(self):
        """Test bot network detection"""
        gi = GraphIntelligence()
        
        # Simulate bot network pattern
        # ... test implementation
        
        bots = gi.detect_bot_network()
        assert isinstance(bots, list)
```

### Task 2.3: Dockerfile
**File**: `Dockerfile`

```dockerfile
# CROT DALAM Production Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies
RUN playwright install-deps chromium

# Set work directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium

# Copy application code
COPY crot_dalam/ ./crot_dalam/
COPY tests/ ./tests/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose GUI port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

# Default command
CMD ["python", "-m", "crot_dalam.gui.app"]
```

### Task 2.4: Docker Compose
**File**: `docker-compose.yml`

```yaml
version: '3.8'

services:
  crot-dalam:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - LOG_LEVEL=INFO
      - DATABASE_URL=sqlite:///data/crot_dalam.db
      - SECRET_KEY=${SECRET_KEY:-change-me-in-production}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:5000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Optional: Redis for distributed scanning
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  # Optional: PostgreSQL for production
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: crot_dalam
      POSTGRES_USER: crot_dalam
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

volumes:
  redis_data:
  postgres_data:
```

---

## ✅ Definition of Done (DoD)

Setiap task dianggap selesai jika:
- [ ] Kode ditulis dan berfungsi
- [ ] Unit tests dibuat (coverage >80%)
- [ ] Integration tests lulus
- [ ] Dokumentasi diperbarui
- [ ] Code review dilakukan
- [ ] Tidak ada security vulnerabilities (Bandit clean)
- [ ] Performance benchmarks acceptable

---

## 📊 Success Metrics untuk Sprint Ini

| Metric | Target | Current |
|--------|--------|---------|
| Test Coverage | >80% | 0% |
| CI/CD Pipeline | ✅ Working | ❌ Not exists |
| Docker Build | ✅ Working | ❌ Not exists |
| Structured Logging | ✅ Implemented | ❌ Not exists |
| Database Layer | ✅ Schema ready | ❌ Not exists |
| Critical Bugs | 0 | TBD |

---

**Next Review**: End of Week 2
**Sprint Goal**: Production-ready foundation with testing infrastructure
