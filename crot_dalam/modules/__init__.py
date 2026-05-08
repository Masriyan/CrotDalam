#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Advanced OSINT Modules
Expert-level intelligence modules for comprehensive TikTok analysis.
"""

from .graph_intelligence import GraphIntelligence, Entity, InfluenceScore
from .media_forensics import MediaForensics, MediaAnalysisResult, ManipulationType
from .trend_prediction import TrendPredictor, TrendDirection, ViralPrediction
from .cross_platform import CrossPlatformIntelligence, IdentityCluster, Platform
from .geospatial import GeospatialIntelligence, GeoLocation, GeographicCluster

__all__ = [
    # Graph Intelligence
    "GraphIntelligence",
    "Entity",
    "InfluenceScore",
    
    # Media Forensics
    "MediaForensics",
    "MediaAnalysisResult",
    "ManipulationType",
    
    # Trend Prediction
    "TrendPredictor",
    "TrendDirection",
    "ViralPrediction",
    
    # Cross-Platform
    "CrossPlatformIntelligence",
    "IdentityCluster",
    "Platform",
    
    # Geospatial
    "GeospatialIntelligence",
    "GeoLocation",
    "GeographicCluster",
]

__version__ = "4.0.0"
__author__ = "CROT DALAM Team"
