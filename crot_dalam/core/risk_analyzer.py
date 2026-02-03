#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CROT DALAM — Risk Analyzer Module
Multi-language scam/phishing risk detection with ML-ready architecture.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Set
from enum import Enum


class RiskLevel(Enum):
    """Risk classification levels."""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class RiskMatch:
    """Represents a single risk indicator match."""
    term: str
    category: str
    language: str
    weight: float = 1.0
    context: Optional[str] = None


@dataclass
class RiskResult:
    """Complete risk analysis result."""
    score: int
    level: RiskLevel
    matches: List[RiskMatch]
    categories: Dict[str, int]
    extracted_entities: Dict[str, List[str]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level.name,
            "matches": [
                {"term": m.term, "category": m.category, "language": m.language}
                for m in self.matches
            ],
            "categories": self.categories,
            "extracted_entities": self.extracted_entities,
        }


class RiskAnalyzer:
    """
    Multi-language risk analyzer for TikTok content.
    Detects scam, phishing, and fraud indicators.
    """
    
    # Risk term categories with weights
    RISK_TERMS: Dict[str, Dict[str, List[Tuple[str, float]]]] = {
        "indonesian": {
            "financial_scam": [
                ("undian berhadiah", 2.0),
                ("hadiah langsung", 1.5),
                ("menang undian", 2.0),
                ("hadiah cair", 1.5),
                ("bagi-bagi saldo", 2.0),
                ("saldo dana gratis", 2.0),
                ("saldo gopay gratis", 2.0),
                ("saldo ovo gratis", 2.0),
                ("transfer dulu", 3.0),
                ("biaya admin dulu", 3.0),
                ("bayar dulu", 2.5),
                ("dp dulu", 2.0),
            ],
            "investment_fraud": [
                ("investasi cepat", 2.5),
                ("cuan cepat", 2.0),
                ("profit harian", 2.5),
                ("dijamin profit", 3.0),
                ("untung besar", 1.5),
                ("modal kecil untung besar", 2.5),
                ("trading forex", 1.0),
                ("trading binary", 2.0),
            ],
            "gambling": [
                ("slot gacor", 2.5),
                ("slot online", 2.0),
                ("judi online", 2.5),
                ("togel", 2.0),
                ("deposit via dm", 2.5),
                ("deposit via link", 2.0),
                ("wd cepat", 1.5),
            ],
            "loan_scam": [
                ("pinjol cair", 2.0),
                ("pinjaman tanpa agunan", 1.5),
                ("pinjaman cepat cair", 2.0),
                ("dana tunai", 1.0),
                ("syarat mudah", 1.0),
            ],
            "job_scam": [
                ("kerja dari rumah gaji", 2.0),
                ("kerja online tanpa modal", 2.5),
                ("penghasilan sampingan", 1.0),
                ("income pasif", 1.5),
                ("kerja mudah gaji besar", 2.5),
                ("lowongan kerja online", 1.0),
            ],
            "contact_urgency": [
                ("WA admin", 1.5),
                ("hubungi admin", 1.5),
                ("dm admin", 1.5),
                ("langsung chat admin", 2.0),
                ("chat sekarang", 1.0),
                ("segera hubungi", 1.5),
            ],
            "fake_business": [
                ("reseller resmi", 1.0),
                ("agen resmi", 1.0),
                ("distributor resmi", 1.0),
                ("rekening penampung", 2.5),
                ("kode rahasia", 2.0),
                ("terbatas", 1.0),
            ],
        },
        "english": {
            "crypto_scam": [
                ("airdrop", 1.5),
                ("claim reward", 2.0),
                ("verify wallet", 2.5),
                ("seed phrase", 3.0),
                ("private key", 3.0),
                ("connect wallet", 2.0),
                ("crypto double", 2.5),
                ("send first", 2.5),
                ("bitcoin giveaway", 2.5),
            ],
            "exchange_scam": [
                ("binance bonus", 2.0),
                ("okx bonus", 2.0),
                ("bybit bonus", 2.0),
                ("coinbase bonus", 2.0),
                ("exchange bonus", 2.0),
            ],
            "giveaway_scam": [
                ("free giveaway", 2.0),
                ("claim free", 2.0),
                ("limited slots", 2.0),
                ("act fast", 1.5),
                ("limited time offer", 1.5),
                ("exclusive offer", 1.5),
            ],
            "investment_fraud": [
                ("investment 100% profit", 3.0),
                ("guaranteed returns", 2.5),
                ("double your money", 3.0),
                ("passive income", 1.0),
                ("financial freedom", 1.0),
                ("get rich quick", 2.5),
            ],
            "payment_scam": [
                ("processing fee", 2.0),
                ("admin fee", 2.0),
                ("payment upfront", 2.5),
                ("small fee required", 2.0),
                ("pay to claim", 2.5),
            ],
        },
        "malay": {
            "financial_scam": [
                ("hadiah percuma", 2.0),
                ("menang loteri", 2.0),
                ("wang tunai percuma", 2.0),
                ("bayar dahulu", 2.5),
                ("fi pemprosesan", 2.0),
            ],
            "job_scam": [
                ("kerja dari rumah", 1.5),
                ("pendapatan tambahan", 1.0),
                ("gaji tinggi", 1.5),
            ],
        },
        "vietnamese": {
            "financial_scam": [
                ("trúng thưởng", 2.0),
                ("nhận thưởng", 2.0),
                ("tiền thưởng miễn phí", 2.0),
                ("thanh toán trước", 2.5),
                ("phí xử lý", 2.0),
            ],
            "investment_fraud": [
                ("đầu tư sinh lời", 2.0),
                ("lợi nhuận cao", 2.0),
                ("kiếm tiền online", 1.5),
            ],
        },
        "thai": {
            "financial_scam": [
                ("ถูกรางวัล", 2.0),
                ("รับเงินฟรี", 2.0),
                ("โอนเงินก่อน", 2.5),
                ("ค่าธรรมเนียม", 1.5),
            ],
            "gambling": [
                ("สล็อตเว็บตรง", 2.0),
                ("คาสิโนออนไลน์", 2.0),
                ("แทงบอล", 1.5),
            ],
        },
        "filipino": {
            "financial_scam": [
                ("libre Regalo", 2.0),
                ("nanalo ng premyo", 2.0),
                ("pera muna", 2.5),
                ("bayad muna", 2.5),
            ],
            "job_scam": [
                ("trabaho sa bahay", 1.5),
                ("kumita ng pera", 1.0),
                ("malaking kita", 1.5),
            ],
        },
    }
    
    # Entity extraction patterns
    ENTITY_PATTERNS: Dict[str, re.Pattern] = {
        "phone_id": re.compile(r"\b(\+?62|0)8\d{8,12}\b"),
        "phone_intl": re.compile(r"\+\d{10,15}\b"),
        "btc_wallet": re.compile(r"\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}\b"),
        "eth_wallet": re.compile(r"\b0x[0-9A-Fa-f]{40}\b"),
        "trx_wallet": re.compile(r"\bT[a-zA-Z0-9]{33}\b"),
        "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        "telegram": re.compile(r"(?:t\.me/|@)([a-zA-Z0-9_]{5,32})", re.IGNORECASE),
        "whatsapp": re.compile(r"wa\.me/(\d+)", re.IGNORECASE),
        "url": re.compile(r"https?://[^\s\"'<>]+"),
        "short_url": re.compile(r"\b(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|ow\.ly)/[a-zA-Z0-9]+", re.IGNORECASE),
    }
    
    # Amplifier patterns (increase score significantly)
    AMPLIFIERS: List[Tuple[str, float]] = [
        ("transfer dulu", 3.0),
        ("seed phrase", 3.0),
        ("private key", 3.0),
        ("biaya admin dulu", 3.0),
        ("bayar duluan", 2.5),
        ("kirim uang", 2.5),
        ("send first", 2.5),
        ("pay upfront", 2.5),
    ]
    
    def __init__(
        self,
        languages: Optional[List[str]] = None,
        custom_terms: Optional[Dict[str, List[Tuple[str, float]]]] = None,
        sensitivity: float = 1.0,
    ):
        """
        Initialize risk analyzer.
        
        Args:
            languages: List of language codes to check (None = all)
            custom_terms: Additional custom risk terms
            sensitivity: Multiplier for final score (higher = more sensitive)
        """
        self.languages = languages or list(self.RISK_TERMS.keys())
        self.custom_terms = custom_terms or {}
        self.sensitivity = sensitivity
    
    def analyze(self, text: Optional[str]) -> RiskResult:
        """
        Analyze text for risk indicators.
        
        Args:
            text: The text content to analyze
            
        Returns:
            RiskResult with score, level, matches, and extracted entities
        """
        if not text:
            return RiskResult(
                score=0,
                level=RiskLevel.NONE,
                matches=[],
                categories={},
                extracted_entities={},
            )
        
        text_lower = text.lower()
        matches: List[RiskMatch] = []
        categories: Dict[str, int] = {}
        seen_terms: Set[str] = set()
        
        # Check risk terms by language
        for lang in self.languages:
            if lang not in self.RISK_TERMS:
                continue
            
            for category, terms in self.RISK_TERMS[lang].items():
                for term, weight in terms:
                    if term in text_lower and term not in seen_terms:
                        seen_terms.add(term)
                        matches.append(RiskMatch(
                            term=term,
                            category=category,
                            language=lang,
                            weight=weight,
                        ))
                        categories[category] = categories.get(category, 0) + 1
        
        # Check custom terms
        for category, terms in self.custom_terms.items():
            for term, weight in terms:
                if term.lower() in text_lower and term.lower() not in seen_terms:
                    seen_terms.add(term.lower())
                    matches.append(RiskMatch(
                        term=term,
                        category=category,
                        language="custom",
                        weight=weight,
                    ))
                    categories[category] = categories.get(category, 0) + 1
        
        # Extract entities
        entities = self._extract_entities(text)
        
        # Add entity-based risk
        entity_risk = 0
        if entities.get("btc_wallet"):
            entity_risk += 2
        if entities.get("eth_wallet"):
            entity_risk += 2
        if entities.get("trx_wallet"):
            entity_risk += 2
        if entities.get("short_url"):
            entity_risk += 1.5
        if entities.get("telegram") or entities.get("whatsapp"):
            entity_risk += 0.5
        
        # Calculate base score
        base_score = sum(m.weight for m in matches) + entity_risk
        
        # Apply amplifiers
        amplifier_bonus = 0
        for amp_term, amp_weight in self.AMPLIFIERS:
            if amp_term in text_lower:
                amplifier_bonus += amp_weight
        
        # Final score with sensitivity
        final_score = int((base_score + amplifier_bonus) * self.sensitivity)
        
        # Determine risk level
        level = self._score_to_level(final_score)
        
        return RiskResult(
            score=final_score,
            level=level,
            matches=matches,
            categories=categories,
            extracted_entities=entities,
        )
    
    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract suspicious entities from text."""
        entities: Dict[str, List[str]] = {}
        
        for entity_type, pattern in self.ENTITY_PATTERNS.items():
            found = pattern.findall(text)
            if found:
                # Flatten tuples if pattern has groups
                if found and isinstance(found[0], tuple):
                    found = [item for tup in found for item in tup if item]
                entities[entity_type] = list(set(found))
        
        return entities
    
    def _score_to_level(self, score: int) -> RiskLevel:
        """Convert numeric score to risk level."""
        if score == 0:
            return RiskLevel.NONE
        elif score <= 2:
            return RiskLevel.LOW
        elif score <= 5:
            return RiskLevel.MEDIUM
        elif score <= 10:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    def analyze_batch(self, texts: List[str]) -> List[RiskResult]:
        """Analyze multiple texts."""
        return [self.analyze(text) for text in texts]
    
    def add_custom_terms(self, category: str, terms: List[Tuple[str, float]]) -> None:
        """Add custom risk terms at runtime."""
        if category not in self.custom_terms:
            self.custom_terms[category] = []
        self.custom_terms[category].extend(terms)
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages."""
        return list(self.RISK_TERMS.keys())
    
    def get_categories(self) -> Dict[str, List[str]]:
        """Get all categories by language."""
        result: Dict[str, List[str]] = {}
        for lang, categories in self.RISK_TERMS.items():
            result[lang] = list(categories.keys())
        return result


# Sentiment analyzer for comments
class SentimentAnalyzer:
    """Simple sentiment analysis for comments."""
    
    POSITIVE_TERMS = {
        "en": ["love", "amazing", "great", "awesome", "best", "perfect", "excellent", "wonderful", "fantastic", "good"],
        "id": ["bagus", "mantap", "keren", "suka", "hebat", "luar biasa", "sempurna", "indah", "cantik", "baik"],
    }
    
    NEGATIVE_TERMS = {
        "en": ["scam", "fake", "fraud", "terrible", "worst", "bad", "hate", "awful", "horrible", "dangerous"],
        "id": ["penipuan", "palsu", "bohong", "jelek", "buruk", "tipu", "sampah", "berbahaya", "hoax", "benci"],
    }
    
    NEUTRAL_INDICATORS = ["ok", "okay", "fine", "average", "biasa", "lumayan"]
    
    @classmethod
    def analyze(cls, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text."""
        if not text:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0}
        
        text_lower = text.lower()
        
        positive_count = 0
        negative_count = 0
        
        for lang_terms in cls.POSITIVE_TERMS.values():
            for term in lang_terms:
                if term in text_lower:
                    positive_count += 1
        
        for lang_terms in cls.NEGATIVE_TERMS.values():
            for term in lang_terms:
                if term in text_lower:
                    negative_count += 1
        
        total = positive_count + negative_count
        if total == 0:
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.3}
        
        score = (positive_count - negative_count) / max(total, 1)
        
        if score > 0.2:
            sentiment = "positive"
        elif score < -0.2:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        confidence = min(1.0, total / 3)
        
        return {
            "sentiment": sentiment,
            "score": round(score, 2),
            "confidence": round(confidence, 2),
        }


# Convenience function
def quick_analyze(text: str) -> Tuple[int, List[str]]:
    """Quick risk analysis returning score and match terms."""
    analyzer = RiskAnalyzer()
    result = analyzer.analyze(text)
    terms = [m.term for m in result.matches]
    return result.score, terms
