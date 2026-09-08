"""Offline lexical URL triage: no HTTP, DNS, reputation or arbitrary URL fetch."""

import ipaddress
import re
from urllib.parse import urlsplit, unquote
from ..config.patterns import URL_PATTERN, SENSITIVE_URL_WORDS
from .common import rows, text_of, risk_result


class PhishingDetector:
    """analyze(str|dict) accepts a URL/text or record with url/urls/content.

    At most 100 URLs, each <=4096 characters; aggregate score is the maximum
    individual URL score, not a sum across unrelated links. No brand claims.
    """

    def analyze(self, data):
        if isinstance(data, str):
            if len(data) > 100_000:
                raise ValueError("Input exceeds 100000 characters")
            candidates = re.findall(URL_PATTERN, data)
            if not candidates and data.strip():
                candidates = [data.strip()]
        elif isinstance(data, dict):
            value = rows(data)[0]
            candidates = re.findall(URL_PATTERN, text_of(value))
            if isinstance(value.get("url"), str):
                candidates.append(value["url"])
            if "urls" in value:
                if not isinstance(value["urls"], list) or not all(isinstance(v, str) for v in value["urls"]):
                    raise ValueError("urls must be a list of strings")
                candidates.extend(value["urls"])
            if not candidates and isinstance(data.get("source_url"), str):
                candidates.append(data["source_url"])
        else:
            raise ValueError("PhishingDetector accepts text or a dictionary")
        if len(candidates) > 100:
            raise ValueError("At most 100 URLs per analysis")
        results = []
        for url in dict.fromkeys(candidates):
            if len(url) > 4096:
                raise ValueError("URL exceeds 4096 characters")
            evidence = []
            try:
                parsed = urlsplit(url)
                host = parsed.hostname or ""
                port = parsed.port
                valid = bool(host and parsed.scheme.lower() in {"http", "https"} and not any(c.isspace() for c in url))
                ascii_host = host.encode("idna").decode("ascii")
            except (ValueError, UnicodeError):
                valid = False
            if not valid:
                results.append({"url": url, "valid": False, "score": None, "evidence": [], "error": "Malformed or non-HTTP(S) URL"})
                continue
            signals = []
            if parsed.scheme == "http":
                signals.append(("unencrypted_http", 10))
            if parsed.username is not None or parsed.password is not None:
                signals.append(("userinfo_obscures_host", 25))
            try:
                ipaddress.ip_address(host)
                signals.append(("literal_ip_host", 15))
            except ValueError:
                if len(ascii_host.split(".")) >= 5:
                    signals.append(("many_host_labels", 10))
            if any(label.startswith("xn--") for label in ascii_host.split(".")):
                signals.append(("internationalized_hostname", 10))
            if port not in (None, 80, 443):
                signals.append(("unusual_port", 5))
            tokens = set(re.findall(r"[a-z]+", unquote(parsed.path + " " + parsed.query).casefold()))
            if tokens & SENSITIVE_URL_WORDS:
                signals.append(("sensitive_action_words", 15))
            if len(url) > 200:
                signals.append(("long_url", 5))
            if "%" in parsed.netloc or "\\" in url:
                signals.append(("ambiguous_url_syntax", 20))
            evidence.extend({"signal": name, "weight": weight} for name, weight in signals)
            results.append({"url": url, "host": host, "valid": True,
                            "score": min(100, sum(w for _, w in signals)), "evidence": evidence})
        valid_scores = [r["score"] for r in results if r["valid"]]
        result = risk_result(max(valid_scores, default=0),
                             [dict(e, url=r["url"]) for r in results for e in r["evidence"]],
                             ["Lexical signals also occur on legitimate URLs; HTTPS does not establish safety.",
                              "No URL was fetched; DNS, redirects, reputation and page content are unknown."])
        result.update({"urls": results, "assessed_urls": len(valid_scores), "status": "assessed" if valid_scores else "insufficient_data"})
        return result
