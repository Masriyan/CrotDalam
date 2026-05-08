#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Geospatial Intelligence Module
Location-based analysis, geographic clustering, and visual context extraction.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class LocationType(str, Enum):
    """Types of location references."""
    COORDINATES = "coordinates"
    PLACE_NAME = "place_name"
    LANDMARK = "landmark"
    ADDRESS = "address"
    REGION = "region"
    COUNTRY = "country"


@dataclass
class GeoLocation:
    """Geographic location with coordinates and metadata."""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_meters: Optional[float] = None
    
    # Parsed location components
    place_name: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    
    # Type and source
    location_type: LocationType = LocationType.PLACE_NAME
    source: str = "unknown"
    
    # Context
    extracted_from: str = ""  # e.g., "video_metadata", "bio", "comment"
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy_meters": self.accuracy_meters,
            "place_name": self.place_name,
            "city": self.city,
            "region": self.region,
            "country": self.country,
            "country_code": self.country_code,
            "location_type": self.location_type.value,
            "source": self.source,
            "extracted_from": self.extracted_from,
            "confidence": self.confidence
        }
    
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None


@dataclass
class VisualContext:
    """Visual elements detected in media that provide geographic context."""
    element_type: str  # "landmark", "signage", "vehicle_plate", "architecture"
    description: str
    location_hints: List[str] = field(default_factory=list)
    confidence: float = 0.0
    bounding_box: Optional[Tuple[int, int, int, int]] = None


@dataclass
class GeographicCluster:
    """Cluster of content from the same geographic area."""
    cluster_id: str
    center_lat: float
    center_lon: float
    radius_km: float
    content_count: int
    unique_authors: int
    primary_location: Optional[str] = None
    risk_concentration: float = 0.0
    time_distribution: Dict[str, int] = field(default_factory=dict)
    content_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "center": {"lat": self.center_lat, "lon": self.center_lon},
            "radius_km": self.radius_km,
            "content_count": self.content_count,
            "unique_authors": self.unique_authors,
            "primary_location": self.primary_location,
            "risk_concentration": self.risk_concentration,
            "time_distribution": self.time_distribution,
            "content_ids": self.content_ids[:20]  # Limit for export
        }


@dataclass
class HeatmapPoint:
    """Point for heatmap visualization."""
    latitude: float
    longitude: float
    intensity: float
    category: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)


class GeospatialIntelligence:
    """
    Geospatial intelligence for location-based OSINT analysis.
    Extracts locations, performs geographic clustering, and generates heatmaps.
    """

    def __init__(self):
        self.locations: List[GeoLocation] = []
        self.visual_contexts: Dict[str, List[VisualContext]] = defaultdict(list)
        self.geo_clusters: List[GeographicCluster] = []
        self.location_content_map: Dict[str, List[str]] = defaultdict(list)
        
        # Country code mapping (simplified)
        self.country_codes = {
            "indonesia": "ID", "indonesian": "ID", "indonesia": "ID",
            "malaysia": "MY", "malaysian": "MY",
            "singapore": "SG", "singaporean": "SG",
            "thailand": "TH", "thai": "TH",
            "vietnam": "VN", "vietnamese": "VN",
            "philippines": "PH", "filipino": "PH",
            "united states": "US", "usa": "US", "american": "US",
            "united kingdom": "GB", "british": "GB", "uk": "GB",
            "australia": "AU", "australian": "AU",
        }
        
        # Location keywords for extraction
        self.location_keywords = [
            r"\b(Jakarta|Bandung|Surabaya|Medan|Semarang|Makassar|Palembang)\b",
            r"\b(Kuala Lumpur|Johor|Penang|Selangor)\b",
            r"\b(Bangkok|Chiang Mai|Phuket)\b",
            r"\b(Manila|Cebu|Davao)\b",
            r"\b(Ho Chi Minh|Hanoi|Da Nang)\b",
            r"\b(Singapore)\b",
        ]

    def extract_location_from_text(self, text: str, source: str = "") -> Optional[GeoLocation]:
        """Extract location information from text."""
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Try to extract city/place names
        for pattern in self.location_keywords:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            if matches:
                place_name = matches[0]
                country = self._infer_country(place_name)
                
                # Get approximate coordinates (would use geocoding API in production)
                lat, lon = self._get_approximate_coords(place_name)
                
                return GeoLocation(
                    latitude=lat,
                    longitude=lon,
                    place_name=place_name.title(),
                    country=country,
                    country_code=self.country_codes.get(country.lower()),
                    location_type=LocationType.PLACE_NAME,
                    source=source or "text_extraction",
                    extracted_from="bio_or_description",
                    confidence=0.7
                )
        
        # Try to extract coordinates
        coord_pattern = r'(-?\d{1,2}\.\d{3,6})\s*,?\s*(-?\d{1,3}\.\d{3,6})'
        coord_matches = re.search(coord_pattern, text)
        if coord_matches:
            try:
                lat = float(coord_matches.group(1))
                lon = float(coord_matches.group(2))
                
                # Validate coordinate ranges
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return GeoLocation(
                        latitude=lat,
                        longitude=lon,
                        location_type=LocationType.COORDINATES,
                        source=source or "coordinate_extraction",
                        extracted_from="bio_or_description",
                        confidence=0.9
                    )
            except ValueError:
                pass
        
        return None

    def extract_locations_from_video(self, video_record: Any) -> List[GeoLocation]:
        """Extract all location references from a video record."""
        locations = []
        
        # Extract from description
        if hasattr(video_record, 'description') and video_record.description:
            loc = self.extract_location_from_text(
                video_record.description, 
                source="video_description"
            )
            if loc:
                loc.extracted_from = "description"
                locations.append(loc)
        
        # Extract from username/bio context if available
        if hasattr(video_record, 'username') and video_record.username:
            # Username might contain location hints
            loc_keywords = ['jakarta', 'bali', 'kl', 'malaysia', 'sgp']
            for keyword in loc_keywords:
                if keyword in video_record.username.lower():
                    loc = self.extract_location_from_text(keyword, source="username")
                    if loc:
                        loc.extracted_from = "username"
                        locations.append(loc)
                    break
        
        return locations

    def add_location(self, location: GeoLocation, content_id: str) -> None:
        """Add a location and map it to content."""
        self.locations.append(location)
        location_key = self._location_to_key(location)
        self.location_content_map[location_key].append(content_id)

    def cluster_geographic_points(
        self, 
        max_radius_km: float = 50.0,
        min_points: int = 3
    ) -> List[GeographicCluster]:
        """Cluster geographic points into regions."""
        clusters = []
        processed = set()
        
        # Filter locations with coordinates
        coords_locations = [loc for loc in self.locations if loc.has_coordinates()]
        
        for i, loc in enumerate(coords_locations):
            if i in processed:
                continue
            
            # Start new cluster
            cluster_points = [(loc.latitude, loc.longitude)]
            cluster_content = []
            
            # Find nearby points
            for j, other_loc in enumerate(coords_locations):
                if j in processed or j == i:
                    continue
                
                distance = self._haversine_distance(
                    loc.latitude, loc.longitude,
                    other_loc.latitude, other_loc.longitude
                )
                
                if distance <= max_radius_km:
                    cluster_points.append((other_loc.latitude, other_loc.longitude))
                    processed.add(j)
            
            if len(cluster_points) >= min_points:
                # Calculate cluster center
                center_lat = sum(p[0] for p in cluster_points) / len(cluster_points)
                center_lon = sum(p[1] for p in cluster_points) / len(cluster_points)
                
                # Calculate effective radius
                max_distance = max(
                    self._haversine_distance(center_lat, center_lon, p[0], p[1])
                    for p in cluster_points
                )
                
                # Get content IDs for this cluster
                content_ids = []
                for point in cluster_points:
                    for loc in coords_locations:
                        if abs(loc.latitude - point[0]) < 0.001 and abs(loc.longitude - point[1]) < 0.001:
                            key = self._location_to_key(loc)
                            content_ids.extend(self.location_content_map.get(key, []))
                
                # Calculate risk concentration
                risk_scores = []
                # Would need access to video risk scores here
                
                cluster = GeographicCluster(
                    cluster_id=f"geo_cluster_{len(clusters)+1}",
                    center_lat=center_lat,
                    center_lon=center_lon,
                    radius_km=max(max_distance, 1.0),
                    content_count=len(content_ids),
                    unique_authors=len(set(content_ids)),  # Simplified
                    primary_location=loc.place_name,
                    risk_concentration=0.0,  # Would calculate from actual data
                    content_ids=content_ids
                )
                
                clusters.append(cluster)
                processed.add(i)
        
        self.geo_clusters = clusters
        return clusters

    def generate_heatmap_data(
        self,
        category_filter: Optional[str] = None,
        normalize: bool = True
    ) -> List[HeatmapPoint]:
        """Generate heatmap points for visualization."""
        points = []
        
        # Group by location
        location_counts = defaultdict(int)
        location_risk = defaultdict(list)
        
        for loc in self.locations:
            if loc.has_coordinates():
                key = f"{loc.latitude:.4f},{loc.longitude:.4f}"
                location_counts[key] += 1
        
        # Create heatmap points
        max_count = max(location_counts.values()) if location_counts else 1
        
        for key, count in location_counts.items():
            lat_str, lon_str = key.split(",")
            lat = float(lat_str)
            lon = float(lon_str)
            
            intensity = count / max_count if normalize and max_count > 0 else count
            
            points.append(HeatmapPoint(
                latitude=lat,
                longitude=lon,
                intensity=intensity,
                category=category_filter or "content_density",
                metadata={"count": count}
            ))
        
        return points

    def analyze_visual_context(
        self,
        image_path: str,
        video_id: str
    ) -> List[VisualContext]:
        """Analyze visual elements in an image for geographic context."""
        contexts = []
        
        # Placeholder - would use computer vision models in production
        # Examples: landmark detection, text recognition for signs, license plate reading
        
        # Simulated analysis
        contexts.append(VisualContext(
            element_type="analysis_status",
            description="Visual context analysis requires ML models",
            location_hints=[],
            confidence=0.0
        ))
        
        self.visual_contexts[video_id] = contexts
        return contexts

    def export_geo_report(self) -> Dict[str, Any]:
        """Export comprehensive geospatial analysis report."""
        if not self.geo_clusters:
            self.cluster_geographic_points()
        
        heatmap_data = self.generate_heatmap_data()
        
        # Country distribution
        country_dist = defaultdict(int)
        for loc in self.locations:
            if loc.country:
                country_dist[loc.country] += 1
        
        # Location type distribution
        type_dist = defaultdict(int)
        for loc in self.locations:
            type_dist[loc.location_type.value] += 1
        
        return {
            "summary": {
                "total_locations_extracted": len(self.locations),
                "locations_with_coordinates": sum(1 for loc in self.locations if loc.has_coordinates()),
                "geographic_clusters": len(self.geo_clusters),
                "countries_represented": len(country_dist),
                "analysis_timestamp": datetime.now().isoformat()
            },
            "country_distribution": dict(country_dist),
            "location_type_distribution": dict(type_dist),
            "clusters": [c.to_dict() for c in self.geo_clusters],
            "heatmap_data": [
                {"lat": p.latitude, "lon": p.longitude, "intensity": p.intensity, "category": p.category}
                for p in heatmap_data
            ],
            "sample_locations": [loc.to_dict() for loc in self.locations[:50]]
        }

    def _location_to_key(self, location: GeoLocation) -> str:
        """Generate unique key for location."""
        if location.has_coordinates():
            return f"{location.latitude:.4f},{location.longitude:.4f}"
        elif location.place_name:
            return f"place:{location.place_name.lower()}"
        else:
            return hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:16]

    def _infer_country(self, place_name: str) -> Optional[str]:
        """Infer country from place name."""
        place_lower = place_name.lower()
        
        # Known city-country mappings
        city_countries = {
            "jakarta": "Indonesia", "bandung": "Indonesia", "surabaya": "Indonesia",
            "kuala lumpur": "Malaysia", "johor": "Malaysia", "penang": "Malaysia",
            "bangkok": "Thailand", "chiang mai": "Thailand",
            "manila": "Philippines", "cebu": "Philippines",
            "ho chi minh": "Vietnam", "hanoi": "Vietnam",
            "singapore": "Singapore"
        }
        
        return city_countries.get(place_lower)

    def _get_approximate_coords(self, place_name: str) -> Tuple[Optional[float], Optional[float]]:
        """Get approximate coordinates for a place name."""
        # Simplified coordinate lookup (would use geocoding API in production)
        coords = {
            "jakarta": (-6.2088, 106.8456),
            "bandung": (-6.9175, 107.6191),
            "surabaya": (-7.2575, 112.7521),
            "kuala lumpur": (3.1390, 101.6869),
            "bangkok": (13.7563, 100.5018),
            "manila": (14.5995, 120.9842),
            "ho chi minh": (10.8231, 106.6297),
            "singapore": (1.3521, 103.8198),
        }
        
        return coords.get(place_name.lower(), (None, None))

    def _haversine_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two points in kilometers."""
        import math
        
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
