#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Export Module
Multi-format exporters for investigation results.
"""
from __future__ import annotations

import csv
import json
import html as html_lib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import asdict

from crot_dalam.models.data import VideoRecord, ScanResult, UserProfile


class Exporter:
    """Multi-format exporter for CROT DALAM results."""
    
    def __init__(self, base_path: str = "out/crot_dalam"):
        self.base_path = Path(base_path).resolve()
        # Ensure output directory exists
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[Exporter] Output base: {self.base_path}")
    
    def export_all(
        self,
        records: List[VideoRecord],
        keywords: List[str],
        mode: str,
    ) -> Dict[str, Path]:
        """Export to all formats and return paths."""
        paths = {}
        paths["jsonl"] = self.export_jsonl(records)
        paths["csv"] = self.export_csv(records)
        paths["html"] = self.export_html(records, keywords, mode)
        return paths
    
    def export_jsonl(self, records: List[VideoRecord]) -> Path:
        """Export to JSONL format."""
        path = self.base_path.with_suffix(".jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
        return path
    
    def export_csv(self, records: List[VideoRecord]) -> Path:
        """Export to CSV format."""
        path = self.base_path.with_suffix(".csv")
        if not records:
            path.touch()
            return path
        
        fieldnames = list(VideoRecord.__dataclass_fields__.keys())
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                writer.writerow(r.to_row())
        return path
    
    def export_json(self, records: List[VideoRecord]) -> Path:
        """Export to pretty JSON format."""
        path = self.base_path.with_suffix(".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in records], f, ensure_ascii=False, indent=2)
        return path
    
    def export_html(
        self,
        records: List[VideoRecord],
        keywords: List[str],
        mode: str,
    ) -> Path:
        """Export to styled HTML report."""
        path = self.base_path.with_suffix(".html")
        try:
            html_content = self._generate_html_report(records, keywords, mode)
            with open(path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"[Exporter] HTML report saved: {path}")
        except Exception as e:
            print(f"[Exporter] HTML export error: {e}")
            # Create minimal report on failure
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"<html><body><h1>CROT DALAM Report</h1><p>Error: {e}</p></body></html>")
        return path
    
    def _generate_html_report(
        self,
        records: List[VideoRecord],
        keywords: List[str],
        mode: str,
    ) -> str:
        """Generate complete HTML report."""
        
        # Sort by risk desc, then likes desc
        records_sorted = sorted(
            records,
            key=lambda r: (-(r.risk_score or 0), -(r.like_count or 0))
        )
        
        # Calculate statistics
        total = len(records)
        high_risk = sum(1 for r in records if r.risk_score >= 5)
        medium_risk = sum(1 for r in records if 2 <= r.risk_score < 5)
        low_risk = sum(1 for r in records if 0 < r.risk_score < 2)
        
        # Generate table rows
        rows = []
        for r in records_sorted:
            risk_class = self._get_risk_class(r.risk_score)
            rows.append(self._generate_row(r, risk_class))
        
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CROT DALAM — Investigation Report</title>
    {self._get_html_styles()}
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="logo">
                <h1>🔍 CROT DALAM</h1>
                <p class="subtitle">TikTok OSINT Investigation Report</p>
            </div>
            <div class="report-meta">
                <span class="badge mode-badge">{html_lib.escape(mode.upper())}</span>
                <span class="timestamp">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
            </div>
        </header>
        
        <section class="summary-section">
            <h2>📊 Investigation Summary</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{total}</div>
                    <div class="stat-label">Total Videos</div>
                </div>
                <div class="stat-card high-risk">
                    <div class="stat-value">{high_risk}</div>
                    <div class="stat-label">High Risk</div>
                </div>
                <div class="stat-card medium-risk">
                    <div class="stat-value">{medium_risk}</div>
                    <div class="stat-label">Medium Risk</div>
                </div>
                <div class="stat-card low-risk">
                    <div class="stat-value">{low_risk}</div>
                    <div class="stat-label">Low Risk</div>
                </div>
            </div>
            <div class="keywords-section">
                <strong>Keywords:</strong>
                {' '.join(f'<span class="keyword-tag">{html_lib.escape(k)}</span>' for k in keywords)}
            </div>
        </section>
        
        <section class="results-section">
            <h2>📋 Investigation Results</h2>
            <div class="table-container">
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>Video / User</th>
                            <th>Description</th>
                            <th>Extracted URLs</th>
                            <th>Risk</th>
                            <th>Engagement</th>
                            <th>Hashtags</th>
                            <th>Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
        </section>
        
        <footer class="footer">
            <p>Generated by <strong>CROT DALAM v2.0</strong> — TikTok OSINT Tool</p>
            <p class="disclaimer">⚠️ For research and security awareness only. Respect platform terms and local laws.</p>
        </footer>
    </div>
    {self._get_html_scripts()}
</body>
</html>"""
    
    def _get_risk_class(self, score: int) -> str:
        """Get CSS class for risk level."""
        if score >= 5:
            return "risk-high"
        elif score >= 2:
            return "risk-medium"
        elif score > 0:
            return "risk-low"
        return ""
    
    def _generate_row(self, r: VideoRecord, risk_class: str) -> str:
        """Generate a table row for a video record."""
        urls_html = self._format_urls(r.extracted_urls)
        
        engagement = f"""
            <div class="engagement">
                <span title="Likes">❤️ {self._format_number(r.like_count)}</span>
                <span title="Comments">💬 {self._format_number(r.comment_count)}</span>
                <span title="Shares">🔗 {self._format_number(r.share_count)}</span>
                <span title="Views">👁️ {self._format_number(r.view_count)}</span>
            </div>
        """
        
        return f"""
        <tr class="{risk_class}">
            <td>
                <a href="{html_lib.escape(r.url)}" target="_blank" rel="noopener" class="video-link">
                    {html_lib.escape(r.video_id or '—')}
                </a>
                <br>
                <span class="username">@{html_lib.escape(r.username or '')}</span>
            </td>
            <td class="description-cell">{html_lib.escape(r.description or '')[:200]}{'...' if r.description and len(r.description) > 200 else ''}</td>
            <td>{urls_html}</td>
            <td class="risk-cell">
                <span class="risk-score">{r.risk_score}</span>
                <span class="risk-level">{r.risk_level}</span>
                <div class="risk-matches">{html_lib.escape(', '.join(r.risk_matches[:3]))}</div>
            </td>
            <td>{engagement}</td>
            <td class="hashtags-cell">{html_lib.escape(', '.join(r.hashtags[:5]))}</td>
            <td class="date-cell">{html_lib.escape(r.upload_date or '')}</td>
        </tr>
        """
    
    def _format_urls(self, urls: List[str]) -> str:
        """Format extracted URLs as clickable links."""
        if not urls:
            return '<span class="muted">—</span>'
        
        links = []
        for url in urls[:3]:  # Limit to 3 URLs
            short = url[:40] + "..." if len(url) > 40 else url
            links.append(
                f'<a href="{html_lib.escape(url)}" target="_blank" rel="noopener" class="extracted-url">'
                f'{html_lib.escape(short)}</a>'
            )
        
        result = '<br>'.join(links)
        if len(urls) > 3:
            result += f'<br><span class="muted">+{len(urls) - 3} more</span>'
        return result
    
    def _format_number(self, n: Optional[int]) -> str:
        """Format number with K/M suffix."""
        if n is None:
            return "—"
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        elif n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)
    
    def _get_html_styles(self) -> str:
        """Get CSS styles for HTML report."""
        return """
<style>
:root {
    --bg-primary: #0f0f23;
    --bg-secondary: #1a1a2e;
    --bg-tertiary: #16213e;
    --text-primary: #e4e4e7;
    --text-secondary: #a1a1aa;
    --accent-primary: #6366f1;
    --accent-secondary: #8b5cf6;
    --risk-high: #ef4444;
    --risk-medium: #f59e0b;
    --risk-low: #22c55e;
    --border-color: #27272a;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
    color: var(--text-primary);
    min-height: 100vh;
    line-height: 1.6;
}

.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem;
}

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--border-color);
}

.logo h1 {
    font-size: 2rem;
    background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.subtitle {
    color: var(--text-secondary);
    font-size: 0.9rem;
}

.report-meta {
    display: flex;
    align-items: center;
    gap: 1rem;
}

.badge {
    padding: 0.5rem 1rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
}

.mode-badge {
    background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
}

.timestamp {
    color: var(--text-secondary);
    font-size: 0.875rem;
}

.summary-section, .results-section {
    background: var(--bg-secondary);
    border-radius: 1rem;
    padding: 1.5rem;
    margin-bottom: 2rem;
    border: 1px solid var(--border-color);
}

.summary-section h2, .results-section h2 {
    margin-bottom: 1rem;
    font-size: 1.25rem;
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.stat-card {
    background: var(--bg-tertiary);
    padding: 1.5rem;
    border-radius: 0.75rem;
    text-align: center;
    border: 1px solid var(--border-color);
    transition: transform 0.2s;
}

.stat-card:hover {
    transform: translateY(-2px);
}

.stat-value {
    font-size: 2rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
}

.stat-label {
    color: var(--text-secondary);
    font-size: 0.875rem;
}

.stat-card.high-risk .stat-value { color: var(--risk-high); }
.stat-card.medium-risk .stat-value { color: var(--risk-medium); }
.stat-card.low-risk .stat-value { color: var(--risk-low); }

.keywords-section {
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
}

.keyword-tag {
    display: inline-block;
    background: var(--bg-tertiary);
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.875rem;
    margin: 0.25rem;
    border: 1px solid var(--accent-primary);
}

.table-container {
    overflow-x: auto;
}

.results-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}

.results-table th, .results-table td {
    padding: 0.75rem 1rem;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
    vertical-align: top;
}

.results-table th {
    background: var(--bg-tertiary);
    font-weight: 600;
    color: var(--text-secondary);
    position: sticky;
    top: 0;
}

.results-table tr:hover {
    background: rgba(99, 102, 241, 0.1);
}

.results-table tr.risk-high {
    background: rgba(239, 68, 68, 0.1);
    border-left: 3px solid var(--risk-high);
}

.results-table tr.risk-medium {
    background: rgba(245, 158, 11, 0.1);
    border-left: 3px solid var(--risk-medium);
}

.results-table tr.risk-low {
    border-left: 3px solid var(--risk-low);
}

.video-link {
    color: var(--accent-primary);
    text-decoration: none;
    font-weight: 500;
}

.video-link:hover {
    text-decoration: underline;
}

.username {
    color: var(--text-secondary);
    font-size: 0.8rem;
}

.description-cell {
    max-width: 300px;
    word-wrap: break-word;
}

.risk-cell {
    text-align: center;
}

.risk-score {
    display: inline-block;
    width: 2rem;
    height: 2rem;
    line-height: 2rem;
    border-radius: 50%;
    font-weight: 700;
    background: var(--bg-tertiary);
}

.risk-high .risk-score { background: var(--risk-high); }
.risk-medium .risk-score { background: var(--risk-medium); color: #000; }

.risk-level {
    display: block;
    font-size: 0.7rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
}

.risk-matches {
    font-size: 0.7rem;
    color: var(--risk-high);
    margin-top: 0.25rem;
}

.engagement {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.8rem;
}

.engagement span {
    white-space: nowrap;
}

.extracted-url {
    color: var(--accent-secondary);
    text-decoration: none;
    font-size: 0.8rem;
    word-break: break-all;
}

.extracted-url:hover {
    text-decoration: underline;
}

.muted {
    color: var(--text-secondary);
    opacity: 0.7;
}

.hashtags-cell {
    max-width: 150px;
    font-size: 0.8rem;
    color: var(--accent-primary);
}

.date-cell {
    white-space: nowrap;
    font-size: 0.8rem;
}

.footer {
    text-align: center;
    padding: 2rem;
    color: var(--text-secondary);
    font-size: 0.875rem;
}

.disclaimer {
    margin-top: 0.5rem;
    font-size: 0.75rem;
    opacity: 0.7;
}

@media (max-width: 768px) {
    .container { padding: 1rem; }
    .header { flex-direction: column; gap: 1rem; text-align: center; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
"""
    
    def _get_html_scripts(self) -> str:
        """Get JavaScript for interactive features."""
        return """
<script>
// Add sorting functionality
document.querySelectorAll('.results-table th').forEach((th, index) => {
    th.style.cursor = 'pointer';
    th.addEventListener('click', () => sortTable(index));
});

function sortTable(column) {
    const table = document.querySelector('.results-table');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    const isNumeric = column === 3; // Risk column
    
    rows.sort((a, b) => {
        const aVal = a.cells[column].textContent.trim();
        const bVal = b.cells[column].textContent.trim();
        
        if (isNumeric) {
            return parseInt(bVal) - parseInt(aVal);
        }
        return aVal.localeCompare(bVal);
    });
    
    rows.forEach(row => tbody.appendChild(row));
}
</script>
"""
    
    def export_summary(self, result: ScanResult) -> Path:
        """Export scan summary."""
        path = self.base_path.with_name(f"{self.base_path.name}_summary.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        return path


def export_network_graph(graph: "NetworkGraph", path: Path) -> None:
    """Export network graph to JSON for visualization."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(graph.to_dict(), f, ensure_ascii=False, indent=2)
