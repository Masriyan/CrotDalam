"""Weighted bilingual scam indicators, not a fraud determination."""

import re
from ..config.keywords import SCAM_SIGNALS
from .common import rows, text_of, risk_result


class ScamDetector:
    """analyze(record:dict) -> score 0..100, evidence and uncertainty.

    Each indicator category contributes once, irrespective of repetition.
    Credential requests plus prize/advance-fee bait add a 15-point interaction.
    Quotes, reporting, satire and negation can produce false positives.
    """

    def analyze(self, data):
        if not isinstance(data, dict):
            raise ValueError("ScamDetector requires one record dictionary")
        text = text_of(rows(data)[0]).casefold()
        evidence = []
        score = 0
        for name, (weight, phrases) in SCAM_SIGNALS.items():
            matches = [phrase for phrase in phrases if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text)]
            if matches:
                score += weight
                evidence.append({"signal": name, "weight": weight, "matches": matches})
        names = {e["signal"] for e in evidence}
        if "credential_request" in names and names & {"prize_bait", "advance_fee"}:
            score += 15
            evidence.append({"signal": "credential_bait_combination", "weight": 15})
        uncertainty = ["Indicators are not proof of fraud; quoted or educational content may match.",
                       "Identity, transaction history and intent are not verified."]
        if not text.strip():
            uncertainty.append("No supported text fields supplied; low score does not establish safety.")
        return risk_result(score, evidence, uncertainty)
