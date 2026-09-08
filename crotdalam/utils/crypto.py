"""AES-256-GCM authenticated encryption; SHA256 alone is not authentication.

Hashes describe plaintext canonical values and remain visible in the database.
They reveal equality and can permit guessing low-entropy values. GCM authenticates
encrypted values/state, but does not provide whole-database tamper evidence.
"""

import base64
import hmac
import os

from .helpers import sha256_value


def generate_key() -> str:
    return base64.b64encode(os.urandom(32)).decode("ascii")


def decode_key(key: str) -> bytes:
    try:
        decoded = base64.b64decode(key, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("key must be standard base64 encoding of 32 bytes") from exc
    if len(decoded) != 32:
        raise ValueError("AES-256 requires a 32-byte key")
    return decoded


def encrypt(data: bytes, key: str, *, aad: bytes = b"") -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    ciphertext = AESGCM(decode_key(key)).encrypt(nonce, data, aad)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt(data: str, key: str, *, aad: bytes = b"") -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    payload = base64.b64decode(data, validate=True)
    if len(payload) < 28:
        raise ValueError("invalid encrypted payload")
    return AESGCM(decode_key(key)).decrypt(payload[:12], payload[12:], aad)


def verify_hash(value: object, expected: str) -> bool:
    return isinstance(expected, str) and hmac.compare_digest(
        sha256_value(value).encode("ascii"), expected.encode("utf-8"))
