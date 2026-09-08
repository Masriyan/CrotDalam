"""Offline patterns. No signatures, private endpoints, or predictive claims."""

USERNAME_PATTERN = r"[A-Za-z0-9_.]{1,24}"
VIDEO_PATH_PATTERN = r"/@([A-Za-z0-9_.]{1,24})/video/([0-9]{5,30})/?"
URL_PATTERN = r"https?://[^\s<>\"']+"
TOKEN_PATTERN = r"[^\W_]+"
SENSITIVE_URL_WORDS = frozenset(("login", "verify", "password", "wallet", "signin", "otp", "seed", "verifikasi"))
