#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Flask Web GUI Application
Modern dashboard interface for TikTok OSINT.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, render_template_string, request, jsonify, send_from_directory
from flask_cors import CORS

# Try importing socketio for real-time updates
try:
    from flask_socketio import SocketIO, emit
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    SocketIO = None

from crot_dalam.models.data import ScanConfig, ScanResult, InvestigationMode, ScanStatus
from crot_dalam.core.scraper import TikTokScraper
from crot_dalam.core.exporters import Exporter
from crot_dalam.utils.config import load_config, Config


# Global state for scan management
_active_scans: Dict[str, Dict[str, Any]] = {}
_scan_results: Dict[str, ScanResult] = {}


def create_app(config: Optional[Config] = None) -> Flask:
    """Create Flask application."""
    app = Flask(__name__)
    
    config = config or load_config()
    app.config["SECRET_KEY"] = config.gui_secret_key
    app.config["CROT_CONFIG"] = config
    
    CORS(app)
    
    # Initialize SocketIO if available
    socketio = None
    if SOCKETIO_AVAILABLE:
        socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
        app.config["SOCKETIO"] = socketio
    
    # Register routes
    register_routes(app)
    
    if socketio:
        register_socketio_events(socketio)
    
    return app


def register_routes(app: Flask) -> None:
    """Register all routes."""
    
    @app.route("/")
    def index():
        """Serve main dashboard."""
        return render_template_string(get_dashboard_html())
    
    @app.route("/api/scan/start", methods=["POST"])
    def start_scan():
        """Start a new scan."""
        data = request.get_json() or {}
        
        # Parse keywords
        keywords = data.get("keywords", "")
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        
        if not keywords:
            return jsonify({"error": "No keywords provided"}), 400
        
        # Create scan config
        scan_config = ScanConfig(
            keywords=keywords,
            mode=InvestigationMode(data.get("mode", "quick")),
            limit=int(data.get("limit", 60)),
            headless=data.get("headless", True),
            locale=data.get("locale", "en-US"),
            screenshot=data.get("screenshot", False),
            download=data.get("download", False),
            web_archive=data.get("web_archive", False),
            comments_limit=int(data.get("comments", 0)),
            pivot_hashtags=int(data.get("pivot_hashtags", 0)),
            antidetect_enabled=data.get("antidetect", True),
            antidetect_aggressive=data.get("antidetect_aggressive", False),
            output_base=f"out/scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )
        
        # Apply mode presets
        scan_config.apply_mode_presets()
        
        # Generate scan ID
        scan_id = str(uuid.uuid4())[:8]
        
        # Store scan info
        _active_scans[scan_id] = {
            "id": scan_id,
            "status": "starting",
            "progress": 0,
            "total": 0,
            "config": scan_config,
            "started_at": datetime.now().isoformat(),
        }
        
        # Start scan in background thread
        thread = threading.Thread(
            target=run_scan_background,
            args=(scan_id, scan_config, app),
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            "scan_id": scan_id,
            "status": "started",
            "keywords": keywords,
            "mode": scan_config.mode.value,
        })
    
    @app.route("/api/scan/<scan_id>/status")
    def get_scan_status(scan_id: str):
        """Get scan status."""
        if scan_id in _active_scans:
            return jsonify(_active_scans[scan_id])
        elif scan_id in _scan_results:
            result = _scan_results[scan_id]
            return jsonify({
                "id": scan_id,
                "status": result.status.value,
                "total_videos": result.total_videos,
                "high_risk_count": result.high_risk_count,
                "duration_seconds": result.duration_seconds,
            })
        return jsonify({"error": "Scan not found"}), 404
    
    @app.route("/api/scan/<scan_id>/results")
    def get_scan_results(scan_id: str):
        """Get scan results."""
        if scan_id not in _scan_results:
            return jsonify({"error": "Results not found"}), 404
        
        result = _scan_results[scan_id]
        return jsonify({
            "scan_id": scan_id,
            "status": result.status.value,
            "total_videos": result.total_videos,
            "high_risk_count": result.high_risk_count,
            "medium_risk_count": result.medium_risk_count,
            "duration_seconds": result.duration_seconds,
            "videos": [v.to_dict() for v in result.videos[:100]],  # Limit for performance
            "output_files": {
                "jsonl": result.output_jsonl,
                "csv": result.output_csv,
                "html": result.output_html,
            },
        })
    
    @app.route("/api/scan/<scan_id>/stop", methods=["POST"])
    def stop_scan(scan_id: str):
        """Stop a running scan."""
        if scan_id in _active_scans:
            _active_scans[scan_id]["status"] = "stopping"
            return jsonify({"message": "Stop requested"})
        return jsonify({"error": "Scan not found"}), 404
    
    @app.route("/api/scans")
    def list_scans():
        """List all scans."""
        scans = []
        
        for scan_id, info in _active_scans.items():
            scans.append({
                "id": scan_id,
                "status": info.get("status"),
                "started_at": info.get("started_at"),
            })
        
        for scan_id, result in _scan_results.items():
            if scan_id not in _active_scans:
                scans.append({
                    "id": scan_id,
                    "status": result.status.value,
                    "total_videos": result.total_videos,
                    "high_risk_count": result.high_risk_count,
                })
        
        return jsonify(scans)
    
    @app.route("/api/config")
    def get_config():
        """Get current configuration."""
        config = app.config.get("CROT_CONFIG", Config())
        return jsonify({
            "version": config.version,
            "default_mode": config.default_mode,
            "default_limit": config.default_limit,
            "antidetect_enabled": config.antidetect_enabled,
        })
    
    @app.route("/api/download/<path:filename>")
    def download_file(filename: str):
        """Download output file."""
        directory = Path("out")
        return send_from_directory(directory, filename, as_attachment=True)


def register_socketio_events(socketio) -> None:
    """Register SocketIO events."""
    
    @socketio.on("connect")
    def handle_connect():
        emit("connected", {"message": "Connected to CROT DALAM"})
    
    @socketio.on("subscribe_scan")
    def handle_subscribe(data):
        scan_id = data.get("scan_id")
        if scan_id:
            emit("subscribed", {"scan_id": scan_id})


def run_scan_background(scan_id: str, config: ScanConfig, app: Flask) -> None:
    """Run scan in background thread."""
    
    def progress_callback(stage: str, current: int, total: int):
        _active_scans[scan_id]["status"] = stage
        _active_scans[scan_id]["progress"] = current
        _active_scans[scan_id]["total"] = total
        
        # Emit via socketio if available
        if SOCKETIO_AVAILABLE and "SOCKETIO" in app.config:
            socketio = app.config["SOCKETIO"]
            socketio.emit("scan_progress", {
                "scan_id": scan_id,
                "stage": stage,
                "progress": current,
                "total": total,
            })
    
    try:
        _active_scans[scan_id]["status"] = "running"
        
        scraper = TikTokScraper(
            config=config,
            progress_callback=progress_callback,
        )
        
        result = scraper.run_scan()
        
        _scan_results[scan_id] = result
        _active_scans[scan_id]["status"] = result.status.value
        
        # Emit completion
        if SOCKETIO_AVAILABLE and "SOCKETIO" in app.config:
            socketio = app.config["SOCKETIO"]
            socketio.emit("scan_complete", {
                "scan_id": scan_id,
                "status": result.status.value,
                "total_videos": result.total_videos,
                "high_risk_count": result.high_risk_count,
            })
        
    except Exception as e:
        _active_scans[scan_id]["status"] = "failed"
        _active_scans[scan_id]["error"] = str(e)
        
        if SOCKETIO_AVAILABLE and "SOCKETIO" in app.config:
            socketio = app.config["SOCKETIO"]
            socketio.emit("scan_error", {
                "scan_id": scan_id,
                "error": str(e),
            })
    
    finally:
        # Clean up active scan after delay
        if scan_id in _active_scans:
            del _active_scans[scan_id]


def get_dashboard_html() -> str:
    """Get the main dashboard HTML."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CROT DALAM — TikTok OSINT Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0a1a;
            --bg-secondary: #12122a;
            --bg-tertiary: #1a1a3a;
            --bg-card: rgba(26, 26, 58, 0.8);
            --text-primary: #e4e4f0;
            --text-secondary: #9999bb;
            --accent-primary: #6366f1;
            --accent-secondary: #8b5cf6;
            --accent-gradient: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
            --border-color: rgba(99, 102, 241, 0.2);
            --glass-bg: rgba(26, 26, 58, 0.6);
            --glass-border: rgba(99, 102, 241, 0.3);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Animated background */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(circle at 20% 20%, rgba(99, 102, 241, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(139, 92, 246, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(168, 85, 247, 0.05) 0%, transparent 70%);
            pointer-events: none;
            z-index: -1;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }

        /* Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding: 1.5rem 2rem;
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 1rem;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .logo-icon {
            width: 48px;
            height: 48px;
            background: var(--accent-gradient);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
        }

        .logo-text h1 {
            font-size: 1.5rem;
            font-weight: 700;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .logo-text p {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        .header-actions {
            display: flex;
            gap: 1rem;
        }

        /* Glass Card */
        .glass-card {
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }

        .card-title {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--text-primary);
        }

        /* Form Styles */
        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        .form-group.full-width {
            grid-column: 1 / -1;
        }

        label {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-secondary);
        }

        input, select, textarea {
            padding: 0.75rem 1rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            color: var(--text-primary);
            font-size: 0.875rem;
            transition: all 0.2s;
        }

        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }

        /* Checkbox */
        .checkbox-group {
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .checkbox-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            cursor: pointer;
        }

        .checkbox-item input[type="checkbox"] {
            width: 18px;
            height: 18px;
            accent-color: var(--accent-primary);
        }

        /* Buttons */
        .btn {
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            font-weight: 600;
            font-size: 0.875rem;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }

        .btn-primary {
            background: var(--accent-gradient);
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(99, 102, 241, 0.3);
        }

        .btn-secondary {
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }

        .btn-secondary:hover {
            border-color: var(--accent-primary);
        }

        .btn-danger {
            background: var(--danger);
            color: white;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }

        .stat-card {
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 1rem;
            padding: 1.5rem;
            text-align: center;
            transition: transform 0.2s;
        }

        .stat-card:hover {
            transform: translateY(-4px);
        }

        .stat-icon {
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .stat-label {
            font-size: 0.875rem;
            color: var(--text-secondary);
        }

        .stat-card.danger .stat-value {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            -webkit-background-clip: text;
        }

        .stat-card.warning .stat-value {
            background: linear-gradient(135deg, #f59e0b, #d97706);
            -webkit-background-clip: text;
        }

        .stat-card.success .stat-value {
            background: linear-gradient(135deg, #22c55e, #16a34a);
            -webkit-background-clip: text;
        }

        /* Progress Bar */
        .progress-container {
            margin: 1rem 0;
        }

        .progress-bar {
            height: 8px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: var(--accent-gradient);
            border-radius: 4px;
            transition: width 0.3s ease;
        }

        .progress-text {
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-top: 0.5rem;
        }

        /* Results Table */
        .table-container {
            overflow-x: auto;
            border-radius: 0.5rem;
        }

        .results-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }

        .results-table th,
        .results-table td {
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
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

        .risk-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .risk-high {
            background: rgba(239, 68, 68, 0.2);
            color: var(--danger);
        }

        .risk-medium {
            background: rgba(245, 158, 11, 0.2);
            color: var(--warning);
        }

        .risk-low {
            background: rgba(34, 197, 94, 0.2);
            color: var(--success);
        }

        /* Status Badge */
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
        }

        .status-running {
            background: rgba(99, 102, 241, 0.2);
            color: var(--accent-primary);
        }

        .status-completed {
            background: rgba(34, 197, 94, 0.2);
            color: var(--success);
        }

        .status-failed {
            background: rgba(239, 68, 68, 0.2);
            color: var(--danger);
        }

        /* Pulse Animation */
        .pulse {
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* Link Styles */
        a {
            color: var(--accent-primary);
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }

        /* Hidden */
        .hidden {
            display: none !important;
        }

        /* Responsive */
        @media (max-width: 768px) {
            .container { padding: 1rem; }
            .header { flex-direction: column; gap: 1rem; text-align: center; }
            .form-grid { grid-template-columns: 1fr; }
        }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg-tertiary);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--accent-primary);
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header class="header">
            <div class="logo">
                <div class="logo-icon">🔍</div>
                <div class="logo-text">
                    <h1>CROT DALAM</h1>
                    <p>TikTok OSINT Dashboard v2.0</p>
                </div>
            </div>
            <div class="header-actions">
                <span id="connectionStatus" class="status-badge status-running">
                    <span class="pulse">●</span> Connecting...
                </span>
            </div>
        </header>

        <!-- Scan Form -->
        <div class="glass-card">
            <div class="card-title">
                <span>🚀</span> New Investigation
            </div>
            <form id="scanForm">
                <div class="form-grid">
                    <div class="form-group full-width">
                        <label for="keywords">Keywords (comma-separated)</label>
                        <input type="text" id="keywords" placeholder="e.g., undian berhadiah, giveaway, crypto bonus" required>
                    </div>
                    
                    <div class="form-group">
                        <label for="mode">Investigation Mode</label>
                        <select id="mode">
                            <option value="quick">Quick (Basic scan)</option>
                            <option value="moderate">Moderate (+ Screenshots + Comments)</option>
                            <option value="deep" selected>Deep (+ Downloads + Archive)</option>
                            <option value="deeper">Deeper (+ Extended pivot)</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="limit">Video Limit</label>
                        <input type="number" id="limit" value="60" min="5" max="500">
                    </div>
                    
                    <div class="form-group">
                        <label for="locale">Locale</label>
                        <select id="locale">
                            <option value="en-US">English (US)</option>
                            <option value="id-ID">Indonesian</option>
                            <option value="th-TH">Thai</option>
                            <option value="vi-VN">Vietnamese</option>
                            <option value="ms-MY">Malay</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="comments">Comments per Video</label>
                        <input type="number" id="comments" value="10" min="0" max="100">
                    </div>
                    
                    <div class="form-group full-width">
                        <label>Options</label>
                        <div class="checkbox-group">
                            <label class="checkbox-item">
                                <input type="checkbox" id="antidetect" checked>
                                Anti-Detection
                            </label>
                            <label class="checkbox-item">
                                <input type="checkbox" id="screenshot">
                                Screenshots
                            </label>
                            <label class="checkbox-item">
                                <input type="checkbox" id="download">
                                Download Videos
                            </label>
                            <label class="checkbox-item">
                                <input type="checkbox" id="web_archive">
                                Web Archive
                            </label>
                            <label class="checkbox-item">
                                <input type="checkbox" id="headless" checked>
                                Headless Browser
                            </label>
                        </div>
                    </div>
                </div>
                
                <div style="margin-top: 1.5rem; display: flex; gap: 1rem;">
                    <button type="submit" class="btn btn-primary">
                        <span>🔍</span> Start Investigation
                    </button>
                    <button type="button" class="btn btn-secondary" onclick="resetForm()">
                        Reset
                    </button>
                </div>
            </form>
        </div>

        <!-- Active Scan Progress -->
        <div id="scanProgress" class="glass-card hidden">
            <div class="card-title">
                <span>⏳</span> Investigation in Progress
                <span id="scanStatus" class="status-badge status-running" style="margin-left: auto;">
                    <span class="pulse">●</span> Running
                </span>
            </div>
            <div class="progress-container">
                <div class="progress-bar">
                    <div id="progressFill" class="progress-fill" style="width: 0%"></div>
                </div>
                <div class="progress-text">
                    <span id="progressText">Processing...</span>
                    <span id="progressPercent">0%</span>
                </div>
            </div>
            <button class="btn btn-danger" onclick="stopScan()">
                <span>⏹</span> Stop Scan
            </button>
        </div>

        <!-- Results Stats -->
        <div id="resultsStats" class="stats-grid hidden">
            <div class="stat-card">
                <div class="stat-icon">📹</div>
                <div id="totalVideos" class="stat-value">0</div>
                <div class="stat-label">Total Videos</div>
            </div>
            <div class="stat-card danger">
                <div class="stat-icon">🚨</div>
                <div id="highRisk" class="stat-value">0</div>
                <div class="stat-label">High Risk</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-icon">⚠️</div>
                <div id="mediumRisk" class="stat-value">0</div>
                <div class="stat-label">Medium Risk</div>
            </div>
            <div class="stat-card success">
                <div class="stat-icon">⏱️</div>
                <div id="duration" class="stat-value">0s</div>
                <div class="stat-label">Duration</div>
            </div>
        </div>

        <!-- Results Table -->
        <div id="resultsCard" class="glass-card hidden">
            <div class="card-title">
                <span>📋</span> Investigation Results
                <div style="margin-left: auto; display: flex; gap: 0.5rem;">
                    <a id="downloadCsv" href="#" class="btn btn-secondary">📥 CSV</a>
                    <a id="downloadHtml" href="#" class="btn btn-secondary" target="_blank">📄 Report</a>
                </div>
            </div>
            <div class="table-container">
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>Video</th>
                            <th>Description</th>
                            <th>Risk</th>
                            <th>Engagement</th>
                            <th>URLs</th>
                        </tr>
                    </thead>
                    <tbody id="resultsBody">
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        let socket = null;
        let currentScanId = null;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            initSocketIO();
            document.getElementById('scanForm').addEventListener('submit', startScan);
        });

        function initSocketIO() {
            try {
                socket = io();
                
                socket.on('connect', () => {
                    document.getElementById('connectionStatus').innerHTML = '<span style="color: var(--success);">●</span> Connected';
                    document.getElementById('connectionStatus').className = 'status-badge status-completed';
                });

                socket.on('disconnect', () => {
                    document.getElementById('connectionStatus').innerHTML = '<span class="pulse">●</span> Disconnected';
                    document.getElementById('connectionStatus').className = 'status-badge status-failed';
                });

                socket.on('scan_progress', (data) => {
                    if (data.scan_id === currentScanId) {
                        updateProgress(data);
                    }
                });

                socket.on('scan_complete', (data) => {
                    if (data.scan_id === currentScanId) {
                        loadResults(data.scan_id);
                    }
                });

                socket.on('scan_error', (data) => {
                    if (data.scan_id === currentScanId) {
                        showError(data.error);
                    }
                });
            } catch (e) {
                console.log('SocketIO not available, using polling');
            }
        }

        async function startScan(e) {
            e.preventDefault();
            
            const data = {
                keywords: document.getElementById('keywords').value,
                mode: document.getElementById('mode').value,
                limit: parseInt(document.getElementById('limit').value),
                locale: document.getElementById('locale').value,
                comments: parseInt(document.getElementById('comments').value),
                antidetect: document.getElementById('antidetect').checked,
                screenshot: document.getElementById('screenshot').checked,
                download: document.getElementById('download').checked,
                web_archive: document.getElementById('web_archive').checked,
                headless: document.getElementById('headless').checked,
            };

            try {
                const response = await fetch('/api/scan/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                });

                const result = await response.json();
                
                if (result.scan_id) {
                    currentScanId = result.scan_id;
                    showProgress();
                    
                    if (socket) {
                        socket.emit('subscribe_scan', { scan_id: currentScanId });
                    }
                    
                    // Fallback polling if no socket
                    if (!socket) {
                        pollStatus();
                    }
                } else {
                    alert('Failed to start scan: ' + result.error);
                }
            } catch (err) {
                alert('Error starting scan: ' + err.message);
            }
        }

        function showProgress() {
            document.getElementById('scanProgress').classList.remove('hidden');
            document.getElementById('resultsStats').classList.add('hidden');
            document.getElementById('resultsCard').classList.add('hidden');
        }

        function updateProgress(data) {
            const percent = data.total > 0 ? Math.round((data.progress / data.total) * 100) : 0;
            document.getElementById('progressFill').style.width = percent + '%';
            document.getElementById('progressText').textContent = `${data.stage}: ${data.progress} / ${data.total}`;
            document.getElementById('progressPercent').textContent = percent + '%';
        }

        async function pollStatus() {
            if (!currentScanId) return;
            
            try {
                const response = await fetch(`/api/scan/${currentScanId}/status`);
                const data = await response.json();
                
                if (data.status === 'completed') {
                    loadResults(currentScanId);
                } else if (data.status === 'failed') {
                    showError(data.error || 'Scan failed');
                } else {
                    updateProgress({
                        stage: data.status,
                        progress: data.progress || 0,
                        total: data.total || 0,
                    });
                    setTimeout(pollStatus, 2000);
                }
            } catch (err) {
                setTimeout(pollStatus, 5000);
            }
        }

        async function loadResults(scanId) {
            try {
                const response = await fetch(`/api/scan/${scanId}/results`);
                const data = await response.json();
                
                // Hide progress, show results
                document.getElementById('scanProgress').classList.add('hidden');
                document.getElementById('resultsStats').classList.remove('hidden');
                document.getElementById('resultsCard').classList.remove('hidden');
                
                // Update stats
                document.getElementById('totalVideos').textContent = data.total_videos;
                document.getElementById('highRisk').textContent = data.high_risk_count;
                document.getElementById('mediumRisk').textContent = data.medium_risk_count;
                document.getElementById('duration').textContent = formatDuration(data.duration_seconds);
                
                // Update download links
                if (data.output_files.csv) {
                    document.getElementById('downloadCsv').href = `/api/download/${data.output_files.csv.replace('out/', '')}`;
                }
                if (data.output_files.html) {
                    document.getElementById('downloadHtml').href = `/api/download/${data.output_files.html.replace('out/', '')}`;
                }
                
                // Populate table
                const tbody = document.getElementById('resultsBody');
                tbody.innerHTML = '';
                
                data.videos.forEach(video => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>
                            <a href="${video.url}" target="_blank">${video.video_id || 'N/A'}</a>
                            <br><small>@${video.username || ''}</small>
                        </td>
                        <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis;">
                            ${(video.description || '').substring(0, 100)}...
                        </td>
                        <td>
                            <span class="risk-badge ${getRiskClass(video.risk_score)}">
                                ${video.risk_score} - ${video.risk_level}
                            </span>
                        </td>
                        <td>
                            ❤️ ${formatNumber(video.like_count)}<br>
                            💬 ${formatNumber(video.comment_count)}
                        </td>
                        <td>
                            ${(video.extracted_urls || []).slice(0, 2).map(u => 
                                `<a href="${u}" target="_blank">${u.substring(0, 30)}...</a>`
                            ).join('<br>')}
                        </td>
                    `;
                    tbody.appendChild(row);
                });
                
                // Update status
                document.getElementById('scanStatus').innerHTML = '<span style="color: var(--success);">✓</span> Completed';
                document.getElementById('scanStatus').className = 'status-badge status-completed';
                
            } catch (err) {
                console.error('Failed to load results:', err);
            }
        }

        function stopScan() {
            if (currentScanId) {
                fetch(`/api/scan/${currentScanId}/stop`, { method: 'POST' });
            }
        }

        function showError(message) {
            document.getElementById('scanProgress').classList.add('hidden');
            alert('Scan failed: ' + message);
        }

        function resetForm() {
            document.getElementById('scanForm').reset();
        }

        function getRiskClass(score) {
            if (score >= 5) return 'risk-high';
            if (score >= 2) return 'risk-medium';
            return 'risk-low';
        }

        function formatNumber(n) {
            if (n === null || n === undefined) return '—';
            if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
            if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
            return n.toString();
        }

        function formatDuration(seconds) {
            if (!seconds) return '0s';
            if (seconds < 60) return Math.round(seconds) + 's';
            if (seconds < 3600) return Math.round(seconds / 60) + 'm';
            return Math.round(seconds / 3600) + 'h';
        }
    </script>
</body>
</html>
"""


def run_gui(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    """Run the GUI server."""
    app = create_app()
    
    if SOCKETIO_AVAILABLE and "SOCKETIO" in app.config:
        socketio = app.config["SOCKETIO"]
        socketio.run(app, host=host, port=port, debug=debug)
    else:
        app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_gui(debug=True)
