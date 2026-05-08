#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Media Forensics Module
Advanced media analysis: reverse image search, OCR, audio clustering, manipulation detection.
"""
from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import imagehash
    from PIL import Image
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False


class ManipulationType(str, Enum):
    """Types of detected manipulations."""
    DEEPFAKE = "deepfake"
    SPOOFED = "spoofed"
    EDITED = "edited"
    REUPLOADED = "reuploaded"
    WATERMARK_REMOVED = "watermark_removed"
    METADATA_TAMPERED = "metadata_tampered"


@dataclass
class TextExtraction:
    """Extracted text from media."""
    text: str
    confidence: float
    language: str
    bounding_boxes: List[Dict[str, int]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)


@dataclass
class ImageFingerprint:
    """Perceptual hash and metadata for an image."""
    image_hash: str
    average_hash: str
    difference_hash: str
    color_hash: str
    dimensions: Tuple[int, int]
    file_size: Optional[int] = None
    dominant_colors: List[str] = field(default_factory=list)


@dataclass
class AudioSignature:
    """Audio fingerprint/clustering signature."""
    signature: str
    duration_seconds: float
    sample_rate: int
    channels: int
    spectral_features: Dict[str, float] = field(default_factory=dict)


@dataclass
class ManipulationResult:
    """Result of manipulation detection."""
    is_manipulated: bool
    manipulation_types: List[ManipulationType]
    confidence: float
    indicators: List[str]
    technical_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MediaAnalysisResult:
    """Complete media analysis result."""
    media_id: str
    media_type: str  # "image", "video", "audio"
    source_url: Optional[str] = None
    
    # Text extraction
    ocr_result: Optional[TextExtraction] = None
    
    # Fingerprinting
    image_fingerprint: Optional[ImageFingerprint] = None
    audio_signature: Optional[AudioSignature] = None
    
    # Manipulation detection
    manipulation_result: Optional[ManipulationResult] = None
    
    # Reverse search
    similar_images: List[Dict[str, Any]] = field(default_factory=list)
    first_seen_online: Optional[str] = None
    
    # Metadata
    exif_data: Dict[str, Any] = field(default_factory=dict)
    analyzed_at: Optional[str] = None

    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "media_id": self.media_id,
            "media_type": self.media_type,
            "source_url": self.source_url,
            "analyzed_at": self.analyzed_at,
        }
        
        if self.ocr_result:
            result["ocr"] = {
                "text": self.ocr_result.text,
                "confidence": self.ocr_result.confidence,
                "language": self.ocr_result.language,
                "keywords": self.ocr_result.keywords
            }
        
        if self.image_fingerprint:
            result["fingerprint"] = {
                "image_hash": self.image_fingerprint.image_hash,
                "average_hash": self.image_fingerprint.average_hash,
                "difference_hash": self.image_fingerprint.difference_hash
            }
        
        if self.manipulation_result:
            result["manipulation"] = {
                "is_manipulated": self.manipulation_result.is_manipulated,
                "types": [t.value for t in self.manipulation_result.manipulation_types],
                "confidence": self.manipulation_result.confidence,
                "indicators": self.manipulation_result.indicators
            }
        
        if self.similar_images:
            result["similar_count"] = len(self.similar_images)
            result["first_seen"] = self.first_seen_online
        
        return result


class MediaForensics:
    """
    Advanced media forensics for OSINT analysis.
    Performs OCR, perceptual hashing, manipulation detection, and reverse search.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path("out/media_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.fingerprint_db: Dict[str, Dict[str, Any]] = {}
        self.audio_cluster_db: Dict[str, List[str]] = {}

    def analyze_image(
        self, 
        image_path: str, 
        source_url: Optional[str] = None,
        perform_ocr: bool = True,
        perform_reverse_search: bool = True
    ) -> MediaAnalysisResult:
        """Perform comprehensive image analysis."""
        image_id = self._generate_media_id(image_path)
        result = MediaAnalysisResult(
            media_id=image_id,
            media_type="image",
            source_url=source_url
        )
        
        # Load image
        try:
            img = Image.open(image_path)
        except Exception as e:
            return result
        
        # Extract EXIF metadata
        result.exif_data = self._extract_exif(img)
        
        # Generate perceptual hashes
        if IMAGEHASH_AVAILABLE:
            result.image_fingerprint = self._generate_image_fingerprint(img, image_path)
            
            # Store in fingerprint database
            self._store_fingerprint(result.image_fingerprint, image_id, source_url)
        
        # Perform OCR
        if perform_ocr and TESSERACT_AVAILABLE:
            result.ocr_result = self._perform_ocr(img)
        
        # Detect manipulations
        result.manipulation_result = self._detect_image_manipulation(img, image_path)
        
        # Reverse image search (simulated - would need external API in production)
        if perform_reverse_search and result.image_fingerprint:
            result.similar_images = self._find_similar_images(result.image_fingerprint)
            if result.similar_images:
                result.first_seen_online = min(
                    (img.get("first_seen") for img in result.similar_images if img.get("first_seen")),
                    default=None
                )

        return result

    def analyze_video_frame(
        self,
        frame_path: str,
        video_id: str,
        frame_timestamp: float,
        source_url: Optional[str] = None
    ) -> MediaAnalysisResult:
        """Analyze a specific video frame."""
        result = self.analyze_image(
            image_path=frame_path,
            source_url=f"{source_url}?t={frame_timestamp}" if source_url else None,
            perform_ocr=True,
            perform_reverse_search=True
        )
        result.media_id = f"{video_id}_frame_{frame_timestamp:.2f}"
        return result

    def extract_audio_signature(
        self,
        audio_path: str,
        video_id: Optional[str] = None
    ) -> Optional[AudioSignature]:
        """Extract audio signature for clustering and matching."""
        # Placeholder - would use librosa or similar in production
        try:
            # Simulate audio signature extraction
            with open(audio_path, 'rb') as f:
                content = f.read()
            
            signature = hashlib.sha256(content).hexdigest()[:32]
            
            audio_sig = AudioSignature(
                signature=signature,
                duration_seconds=0.0,  # Would extract from actual audio
                sample_rate=44100,
                channels=2,
                spectral_features={}
            )
            
            # Store for clustering
            if video_id:
                cluster_key = signature[:8]
                if cluster_key not in self.audio_cluster_db:
                    self.audio_cluster_db[cluster_key] = []
                self.audio_cluster_db[cluster_key].append(video_id)
            
            return audio_sig
        except Exception:
            return None

    def cluster_by_audio(self) -> Dict[str, List[str]]:
        """Cluster videos by audio signature (for detecting coordinated campaigns)."""
        clusters = {}
        for cluster_key, video_ids in self.audio_cluster_db.items():
            if len(video_ids) >= 2:
                clusters[cluster_key] = video_ids
        return clusters

    def detect_reupload_campaign(self, threshold: int = 3) -> List[Dict[str, Any]]:
        """Detect potential reupload campaigns based on image fingerprints."""
        campaigns = []
        
        # Group by perceptual hash
        hash_groups: Dict[str, List[Dict[str, Any]]] = {}
        for fp_id, fp_data in self.fingerprint_db.items():
            phash = fp_data.get("perceptual_hash", "")
            if phash:
                if phash not in hash_groups:
                    hash_groups[phash] = []
                hash_groups[phash].append(fp_data)
        
        # Identify groups with multiple sources
        for phash, items in hash_groups.items():
            if len(items) >= threshold:
                unique_sources = set(item.get("source_url") for item in items if item.get("source_url"))
                if len(unique_sources) >= 2:
                    campaigns.append({
                        "type": "reupload_campaign",
                        "fingerprint": phash,
                        "occurrences": len(items),
                        "unique_sources": list(unique_sources),
                        "video_ids": [item.get("media_id") for item in items],
                        "confidence": min(0.6 + len(items) * 0.1, 0.95),
                        "first_seen": min(
                            (item.get("first_seen") for item in items if item.get("first_seen")),
                            default=None
                        )
                    })

        return campaigns

    def _generate_media_id(self, path: str) -> str:
        """Generate unique media ID."""
        return hashlib.md5(f"{path}:{datetime.now().isoformat()}".encode()).hexdigest()[:16]

    def _extract_exif(self, img: Image.Image) -> Dict[str, Any]:
        """Extract EXIF metadata from image."""
        exif_data = {}
        try:
            exif = img._getexif()
            if exif:
                for tag_id, value in exif.items():
                    exif_data[str(tag_id)] = str(value)[:100]  # Truncate long values
        except Exception:
            pass
        return exif_data

    def _generate_image_fingerprint(
        self, 
        img: Image.Image, 
        path: str
    ) -> ImageFingerprint:
        """Generate perceptual hashes for image."""
        try:
            avg_hash = str(imagehash.average_hash(img))
            diff_hash = str(imagehash.difference_hash(img))
            color_hash = str(imagehash.colorhash(img))
            
            # Combined fingerprint
            combined = f"{avg_hash}{diff_hash}{color_hash}"
            fp_hash = hashlib.sha256(combined.encode()).hexdigest()[:32]
            
            # Get dominant colors (simplified)
            img_resized = img.resize((1, 1))
            pixel = img_resized.getpixel((0, 0))
            if isinstance(pixel, tuple):
                dominant_colors = [f"#{c:02x}" for c in pixel[:3]]
            else:
                dominant_colors = [f"#{pixel:02x}"]
            
            file_size = os.path.getsize(path) if os.path.exists(path) else None
            
            return ImageFingerprint(
                image_hash=fp_hash,
                average_hash=avg_hash,
                difference_hash=diff_hash,
                color_hash=color_hash,
                dimensions=img.size,
                file_size=file_size,
                dominant_colors=dominant_colors
            )
        except Exception:
            return ImageFingerprint(
                image_hash="",
                average_hash="",
                difference_hash="",
                color_hash="",
                dimensions=img.size
            )

    def _perform_ocr(self, img: Image.Image) -> TextExtraction:
        """Perform OCR on image using Tesseract."""
        try:
            text = pytesseract.image_to_string(img, lang='eng+ind')
            confidences = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            # Calculate average confidence
            avg_conf = sum(confidences['conf']) / len(confidences['conf']) if confidences['conf'] else 0.0
            
            # Extract keywords (simple approach)
            keywords = [
                word for word in text.lower().split()
                if len(word) > 4 and word not in {'the', 'and', 'with', 'that', 'this'}
            ][:10]
            
            return TextExtraction(
                text=text.strip(),
                confidence=avg_conf / 100.0,
                language="auto",
                keywords=keywords
            )
        except Exception:
            return TextExtraction(text="", confidence=0.0, language="unknown")

    def _detect_image_manipulation(
        self, 
        img: Image.Image, 
        path: str
    ) -> ManipulationResult:
        """Detect potential image manipulations."""
        indicators = []
        manipulation_types = []
        confidence = 0.0
        technical_details = {}
        
        # Check for ELA (Error Level Analysis) - simplified
        # In production, would use proper ELA algorithm
        
        # Check metadata inconsistencies
        exif_data = self._extract_exif(img)
        if not exif_data and img.format == 'JPEG':
            indicators.append("Missing EXIF data in JPEG")
            manipulation_types.append(ManipulationType.METADATA_TAMPERED)
            confidence += 0.3
        
        # Check for watermark removal artifacts (simplified)
        # Would use edge detection in production
        
        # Check compression inconsistencies
        technical_details["format"] = img.format
        technical_details["mode"] = img.mode
        
        is_manipulated = len(manipulation_types) > 0
        
        return ManipulationResult(
            is_manipulated=is_manipulated,
            manipulation_types=manipulation_types,
            confidence=confidence,
            indicators=indicators,
            technical_details=technical_details
        )

    def _find_similar_images(
        self, 
        fingerprint: ImageFingerprint
    ) -> List[Dict[str, Any]]:
        """Find similar images in fingerprint database."""
        similar = []
        
        for fp_id, fp_data in self.fingerprint_db.items():
            stored_hash = fp_data.get("perceptual_hash", "")
            if stored_hash and stored_hash != fingerprint.image_hash:
                # Calculate Hamming distance (simplified - compare avg_hash)
                avg_hash1 = fingerprint.average_hash
                avg_hash2 = fp_data.get("average_hash", "")
                
                if avg_hash1 and avg_hash2 and len(avg_hash1) == len(avg_hash2):
                    distance = sum(c1 != c2 for c1, c2 in zip(avg_hash1, avg_hash2))
                    if distance <= 5:  # Threshold for similarity
                        similar.append({
                            "media_id": fp_data.get("media_id"),
                            "source_url": fp_data.get("source_url"),
                            "first_seen": fp_data.get("first_seen"),
                            "similarity_score": 1.0 - (distance / len(avg_hash1))
                        })
        
        return sorted(similar, key=lambda x: x.get("similarity_score", 0), reverse=True)[:10]

    def _store_fingerprint(
        self, 
        fingerprint: ImageFingerprint, 
        media_id: str,
        source_url: Optional[str] = None
    ) -> None:
        """Store fingerprint in database."""
        self.fingerprint_db[media_id] = {
            "media_id": media_id,
            "perceptual_hash": fingerprint.image_hash,
            "average_hash": fingerprint.average_hash,
            "difference_hash": fingerprint.difference_hash,
            "color_hash": fingerprint.color_hash,
            "source_url": source_url,
            "first_seen": datetime.now().isoformat(),
            "dimensions": fingerprint.dimensions,
            "dominant_colors": fingerprint.dominant_colors
        }

    def export_analysis_report(self, results: List[MediaAnalysisResult]) -> Dict[str, Any]:
        """Export comprehensive analysis report."""
        reupload_campaigns = self.detect_reupload_campaign()
        audio_clusters = self.cluster_by_audio()
        
        return {
            "summary": {
                "total_analyzed": len(results),
                "images_with_text": sum(1 for r in results if r.ocr_result and r.ocr_result.text),
                "potential_manipulations": sum(1 for r in results if r.manipulation_result and r.manipulation_result.is_manipulated),
                "reupload_campaigns_detected": len(reupload_campaigns),
                "audio_clusters_found": len(audio_clusters)
            },
            "results": [r.to_dict() for r in results],
            "campaigns": reupload_campaigns,
            "audio_clusters": audio_clusters,
            "generated_at": datetime.now().isoformat()
        }
