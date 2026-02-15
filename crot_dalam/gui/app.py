#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Flask Web GUI Application
Enterprise-Grade Tactical OSINT Command Center.
"""
from __future__ import annotations

import json
import os
import threading
import time
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
_scan_lock = threading.Lock()


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
        
        # Store scan info with lock
        with _scan_lock:
            _active_scans[scan_id] = {
                "id": scan_id,
                "status": "starting",
                "progress": 0,
                "total": 0,
                "config": scan_config,
                "started_at": datetime.now().isoformat(),
                "log_entries": [],
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
        with _scan_lock:
            if scan_id in _active_scans:
                info = _active_scans[scan_id].copy()
                info.pop("config", None)
                return jsonify(info)
        
        if scan_id in _scan_results:
            result = _scan_results[scan_id]
            return jsonify({
                "id": scan_id,
                "status": result.status.value,
                "total_videos": result.total_videos,
                "high_risk_count": result.high_risk_count,
                "medium_risk_count": result.medium_risk_count,
                "low_risk_count": result.low_risk_count,
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
            "low_risk_count": result.low_risk_count,
            "duration_seconds": result.duration_seconds,
            "videos": [v.to_dict() for v in result.videos[:100]],
            "output_files": {
                "jsonl": result.output_jsonl,
                "csv": result.output_csv,
                "html": result.output_html,
            },
            "errors": result.errors,
        })
    
    @app.route("/api/scan/<scan_id>/stop", methods=["POST"])
    def stop_scan(scan_id: str):
        """Stop a running scan."""
        with _scan_lock:
            if scan_id in _active_scans:
                _active_scans[scan_id]["status"] = "stopping"
                return jsonify({"message": "Stop requested"})
        return jsonify({"error": "Scan not found"}), 404
    
    @app.route("/api/scans")
    def list_scans():
        """List all scans."""
        scans = []
        
        with _scan_lock:
            for scan_id, info in _active_scans.items():
                scans.append({
                    "id": scan_id,
                    "status": info.get("status"),
                    "started_at": info.get("started_at"),
                    "progress": info.get("progress", 0),
                    "total": info.get("total", 0),
                })
        
        for scan_id, result in _scan_results.items():
            with _scan_lock:
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
        with _scan_lock:
            if scan_id in _active_scans:
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
        with _scan_lock:
            if scan_id in _active_scans:
                _active_scans[scan_id]["status"] = "running"
        
        scraper = TikTokScraper(
            config=config,
            progress_callback=progress_callback,
        )
        
        result = scraper.run_scan()
        
        _scan_results[scan_id] = result
        with _scan_lock:
            if scan_id in _active_scans:
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
        with _scan_lock:
            if scan_id in _active_scans:
                _active_scans[scan_id]["status"] = "failed"
                _active_scans[scan_id]["error"] = str(e)
        
        if SOCKETIO_AVAILABLE and "SOCKETIO" in app.config:
            socketio = app.config["SOCKETIO"]
            socketio.emit("scan_error", {
                "scan_id": scan_id,
                "error": str(e),
            })
    
    finally:
        # Delayed cleanup: move to completed, keep for reference
        time.sleep(2)
        with _scan_lock:
            if scan_id in _active_scans:
                del _active_scans[scan_id]


def get_dashboard_html() -> str:
    """Get the main dashboard HTML — Tactical Command Center."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CROT DALAM — Tactical OSINT Command Center</title>
    <meta name="description" content="Enterprise-grade TikTok OSINT investigation platform with real-time monitoring and risk analysis.">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-void: #05060a;
            --bg-primary: #0a0c14;
            --bg-secondary: #0f1220;
            --bg-tertiary: #141829;
            --bg-card: rgba(15, 18, 32, 0.85);
            --bg-card-hover: rgba(20, 24, 41, 0.95);
            --text-primary: #e8eaf6;
            --text-secondary: #8b91b0;
            --text-dim: #505578;
            --accent: #00e5ff;
            --accent-glow: rgba(0, 229, 255, 0.15);
            --accent-dim: #006d7a;
            --accent-secondary: #7c4dff;
            --accent-secondary-glow: rgba(124, 77, 255, 0.15);
            --success: #00e676;
            --success-glow: rgba(0, 230, 118, 0.15);
            --warning: #ffab00;
            --warning-glow: rgba(255, 171, 0, 0.15);
            --danger: #ff1744;
            --danger-glow: rgba(255, 23, 68, 0.15);
            --critical: #ff5252;
            --border-color: rgba(0, 229, 255, 0.08);
            --border-active: rgba(0, 229, 255, 0.25);
            --glass: rgba(15, 18, 32, 0.65);
            --glass-border: rgba(0, 229, 255, 0.12);
            --radius: 6px;
            --font-mono: 'JetBrains Mono', 'Consolas', monospace;
            --font-sans: 'Inter', -apple-system, sans-serif;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        html, body {
            font-family: var(--font-sans);
            background: var(--bg-void);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Tactical grid background */
        body::before {
            content: '';
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background:
                linear-gradient(90deg, rgba(0,229,255,0.02) 1px, transparent 1px),
                linear-gradient(rgba(0,229,255,0.02) 1px, transparent 1px);
            background-size: 60px 60px;
            pointer-events: none;
            z-index: 0;
        }
        body::after {
            content: '';
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background:
                radial-gradient(ellipse at 15% 10%, rgba(0, 229, 255, 0.06) 0%, transparent 50%),
                radial-gradient(ellipse at 85% 90%, rgba(124, 77, 255, 0.04) 0%, transparent 50%);
            pointer-events: none;
            z-index: 0;
        }

        .app { position: relative; z-index: 1; display: flex; flex-direction: column; min-height: 100vh; }

        /* ═══ TOP BAR ═══ */
        .topbar {
            display: flex; align-items: center; justify-content: space-between;
            padding: 0.6rem 1.5rem;
            background: rgba(5, 6, 10, 0.9);
            border-bottom: 1px solid var(--border-color);
            backdrop-filter: blur(10px);
        }
        .topbar-brand {
            display: flex; align-items: center; gap: 0.75rem;
        }
        .brand-icon {
            width: 32px; height: 32px;
            background: linear-gradient(135deg, var(--accent) 0%, var(--accent-secondary) 100%);
            border-radius: 6px;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.85rem; font-weight: 700;
            box-shadow: 0 0 15px var(--accent-glow);
        }
        .brand-text { font-size: 0.9rem; font-weight: 700; letter-spacing: 0.5px; }
        .brand-text span { color: var(--accent); }
        .brand-tag {
            font-family: var(--font-mono); font-size: 0.6rem;
            color: var(--text-dim); letter-spacing: 1px;
            text-transform: uppercase;
        }
        .topbar-status {
            display: flex; align-items: center; gap: 1.5rem; font-size: 0.72rem;
            color: var(--text-secondary); font-family: var(--font-mono);
        }
        .status-dot {
            width: 6px; height: 6px; border-radius: 50%;
            background: var(--success);
            box-shadow: 0 0 8px var(--success-glow);
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* ═══ MAIN LAYOUT ═══ */
        .main { display: flex; flex: 1; }

        /* ═══ SIDEBAR ═══ */
        .sidebar {
            width: 72px; background: rgba(10, 12, 20, 0.95);
            border-right: 1px solid var(--border-color);
            display: flex; flex-direction: column; align-items: center;
            padding: 1rem 0; gap: 0.25rem;
            position: relative; z-index: 10;
        }
        .nav-btn {
            width: 60px; height: 52px;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            gap: 2px;
            border: none; background: transparent;
            color: var(--text-dim); cursor: pointer;
            border-radius: var(--radius); font-size: 1.1rem;
            transition: all 0.2s;
            position: relative; z-index: 11;
        }
        .nav-btn .nav-label {
            font-size: 0.5rem; font-family: var(--font-mono);
            letter-spacing: 0.5px; text-transform: uppercase;
        }
        .nav-btn:hover, .nav-btn.active {
            background: var(--accent-glow);
            color: var(--accent);
        }
        .nav-btn.active { box-shadow: inset 3px 0 0 var(--accent); }

        /* ═══ CONTENT ═══ */
        .content { flex: 1; padding: 1.25rem; overflow-y: auto; display: flex; flex-direction: column; gap: 1.25rem; }

        /* ═══ METRIC CARDS ═══ */
        .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
        .metric-card {
            background: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: var(--radius); padding: 1rem 1.25rem;
            transition: all 0.3s;
        }
        .metric-card:hover {
            border-color: var(--border-active);
            box-shadow: 0 0 20px var(--accent-glow);
        }
        .metric-label {
            font-size: 0.65rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 1.5px;
            color: var(--text-dim); margin-bottom: 0.5rem;
        }
        .metric-value {
            font-family: var(--font-mono); font-size: 1.6rem;
            font-weight: 700; color: var(--text-primary);
        }
        .metric-value.accent { color: var(--accent); }
        .metric-value.danger { color: var(--danger); }
        .metric-value.warning { color: var(--warning); }
        .metric-value.success { color: var(--success); }
        .metric-sub {
            font-size: 0.65rem; color: var(--text-dim);
            font-family: var(--font-mono); margin-top: 0.2rem;
        }

        /* ═══ PANELS ═══ */
        .panel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
        .panel {
            background: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: var(--radius); display: flex; flex-direction: column;
        }
        .panel-full { grid-column: 1 / -1; }
        .panel-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 0.75rem 1.25rem;
            border-bottom: 1px solid var(--border-color);
        }
        .panel-title {
            font-size: 0.7rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 1.5px;
            color: var(--text-secondary);
            display: flex; align-items: center; gap: 0.5rem;
        }
        .panel-title-dot {
            width: 5px; height: 5px; border-radius: 50%; background: var(--accent);
        }
        .panel-body { padding: 1.25rem; flex: 1; }

        /* ═══ SCAN FORM ═══ */
        .form-group { margin-bottom: 1rem; }
        .form-label {
            display: block; font-size: 0.7rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 1px;
            color: var(--text-secondary); margin-bottom: 0.4rem;
        }
        .form-input, .form-select {
            width: 100%; padding: 0.6rem 0.8rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            color: var(--text-primary); font-family: var(--font-mono);
            font-size: 0.8rem; transition: border-color 0.2s;
        }
        .form-input:focus, .form-select:focus {
            outline: none; border-color: var(--accent);
            box-shadow: 0 0 0 2px var(--accent-glow);
        }
        .form-input::placeholder { color: var(--text-dim); }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
        .form-row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.75rem; }

        .toggle-group { display: flex; flex-wrap: wrap; gap: 0.5rem; }
        .toggle {
            display: flex; align-items: center; gap: 0.4rem;
            padding: 0.35rem 0.7rem; border-radius: 4px;
            background: var(--bg-secondary);
            border: 1px solid var(--border-color); cursor: pointer;
            font-size: 0.7rem; color: var(--text-secondary);
            transition: all 0.2s; user-select: none;
        }
        .toggle:hover { border-color: var(--accent-dim); }
        .toggle.active {
            background: var(--accent-glow); border-color: var(--accent);
            color: var(--accent);
        }
        .toggle input { display: none; }

        /* ═══ BUTTONS ═══ */
        .btn {
            padding: 0.6rem 1.5rem; border: 1px solid var(--accent);
            border-radius: var(--radius); background: transparent;
            color: var(--accent); font-family: var(--font-mono);
            font-size: 0.75rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 1.5px;
            cursor: pointer; transition: all 0.3s;
        }
        .btn:hover {
            background: var(--accent); color: var(--bg-void);
            box-shadow: 0 0 25px var(--accent-glow);
        }
        .btn:disabled { opacity: 0.3; cursor: not-allowed; }
        .btn-danger { border-color: var(--danger); color: var(--danger); }
        .btn-danger:hover { background: var(--danger); color: white; }
        .btn-group { display: flex; gap: 0.75rem; margin-top: 1rem; }

        /* ═══ LOG CONSOLE ═══ */
        .log-console {
            background: rgba(5, 6, 10, 0.95);
            border: 1px solid var(--border-color);
            border-radius: var(--radius);
            font-family: var(--font-mono); font-size: 0.72rem;
            max-height: 300px; overflow-y: auto; padding: 0.75rem;
            color: var(--text-dim); line-height: 1.6;
        }
        .log-entry { padding: 1px 0; }
        .log-time { color: var(--text-dim); }
        .log-info { color: var(--accent); }
        .log-warn { color: var(--warning); }
        .log-error { color: var(--danger); }
        .log-success { color: var(--success); }

        /* ═══ RESULTS TABLE ═══ */
        .data-table {
            width: 100%; border-collapse: collapse;
            font-size: 0.75rem; font-family: var(--font-mono);
        }
        .data-table th {
            text-align: left; padding: 0.6rem 0.8rem;
            font-size: 0.6rem; font-weight: 600;
            text-transform: uppercase; letter-spacing: 1px;
            color: var(--text-dim);
            border-bottom: 1px solid var(--border-color);
        }
        .data-table td {
            padding: 0.6rem 0.8rem;
            border-bottom: 1px solid rgba(0,229,255,0.04);
            color: var(--text-secondary);
            max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .data-table tr:hover td { background: rgba(0,229,255,0.03); }

        .risk-badge {
            display: inline-block; padding: 2px 8px;
            border-radius: 3px; font-size: 0.6rem;
            font-weight: 600; letter-spacing: 0.5px;
        }
        .risk-critical { background: var(--danger-glow); color: var(--danger); border: 1px solid var(--danger); }
        .risk-high { background: rgba(255,87,34,0.15); color: #ff5722; border: 1px solid #ff5722; }
        .risk-medium { background: var(--warning-glow); color: var(--warning); border: 1px solid var(--warning); }
        .risk-low { background: var(--success-glow); color: var(--success); border: 1px solid var(--success); }
        .risk-none { background: rgba(0,0,0,0.2); color: var(--text-dim); border: 1px solid var(--text-dim); }

        /* ═══ PROGRESS ═══ */
        .progress-bar-track {
            width: 100%; height: 4px; background: var(--bg-secondary);
            border-radius: 2px; overflow: hidden; margin-top: 0.5rem;
        }
        .progress-bar-fill {
            height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent-secondary));
            border-radius: 2px; transition: width 0.5s;
            box-shadow: 0 0 10px var(--accent-glow);
        }

        /* ═══ SCAN STATUS INDICATOR ═══ */
        .scan-status { display: flex; align-items: center; gap: 0.5rem; font-family: var(--font-mono); font-size: 0.75rem; }
        .scan-status-dot {
            width: 8px; height: 8px; border-radius: 50%;
        }
        .scan-status-dot.running { background: var(--accent); animation: pulse 1s infinite; }
        .scan-status-dot.completed { background: var(--success); }
        .scan-status-dot.failed { background: var(--danger); }
        .scan-status-dot.idle { background: var(--text-dim); }

        /* ═══ EMPTY STATE ═══ */
        .empty-state {
            text-align: center; padding: 3rem;
            color: var(--text-dim); font-size: 0.8rem;
        }
        .empty-state-icon { font-size: 2.5rem; margin-bottom: 1rem; opacity: 0.3; }

        /* ═══ SCROLLBAR ═══ */
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 2px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent-dim); }

        /* ═══ RESPONSIVE ═══ */
        @media (max-width: 1200px) { .metrics { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 900px) {
            .panel-grid { grid-template-columns: 1fr; }
            .metrics { grid-template-columns: 1fr 1fr; }
            .sidebar { width: 54px; }
            .nav-btn { width: 48px; height: 44px; }
            .nav-btn .nav-label { display: none; }
        }

        /* ═══ NOTIFICATION TOAST ═══ */
        .toast-container { position: fixed; bottom: 1rem; right: 1rem; z-index: 9999; display: flex; flex-direction: column; gap: 0.5rem; }
        .toast {
            padding: 0.75rem 1.25rem; border-radius: var(--radius);
            font-family: var(--font-mono); font-size: 0.72rem;
            background: var(--bg-card); border: 1px solid var(--border-color);
            box-shadow: 0 4px 20px rgba(0,0,0,0.5); animation: slideIn 0.3s;
            max-width: 350px;
        }
        .toast.success { border-color: var(--success); }
        .toast.error { border-color: var(--danger); }
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    </style>
</head>
<body>
<div class="app">
    <!-- ═══ TOP BAR ═══ -->
    <header class="topbar">
        <div class="topbar-brand">
            <div class="brand-icon">⚡</div>
            <div>
                <div class="brand-text"><span>CROT</span> DALAM</div>
                <div class="brand-tag">Tactical OSINT Platform v3.0</div>
            </div>
        </div>
        <div class="topbar-status">
            <div style="display:flex;align-items:center;gap:6px;">
                <div class="status-dot"></div>
                <span>SYSTEM ONLINE</span>
            </div>
            <span id="clock"></span>
        </div>
    </header>

    <div class="main">
        <!-- ═══ SIDEBAR ═══ -->
        <nav class="sidebar">
            <button class="nav-btn active" onclick="showPage('dashboard')" title="Dashboard">
                <span>📊</span><span class="nav-label">Home</span>
            </button>
            <button class="nav-btn" onclick="showPage('scan')" title="New Scan">
                <span>🔍</span><span class="nav-label">Scan</span>
            </button>
            <button class="nav-btn" onclick="showPage('results')" title="Results">
                <span>📋</span><span class="nav-label">Results</span>
            </button>
            <button class="nav-btn" onclick="showPage('history')" title="History">
                <span>🗂️</span><span class="nav-label">History</span>
            </button>
        </nav>

        <!-- ═══ CONTENT ═══ -->
        <main class="content">
            <!-- ═══ DASHBOARD PAGE ═══ -->
            <div id="page-dashboard">
                <div class="metrics">
                    <div class="metric-card">
                        <div class="metric-label">Total Scans</div>
                        <div class="metric-value accent" id="m-total-scans">0</div>
                        <div class="metric-sub">lifetime investigations</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Videos Analyzed</div>
                        <div class="metric-value" id="m-total-videos">0</div>
                        <div class="metric-sub">across all scans</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">High Risk</div>
                        <div class="metric-value danger" id="m-high-risk">0</div>
                        <div class="metric-sub">critical findings</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Active Status</div>
                        <div class="scan-status" id="m-active-status">
                            <div class="scan-status-dot idle"></div>
                            <span>IDLE</span>
                        </div>
                        <div class="metric-sub" id="m-scan-detail">no active scan</div>
                    </div>
                </div>

                <div class="panel-grid">
                    <!-- Active Scan Monitor -->
                    <div class="panel">
                        <div class="panel-header">
                            <div class="panel-title"><div class="panel-title-dot"></div>SCAN MONITOR</div>
                        </div>
                        <div class="panel-body" id="scan-monitor">
                            <div class="empty-state">
                                <div class="empty-state-icon">📡</div>
                                <p>No active scan. Configure and launch from the Scan panel.</p>
                            </div>
                        </div>
                    </div>
                    <!-- Live Log Console -->
                    <div class="panel">
                        <div class="panel-header">
                            <div class="panel-title"><div class="panel-title-dot"></div>OPERATION LOG</div>
                        </div>
                        <div class="panel-body" style="padding: 0;">
                            <div class="log-console" id="log-console">
                                <div class="log-entry"><span class="log-time">[SYS]</span> <span class="log-info">CROT DALAM v3.0 initialized</span></div>
                                <div class="log-entry"><span class="log-time">[SYS]</span> <span class="log-success">Anti-detection engine loaded (2026.1)</span></div>
                                <div class="log-entry"><span class="log-time">[SYS]</span> <span class="log-info">CAPTCHA solver module ready</span></div>
                                <div class="log-entry"><span class="log-time">[SYS]</span> <span class="log-info">Waiting for scan target...</span></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ═══ SCAN PAGE ═══ -->
            <div id="page-scan" style="display:none;">
                <div class="panel-grid">
                    <div class="panel">
                        <div class="panel-header">
                            <div class="panel-title"><div class="panel-title-dot"></div>SCAN CONFIGURATION</div>
                        </div>
                        <div class="panel-body">
                            <form id="scan-form" onsubmit="startScan(event)">
                                <div class="form-group">
                                    <label class="form-label">Target Keywords</label>
                                    <input type="text" class="form-input" id="inp-keywords"
                                        placeholder="keyword1, keyword2, #hashtag..." required>
                                </div>
                                <div class="form-row">
                                    <div class="form-group">
                                        <label class="form-label">Investigation Mode</label>
                                        <select class="form-select" id="inp-mode">
                                            <option value="quick">⚡ Quick Recon</option>
                                            <option value="moderate" selected>🔍 Moderate Scan</option>
                                            <option value="deep">🎯 Deep Investigation</option>
                                            <option value="deeper">💀 Maximum Depth</option>
                                        </select>
                                    </div>
                                    <div class="form-group">
                                        <label class="form-label">Video Limit</label>
                                        <input type="number" class="form-input" id="inp-limit" value="60" min="1" max="500">
                                    </div>
                                </div>
                                <div class="form-row-3">
                                    <div class="form-group">
                                        <label class="form-label">Locale</label>
                                        <select class="form-select" id="inp-locale">
                                            <option value="en-US" selected>English (US)</option>
                                            <option value="id-ID">Indonesia</option>
                                            <option value="ja-JP">Japanese</option>
                                            <option value="ko-KR">Korean</option>
                                            <option value="th-TH">Thai</option>
                                            <option value="vi-VN">Vietnamese</option>
                                        </select>
                                    </div>
                                    <div class="form-group">
                                        <label class="form-label">Comments</label>
                                        <input type="number" class="form-input" id="inp-comments" value="0" min="0" max="100">
                                    </div>
                                    <div class="form-group">
                                        <label class="form-label">Hashtag Pivot</label>
                                        <input type="number" class="form-input" id="inp-pivot" value="0" min="0" max="10">
                                    </div>
                                </div>
                                <div class="form-group">
                                    <label class="form-label">Options</label>
                                    <div class="toggle-group">
                                        <label class="toggle active" id="tgl-antidetect">
                                            <input type="checkbox" checked> 🛡️ Anti-Detect
                                        </label>
                                        <label class="toggle" id="tgl-aggressive">
                                            <input type="checkbox"> ⚔️ Aggressive Mode
                                        </label>
                                        <label class="toggle" id="tgl-screenshot">
                                            <input type="checkbox"> 📸 Screenshots
                                        </label>
                                        <label class="toggle" id="tgl-download">
                                            <input type="checkbox"> 💾 Download
                                        </label>
                                        <label class="toggle" id="tgl-archive">
                                            <input type="checkbox"> 🏛️ Web Archive
                                        </label>
                                        <label class="toggle active" id="tgl-headless">
                                            <input type="checkbox" checked> 👻 Headless
                                        </label>
                                    </div>
                                </div>
                                <div class="btn-group">
                                    <button type="submit" class="btn" id="btn-start">LAUNCH SCAN ⚡</button>
                                    <button type="button" class="btn btn-danger" id="btn-stop" onclick="stopScan()" disabled>ABORT</button>
                                </div>
                            </form>
                        </div>
                    </div>
                    <div class="panel">
                        <div class="panel-header">
                            <div class="panel-title"><div class="panel-title-dot"></div>SCAN PROGRESS</div>
                        </div>
                        <div class="panel-body" id="scan-progress-panel">
                            <div class="empty-state">
                                <div class="empty-state-icon">🎯</div>
                                <p>Configure and launch your investigation.</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ═══ RESULTS PAGE ═══ -->
            <div id="page-results" style="display:none;">
                <div class="panel panel-full">
                    <div class="panel-header">
                        <div class="panel-title"><div class="panel-title-dot"></div>INVESTIGATION RESULTS</div>
                        <div class="btn-group" style="margin:0;">
                            <button class="btn" onclick="exportResults('csv')" style="padding:0.35rem 0.8rem;font-size:0.6rem;">EXPORT CSV</button>
                            <button class="btn" onclick="exportResults('html')" style="padding:0.35rem 0.8rem;font-size:0.6rem;">EXPORT HTML</button>
                        </div>
                    </div>
                    <div class="panel-body" id="results-body">
                        <div class="empty-state">
                            <div class="empty-state-icon">📋</div>
                            <p>No results yet. Complete a scan to view findings.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- ═══ HISTORY PAGE ═══ -->
            <div id="page-history" style="display:none;">
                <div class="panel panel-full">
                    <div class="panel-header">
                        <div class="panel-title"><div class="panel-title-dot"></div>INVESTIGATION HISTORY</div>
                    </div>
                    <div class="panel-body" id="history-body">
                        <div class="empty-state">
                            <div class="empty-state-icon">🗂️</div>
                            <p>No previous investigations found.</p>
                        </div>
                    </div>
                </div>
            </div>
        </main>
    </div>
</div>

<div class="toast-container" id="toast-container"></div>

<script>
// ═══════════════════════════════════════════════════════════════
// CROT DALAM — Tactical Command Center Frontend
// ═══════════════════════════════════════════════════════════════

const state = {
    activeScanId: null,
    pollInterval: null,
    currentPage: 'dashboard',
    totalScans: 0,
    totalVideos: 0,
    totalHighRisk: 0,
};

// ── Clock ──
function updateClock() {
    const now = new Date();
    document.getElementById('clock').textContent =
        now.toISOString().slice(0, 19).replace('T', ' ') + ' UTC';
}
setInterval(updateClock, 1000);
updateClock();

// ── Navigation ──
function showPage(page) {
    ['dashboard', 'scan', 'results', 'history'].forEach(p => {
        document.getElementById('page-' + p).style.display = p === page ? 'block' : 'none';
    });
    document.querySelectorAll('.nav-btn').forEach((btn, i) => {
        btn.classList.toggle('active', ['dashboard', 'scan', 'results', 'history'][i] === page);
    });
    state.currentPage = page;
    if (page === 'history') loadHistory();
}

// ── Toggle Buttons ──
document.querySelectorAll('.toggle').forEach(el => {
    el.addEventListener('click', () => {
        const cb = el.querySelector('input[type="checkbox"]');
        cb.checked = !cb.checked;
        el.classList.toggle('active', cb.checked);
    });
});

// ── Log ──
function addLog(msg, level = 'info') {
    const console_ = document.getElementById('log-console');
    const time = new Date().toTimeString().slice(0, 8);
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = '<span class="log-time">[' + time + ']</span> <span class="log-' + level + '">' + msg + '</span>';
    console_.appendChild(entry);
    console_.scrollTop = console_.scrollHeight;
}

// ── Toast ──
function showToast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ── Start Scan ──
async function startScan(e) {
    e.preventDefault();

    const keywords = document.getElementById('inp-keywords').value;
    if (!keywords.trim()) return;

    const payload = {
        keywords: keywords,
        mode: document.getElementById('inp-mode').value,
        limit: parseInt(document.getElementById('inp-limit').value),
        locale: document.getElementById('inp-locale').value,
        comments: parseInt(document.getElementById('inp-comments').value),
        pivot_hashtags: parseInt(document.getElementById('inp-pivot').value),
        antidetect: document.querySelector('#tgl-antidetect input').checked,
        antidetect_aggressive: document.querySelector('#tgl-aggressive input').checked,
        screenshot: document.querySelector('#tgl-screenshot input').checked,
        download: document.querySelector('#tgl-download input').checked,
        web_archive: document.querySelector('#tgl-archive input').checked,
        headless: document.querySelector('#tgl-headless input').checked,
    };

    document.getElementById('btn-start').disabled = true;
    document.getElementById('btn-stop').disabled = false;
    addLog('Initiating scan: ' + keywords, 'info');

    try {
        const resp = await fetch('/api/scan/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await resp.json();

        if (data.scan_id) {
            state.activeScanId = data.scan_id;
            state.totalScans++;
            addLog('Scan ' + data.scan_id + ' launched [' + data.mode + ']', 'success');
            showToast('Scan launched: ' + data.scan_id, 'success');
            startPolling(data.scan_id);
            updateDashboardStatus('running', data.scan_id);
        } else {
            addLog('Error: ' + (data.error || 'Unknown'), 'error');
            document.getElementById('btn-start').disabled = false;
            document.getElementById('btn-stop').disabled = true;
        }
    } catch (err) {
        addLog('Network error: ' + err.message, 'error');
        document.getElementById('btn-start').disabled = false;
        document.getElementById('btn-stop').disabled = true;
    }
}

// ── Stop Scan ──
async function stopScan() {
    if (!state.activeScanId) return;
    try {
        await fetch('/api/scan/' + state.activeScanId + '/stop', { method: 'POST' });
        addLog('Stop requested for ' + state.activeScanId, 'warn');
    } catch (e) {
        addLog('Failed to stop: ' + e.message, 'error');
    }
}

// ── Polling ──
function startPolling(scanId) {
    if (state.pollInterval) clearInterval(state.pollInterval);

    const progressPanel = document.getElementById('scan-progress-panel');
    const monitorPanel = document.getElementById('scan-monitor');

    state.pollInterval = setInterval(async () => {
        try {
            const resp = await fetch('/api/scan/' + scanId + '/status');
            if (!resp.ok) {
                onScanDone(scanId, 'unknown');
                return;
            }
            const data = await resp.json();

            if (data.error === 'Scan not found') {
                // Scan completed and was cleaned up
                onScanDone(scanId, 'completed');
                return;
            }

            const pct = data.total > 0 ? Math.round((data.progress / data.total) * 100) : 0;

            // Update progress panel
            progressPanel.innerHTML =
                '<div style="margin-bottom:1rem;">' +
                '  <div class="scan-status"><div class="scan-status-dot running"></div><span>' + (data.status || 'running').toUpperCase() + '</span></div>' +
                '  <div class="progress-bar-track"><div class="progress-bar-fill" style="width:' + pct + '%"></div></div>' +
                '  <div style="display:flex;justify-content:space-between;margin-top:0.4rem;font-size:0.65rem;font-family:var(--font-mono);color:var(--text-dim);">' +
                '    <span>Progress: ' + data.progress + '/' + data.total + '</span>' +
                '    <span>' + pct + '%</span>' +
                '  </div>' +
                '</div>';

            // Update monitor
            monitorPanel.innerHTML =
                '<div style="font-family:var(--font-mono);font-size:0.75rem;">' +
                '  <div style="margin-bottom:0.5rem;"><span style="color:var(--text-dim);">SCAN ID:</span> <span style="color:var(--accent);">' + scanId + '</span></div>' +
                '  <div style="margin-bottom:0.5rem;"><span style="color:var(--text-dim);">STATUS:</span> <span style="color:var(--success);">' + (data.status || 'running').toUpperCase() + '</span></div>' +
                '  <div style="margin-bottom:0.5rem;"><span style="color:var(--text-dim);">PROGRESS:</span> ' + data.progress + ' / ' + data.total + '</div>' +
                '  <div class="progress-bar-track"><div class="progress-bar-fill" style="width:' + pct + '%"></div></div>' +
                '</div>';

            // Check completion
            if (['completed', 'failed'].includes(data.status)) {
                onScanDone(scanId, data.status);
            }
        } catch (e) {
            // Network error — try to fetch results directly
            try {
                const resultResp = await fetch('/api/scan/' + scanId + '/results');
                if (resultResp.ok) {
                    onScanDone(scanId, 'completed');
                }
            } catch(e2) {}
        }
    }, 2000);
}

async function onScanDone(scanId, status) {
    clearInterval(state.pollInterval);
    state.pollInterval = null;

    document.getElementById('btn-start').disabled = false;
    document.getElementById('btn-stop').disabled = true;

    if (status === 'completed') {
        addLog('Scan ' + scanId + ' completed successfully', 'success');
        showToast('Scan complete!', 'success');
        updateDashboardStatus('completed', scanId);
        await loadResults(scanId);
    } else {
        addLog('Scan ' + scanId + ' ' + status, 'error');
        showToast('Scan ' + status, 'error');
        updateDashboardStatus('failed', scanId);
    }
    state.activeScanId = null;
}

// ── Load Results ──
async function loadResults(scanId) {
    try {
        const resp = await fetch('/api/scan/' + scanId + '/results');
        if (!resp.ok) return;
        const data = await resp.json();

        state.totalVideos += data.total_videos || 0;
        state.totalHighRisk += data.high_risk_count || 0;
        updateMetrics();

        const resultsBody = document.getElementById('results-body');
        if (!data.videos || data.videos.length === 0) {
            resultsBody.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📋</div><p>No videos found in this scan.</p></div>';
            return;
        }

        let html = '<table class="data-table"><thead><tr>' +
            '<th>User</th><th>Description</th><th>Views</th><th>Likes</th><th>Risk</th><th>Hashtags</th>' +
            '</tr></thead><tbody>';

        data.videos.forEach(v => {
            const riskClass = v.risk_score >= 10 ? 'critical' : v.risk_score >= 5 ? 'high' : v.risk_score >= 2 ? 'medium' : v.risk_score > 0 ? 'low' : 'none';
            const riskLabel = v.risk_level || riskClass.toUpperCase();
            const desc = (v.description || '-').substring(0, 80);
            const tags = (v.hashtags || []).slice(0, 3).map(t => '#' + t).join(' ');
            html += '<tr>' +
                '<td>@' + (v.username || 'unknown') + '</td>' +
                '<td title="' + (v.description || '').replace(/"/g, '&quot;') + '">' + desc + '</td>' +
                '<td>' + formatNum(v.view_count) + '</td>' +
                '<td>' + formatNum(v.like_count) + '</td>' +
                '<td><span class="risk-badge risk-' + riskClass + '">' + riskLabel + '</span></td>' +
                '<td style="color:var(--accent-dim);font-size:0.65rem;">' + tags + '</td>' +
                '</tr>';
        });

        html += '</tbody></table>';
        resultsBody.innerHTML = html;

        // Show results page
        showPage('results');
    } catch (e) {
        addLog('Failed to load results: ' + e.message, 'error');
    }
}

// ── History ──
async function loadHistory() {
    try {
        const resp = await fetch('/api/scans');
        const scans = await resp.json();
        const body = document.getElementById('history-body');

        if (!scans || scans.length === 0) {
            body.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🗂️</div><p>No previous investigations.</p></div>';
            return;
        }

        let html = '<table class="data-table"><thead><tr><th>Scan ID</th><th>Status</th><th>Videos</th><th>High Risk</th><th>Action</th></tr></thead><tbody>';
        scans.forEach(s => {
            html += '<tr>' +
                '<td style="color:var(--accent);">' + s.id + '</td>' +
                '<td>' + (s.status || '-') + '</td>' +
                '<td>' + (s.total_videos || s.total || '-') + '</td>' +
                '<td style="color:var(--danger);">' + (s.high_risk_count || '-') + '</td>' +
                '<td><button class="btn" style="padding:0.25rem 0.5rem;font-size:0.55rem;" onclick="loadResults(\\\'' + s.id + '\\\')">VIEW</button></td>' +
                '</tr>';
        });
        html += '</tbody></table>';
        body.innerHTML = html;
    } catch (e) {
        addLog('Failed to load history', 'error');
    }
}

// ── Dashboard helpers ──
function updateDashboardStatus(status, scanId) {
    const el = document.getElementById('m-active-status');
    const detail = document.getElementById('m-scan-detail');
    const dotClass = status === 'running' ? 'running' : status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'idle';
    el.innerHTML = '<div class="scan-status-dot ' + dotClass + '"></div><span>' + status.toUpperCase() + '</span>';
    detail.textContent = scanId ? 'scan: ' + scanId : 'no active scan';
    updateMetrics();
}

function updateMetrics() {
    document.getElementById('m-total-scans').textContent = state.totalScans;
    document.getElementById('m-total-videos').textContent = state.totalVideos;
    document.getElementById('m-high-risk').textContent = state.totalHighRisk;
}

function formatNum(n) {
    if (n === null || n === undefined) return '-';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return n.toString();
}

async function exportResults(format) {
    showToast('Preparing ' + format.toUpperCase() + ' export...', 'info');
    // Results are already exported during scan
    addLog('Export files available in /out/ directory', 'info');
}

// ── Init ──
addLog('Command center ready', 'success');
</script>
</body>
</html>
"""


def run_gui(host: str = "127.0.0.1", port: int = 5000, debug: bool = False) -> None:
    """Run the GUI server."""
    app = create_app()
    
    if SOCKETIO_AVAILABLE:
        socketio = app.config.get("SOCKETIO")
        if socketio:
            socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
            return
    
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_gui(debug=True)
