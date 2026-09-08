"""Redaction for application log handlers, including formatted exceptions."""

import logging
import re


def redact(text: str) -> str:
    text = re.sub(r"(?i)(https?|socks[45]h?)://[^\s/]*@", r"\1://[REDACTED]@", text)
    text = re.sub(r"(?im)\b(authorization|proxy-authorization|cookie|set-cookie)\s*[:=][^\r\n]*",
                  r"\1: [REDACTED]", text)
    text = re.sub(r"(?i)\bBearer\s+[^\s,;]+", "Bearer [REDACTED]", text)
    return re.sub(r"(?i)([\"']?(?:[\w-]*token|api[_-]?key|password|secret|sessionid|cookie)[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s&,;}]+)",
                  r"\1[REDACTED]", text)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def get_logger(name: str = "crotdalam") -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(getattr(handler, "_crotdalam_redacted", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler._crotdalam_redacted = True
        logger.addHandler(handler)
    logger.propagate = False
    return logger
