#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM - Unit Tests for Exporters
Tests the data export functionality (JSON, CSV, HTML).
"""
import pytest
import json
import csv
import tempfile
import os
from pathlib import Path
from datetime import datetime

from crot_dalam.core.exporters import Exporter
from crot_dalam.models.data import VideoRecord, ScanResult, ScanConfig, ScanStatus


class TestExporterInitialization:
    """Tests for Exporter initialization."""
    
    def test_exporter_creation(self):
        """Test Exporter can be created."""
        exporter = Exporter()
        assert exporter is not None
    
    def test_exporter_with_output_dir(self):
        """Test Exporter with custom output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter = Exporter(output_dir=tmpdir)
            assert exporter.output_dir == Path(tmpdir)


class TestJSONExport:
    """Tests for JSON export functionality."""
    
    def test_export_video_to_json(self):
        """Test exporting a single video to JSON."""
        video = VideoRecord(
            id="test_123",
            url="https://example.com/video/123",
            description="Test video",
            author_username="testuser",
            collected_at=datetime.now(),
        )
        
        exporter = Exporter()
        json_str = exporter.to_json(video)
        
        data = json.loads(json_str)
        assert data["id"] == "test_123"
        assert data["url"] == "https://example.com/video/123"
    
    def test_export_videos_to_jsonl(self):
        """Test exporting multiple videos to JSONL format."""
        videos = [
            VideoRecord(id=f"video_{i}", url=f"https://example.com/{i}", author_username="user", collected_at=datetime.now())
            for i in range(3)
        ]
        
        exporter = Exporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = exporter.export_to_jsonl(videos, filename="test", output_dir=tmpdir)
            
            assert Path(filepath).exists()
            
            # Verify content
            with open(filepath, 'r') as f:
                lines = f.readlines()
                assert len(lines) == 3
                
                for i, line in enumerate(lines):
                    data = json.loads(line)
                    assert data["id"] == f"video_{i}"
    
    def test_export_scan_result_to_json(self):
        """Test exporting ScanResult to JSON."""
        config = ScanConfig(keywords=["test"])
        result = ScanResult(
            id="result_123",
            config=config,
            status=ScanStatus.COMPLETED,
            videos=[VideoRecord(id="v1", url="http://test.com", author_username="u", collected_at=datetime.now())],
            profiles=[],
            errors=[],
            started_at=datetime.now(),
            completed_at=datetime.now(),
            total_videos=1,
            total_errors=0,
        )
        
        exporter = Exporter()
        json_str = exporter.to_json(result)
        
        data = json.loads(json_str)
        assert data["id"] == "result_123"
        assert data["total_videos"] == 1


class TestCSVExport:
    """Tests for CSV export functionality."""
    
    def test_export_videos_to_csv(self):
        """Test exporting videos to CSV format."""
        videos = [
            VideoRecord(
                id=f"video_{i}",
                url=f"https://example.com/{i}",
                description=f"Description {i}",
                author_username="user",
                like_count=i * 100,
                collected_at=datetime.now(),
            )
            for i in range(3)
        ]
        
        exporter = Exporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = exporter.export_to_csv(videos, filename="test", output_dir=tmpdir)
            
            assert Path(filepath).exists()
            
            # Verify content
            with open(filepath, 'r', newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 3
                
                for i, row in enumerate(rows):
                    assert row["id"] == f"video_{i}"
                    assert int(row["like_count"]) == i * 100
    
    def test_csv_headers(self):
        """Test that CSV has correct headers."""
        video = VideoRecord(
            id="test",
            url="https://example.com",
            description="Test",
            author_username="user",
            collected_at=datetime.now(),
        )
        
        exporter = Exporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = exporter.export_to_csv([video], filename="headers_test", output_dir=tmpdir)
            
            with open(filepath, 'r') as f:
                header = f.readline().strip()
                assert "id" in header
                assert "url" in header
                assert "description" in header


class TestHTMLExport:
    """Tests for HTML export functionality."""
    
    def test_export_to_html(self):
        """Test exporting scan results to HTML report."""
        config = ScanConfig(keywords=["test"])
        result = ScanResult(
            id="html_test",
            config=config,
            status=ScanStatus.COMPLETED,
            videos=[
                VideoRecord(
                    id="v1",
                    url="https://example.com/1",
                    description="Video 1",
                    author_username="user1",
                    like_count=100,
                    risk_score=0.2,
                    collected_at=datetime.now(),
                )
            ],
            profiles=[],
            errors=[],
            started_at=datetime.now(),
            completed_at=datetime.now(),
            total_videos=1,
            total_errors=0,
            average_risk_score=0.2,
        )
        
        exporter = Exporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = exporter.export_to_html(result, filename="report", output_dir=tmpdir)
            
            assert Path(filepath).exists()
            
            # Verify HTML content
            with open(filepath, 'r') as f:
                content = f.read()
                assert "<!DOCTYPE html>" in content or "<html" in content
                assert "html_test" in content
                assert "Video 1" in content


class TestFormatSelection:
    """Tests for export format selection."""
    
    def test_export_with_format_parameter(self):
        """Test exporting with specific format."""
        videos = [
            VideoRecord(id="v1", url="http://test.com", author_username="u", collected_at=datetime.now())
        ]
        
        exporter = Exporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            # JSON export
            json_path = exporter.export(videos, format="json", filename="test", output_dir=tmpdir)
            assert Path(json_path).suffix == ".jsonl"
            
            # CSV export
            csv_path = exporter.export(videos, format="csv", filename="test", output_dir=tmpdir)
            assert Path(csv_path).suffix == ".csv"
            
            # HTML export requires ScanResult
            config = ScanConfig(keywords=["test"])
            result = ScanResult(
                id="fmt_test", config=config, status=ScanStatus.COMPLETED,
                videos=videos, profiles=[], errors=[],
                started_at=datetime.now(), completed_at=datetime.now(),
                total_videos=1, total_errors=0,
            )
            html_path = exporter.export(result, format="html", filename="report", output_dir=tmpdir)
            assert Path(html_path).suffix == ".html"


class TestFileOperations:
    """Tests for file operations."""
    
    def test_create_output_directory(self):
        """Test that output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new_output_dir"
            assert not new_dir.exists()
            
            exporter = Exporter(output_dir=str(new_dir))
            # Directory should be created during export
            videos = [VideoRecord(id="v1", url="http://test.com", author_username="u", collected_at=datetime.now())]
            exporter.export_to_jsonl(videos, filename="test", output_dir=str(new_dir))
            
            assert new_dir.exists()
    
    def test_filename_generation(self):
        """Test automatic filename generation."""
        exporter = Exporter()
        filename = exporter._generate_filename("test", "jsonl")
        
        assert "test" in filename
        assert filename.endswith(".jsonl")
    
    def test_overwrite_existing_file(self):
        """Test overwriting existing files."""
        videos1 = [VideoRecord(id="v1", url="http://test.com", author_username="u", collected_at=datetime.now())]
        videos2 = [
            VideoRecord(id="v1", url="http://test.com", author_username="u", collected_at=datetime.now()),
            VideoRecord(id="v2", url="http://test.com/2", author_username="u2", collected_at=datetime.now()),
        ]
        
        exporter = Exporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            # First export
            path1 = exporter.export_to_jsonl(videos1, filename="overwrite_test", output_dir=tmpdir)
            
            # Second export (should overwrite)
            path2 = exporter.export_to_jsonl(videos2, filename="overwrite_test", output_dir=tmpdir)
            
            assert path1 == path2
            
            # Verify only second export exists
            with open(path2, 'r') as f:
                lines = f.readlines()
                assert len(lines) == 2
