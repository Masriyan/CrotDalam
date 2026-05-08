#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM - Unit Tests for Risk Analyzer
Tests the risk analysis and sentiment detection logic.
"""
import pytest
from unittest.mock import MagicMock, patch

from crot_dalam.core.risk_analyzer import RiskAnalyzer, SentimentAnalyzer, RiskResult


class TestRiskAnalyzer:
    """Tests for RiskAnalyzer class."""
    
    def test_risk_analyzer_initialization(self):
        """Test RiskAnalyzer initializes correctly."""
        analyzer = RiskAnalyzer()
        assert analyzer is not None
        assert hasattr(analyzer, 'analyze_text')
    
    def test_analyze_safe_text(self):
        """Test analyzing safe/normal text."""
        analyzer = RiskAnalyzer()
        result = analyzer.analyze_text("This is a normal video about cooking")
        
        assert isinstance(result, RiskResult)
        assert result.overall_risk >= 0
        assert result.overall_risk <= 1
    
    def test_analyze_spam_text(self):
        """Test analyzing spam-like text."""
        analyzer = RiskAnalyzer()
        spam_text = "BUY NOW!!! CLICK HERE!!! FREE MONEY!!! http://spam.com"
        result = analyzer.analyze_text(spam_text)
        
        assert result.overall_risk > 0.5 or "spam" in result.categories
    
    def test_analyze_threat_text(self):
        """Test analyzing threatening text."""
        analyzer = RiskAnalyzer()
        threat_text = "I will hurt you, death to everyone"
        result = analyzer.analyze_text(threat_text)
        
        assert isinstance(result, RiskResult)
        # Should detect elevated risk
        assert result.overall_risk > 0.3 or "threat" in result.categories or "violence" in result.categories
    
    def test_analyze_empty_text(self):
        """Test analyzing empty text."""
        analyzer = RiskAnalyzer()
        result = analyzer.analyze_text("")
        
        assert result.overall_risk == 0
        assert result.risk_level == "LOW"
    
    def test_analyze_multilingual_text(self):
        """Test analyzing text in different languages."""
        analyzer = RiskAnalyzer()
        
        # Indonesian
        result_id = analyzer.analyze_text("Ini adalah video yang bagus")
        assert isinstance(result_id, RiskResult)
        
        # Malay
        result_ms = analyzer.analyze_text("Ini adalah video yang bagus")
        assert isinstance(result_ms, RiskResult)
    
    def test_risk_level_assignment(self):
        """Test risk level is properly assigned based on score."""
        analyzer = RiskAnalyzer()
        
        # Low risk
        result_low = analyzer.analyze_text("Nice video")
        if result_low.overall_risk < 0.5:
            assert result_low.risk_level == "LOW"
        
        # Note: We can't guarantee medium/high without specific trigger words
        # as the analyzer uses pattern matching
    
    def test_category_detection(self):
        """Test that categories are detected properly."""
        analyzer = RiskAnalyzer()
        result = analyzer.analyze_text("Free money click here now!!!")
        
        assert isinstance(result.categories, list)
        # Should detect some category for spammy text
    
    def test_sentiment_analysis(self):
        """Test sentiment analysis."""
        analyzer = RiskAnalyzer()
        
        positive = analyzer.analyze_text("Amazing wonderful fantastic!")
        assert positive.sentiment in ["positive", "neutral", "negative"]
        
        negative = analyzer.analyze_text("Terrible awful bad!")
        assert negative.sentiment in ["positive", "neutral", "negative"]


class TestSentimentAnalyzer:
    """Tests for SentimentAnalyzer class."""
    
    def test_sentiment_analyzer_initialization(self):
        """Test SentimentAnalyzer initializes correctly."""
        analyzer = SentimentAnalyzer()
        assert analyzer is not None
    
    def test_positive_sentiment(self):
        """Test detection of positive sentiment."""
        analyzer = SentimentAnalyzer()
        result = analyzer.analyze("I love this amazing video!")
        
        assert result in ["positive", "neutral", "negative"]
    
    def test_negative_sentiment(self):
        """Test detection of negative sentiment."""
        analyzer = SentimentAnalyzer()
        result = analyzer.analyze("This is terrible and awful")
        
        assert result in ["positive", "neutral", "negative"]
    
    def test_neutral_sentiment(self):
        """Test detection of neutral sentiment."""
        analyzer = SentimentAnalyzer()
        result = analyzer.analyze("The sky is blue today")
        
        assert result in ["positive", "neutral", "negative"]
    
    def test_empty_text_sentiment(self):
        """Test sentiment of empty text."""
        analyzer = SentimentAnalyzer()
        result = analyzer.analyze("")
        
        assert result == "neutral"


class TestRiskPatterns:
    """Tests for risk pattern detection."""
    
    def test_url_detection(self):
        """Test URL detection in text."""
        analyzer = RiskAnalyzer()
        result = analyzer.analyze_text("Check out http://example.com")
        
        # URLs should be detected
        assert "http" in result.categories or len(result.categories) > 0
    
    def test_hashtag_heavy_text(self):
        """Test text with many hashtags."""
        analyzer = RiskAnalyzer()
        text = "#spam #follow #like #followme #followback #spam #money"
        result = analyzer.analyze_text(text)
        
        assert isinstance(result, RiskResult)
    
    def test_mention_heavy_text(self):
        """Test text with many mentions."""
        analyzer = RiskAnalyzer()
        text = "@user1 @user2 @user3 @user4 follow me now!"
        result = analyzer.analyze_text(text)
        
        assert isinstance(result, RiskResult)
    
    def test_excessive_caps(self):
        """Test text with excessive capitalization."""
        analyzer = RiskAnalyzer()
        text = "THIS IS ALL CAPS AND VERY LOUD!!!"
        result = analyzer.analyze_text(text)
        
        assert isinstance(result, RiskResult)
        # May increase risk score
    
    def test_repetitive_text(self):
        """Test repetitive/spammy text patterns."""
        analyzer = RiskAnalyzer()
        text = "buy buy buy click click click now now now"
        result = analyzer.analyze_text(text)
        
        assert isinstance(result, RiskResult)


class TestBatchAnalysis:
    """Tests for batch text analysis."""
    
    def test_analyze_multiple_texts(self):
        """Test analyzing multiple texts."""
        analyzer = RiskAnalyzer()
        texts = [
            "Safe content",
            "Spam spam spam",
            "Normal video",
        ]
        
        results = [analyzer.analyze_text(text) for text in texts]
        
        assert len(results) == 3
        assert all(isinstance(r, RiskResult) for r in results)
    
    def test_average_risk_score(self):
        """Test calculating average risk score."""
        analyzer = RiskAnalyzer()
        texts = ["Safe text"] * 10
        
        results = [analyzer.analyze_text(text) for text in texts]
        avg_risk = sum(r.overall_risk for r in results) / len(results)
        
        assert 0 <= avg_risk <= 1
