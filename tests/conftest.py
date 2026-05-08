"""
CROT DALAM - Test Configuration
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test configuration
pytest_plugins = ["tests.fixtures.mocks"]

# Default test markers
markers = [
    "unit: Unit tests (fast, no external dependencies)",
    "integration: Integration tests (require network access)",
    "slow: Slow running tests",
    "requires_playwright: Tests requiring Playwright",
]
