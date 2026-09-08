"""Small bilingual lexicon sentiment baseline with three-token negation."""

import re
from ..config.keywords import POSITIVE_WORDS, NEGATIVE_WORDS, NEGATIONS
from ..config.patterns import TOKEN_PATTERN
from .common import rows, text_of


class SentimentAnalyzer:
    """Accept dict/list records; analyzes explicit text fields.

    Sentence punctuation resets negation. Score is signed matched-token
    average (-1..1), not a calibrated probability; unmatched text is unknown.
    """

    def analyze(self, data):
        output = []
        all_polarities = []
        for value in rows(data):
            evidence = []
            for sentence in re.split(r"[.!?;\n]+", text_of(value).casefold()):
                tokens = re.findall(TOKEN_PATTERN, sentence)
                for i, token in enumerate(tokens):
                    polarity = 1 if token in POSITIVE_WORDS else -1 if token in NEGATIVE_WORDS else 0
                    if not polarity:
                        continue
                    negated = sum(t in NEGATIONS for t in tokens[max(0, i - 3):i]) % 2 == 1
                    if negated:
                        polarity *= -1
                    evidence.append({"token": token, "polarity": polarity, "negated": negated})
            polarities = [e["polarity"] for e in evidence]
            all_polarities.extend(polarities)
            score = sum(polarities) / len(polarities) if polarities else None
            label = "unknown" if score is None else "positive" if score > 0.1 else "negative" if score < -0.1 else "mixed_or_neutral"
            output.append({"score": score, "label": label, "evidence": evidence})
        return {"records": output, "score": sum(all_polarities) / len(all_polarities) if all_polarities else None,
                "matched_tokens": len(all_polarities), "method": "bilingual_lexicon",
                "uncertainty": ["Limited English/Indonesian vocabulary; sarcasm, slang and long-distance negation are not resolved."]}
