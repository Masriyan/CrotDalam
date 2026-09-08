"""SQLite record/state storage.

Only value and state payloads are encrypted. Metadata and plaintext SHA256
checksums are visible. Checksums detect accidental value corruption, not malicious
rewriting. Existing parent permissions are left unchanged; new parents are 0700.
Each operation is transactional; a monitor check is not a multi-process CAS.
"""

import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
from threading import RLock
from collections.abc import Iterator

from .crypto import decode_key, decrypt, encrypt, verify_hash
from .helpers import canonical_json, sha256_value, utc_now
from .models import validate_record


class Database:
    def __init__(self, path: str, encryption_key: str | None = None):
        self._key = encryption_key
        self._lock = RLock()
        if encryption_key is not None:
            decode_key(encryption_key)
        if path != ":memory:":
            destination = Path(path).expanduser().absolute()
            missing = []
            parent = destination.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir(mode=0o700, exist_ok=True)
            flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(destination, flags, 0o600)
            try:
                os.fchmod(fd, 0o600)
            finally:
                os.close(fd)
            path = str(destination)
        self._conn = sqlite3.connect(path, timeout=5, check_same_thread=False)
        try:
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.execute("PRAGMA journal_mode=WAL")
            with self._conn:
                self._conn.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                self._conn.execute("CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, metadata TEXT NOT NULL, value TEXT NOT NULL)")
                self._conn.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                mode = "aes256gcm" if self._key is not None else "plain"
                self._conn.execute("INSERT OR IGNORE INTO metadata VALUES (?, ?)", ("mode", mode))
                actual = self._conn.execute("SELECT value FROM metadata WHERE key=?", ("mode",)).fetchone()[0]
                if actual != mode:
                    raise ValueError("database encryption mode does not match supplied key")
                if self._key is not None:
                    self._conn.execute("INSERT OR IGNORE INTO metadata VALUES (?, ?)",
                                       ("key_check", encrypt(b"crotdalam", self._key, aad=b"key_check")))
                    check = self._conn.execute("SELECT value FROM metadata WHERE key=?", ("key_check",)).fetchone()[0]
                    if decrypt(check, self._key, aad=b"key_check") != b"crotdalam":
                        raise ValueError("invalid key check")
                # Seal the record log so deletion, truncation or reordering is
                # detectable. Keyed (HMAC) when encrypted, so rebuilding the
                # chain requires the key; a bare hash otherwise.
                self._conn.execute("INSERT OR IGNORE INTO metadata VALUES (?, ?)", ("chain_head", self._genesis()))
        except BaseException:
            self._conn.close()
            raise

    def _genesis(self) -> str:
        return hashlib.sha256(b"crotdalam-chain-v1|" + (b"aes256gcm" if self._key else b"plain")).hexdigest()

    def _chain_step(self, previous: str, aad: bytes) -> str:
        message = previous.encode("ascii") + b"|" + aad
        if self._key is not None:
            return hmac.new(decode_key(self._key), message, hashlib.sha256).hexdigest()
        return hashlib.sha256(message).hexdigest()

    def _encode(self, value: dict, aad: bytes) -> str:
        raw = canonical_json(value)
        return encrypt(raw, self._key, aad=aad) if self._key is not None else raw.decode("utf-8")

    def _decode(self, value: str, aad: bytes) -> dict:
        raw = decrypt(value, self._key, aad=aad) if self._key is not None else value
        return json.loads(raw)

    def store(self, record: dict) -> dict:
        validate_record(record)
        result = json.loads(canonical_json(record))
        result.setdefault("timestamp", utc_now())
        result["sha256"] = sha256_value(result["value"])
        metadata = {k: v for k, v in result.items() if k != "value"}
        aad = canonical_json(metadata)
        payload = self._encode(result["value"], aad)
        with self._lock, self._conn:
            head = self._conn.execute("SELECT value FROM metadata WHERE key=?", ("chain_head",)).fetchone()[0]
            self._conn.execute("INSERT INTO records (metadata, value) VALUES (?, ?)",
                               (aad.decode("utf-8"), payload))
            self._conn.execute("UPDATE metadata SET value=? WHERE key=?", (self._chain_step(head, aad), "chain_head"))
        return result

    def verify_chain(self) -> dict:
        """Recompute the seal over every record and compare to the stored head.

        Detects deletion, truncation, reordering and metadata edits. In plain
        (unencrypted) mode an editor with write access can rebuild the chain;
        in keyed mode that requires the encryption key. Also re-verifies each
        record's value checksum, so a decoded value is always consistent.
        """
        with self._lock:
            stored = self._conn.execute("SELECT value FROM metadata WHERE key=?", ("chain_head",)).fetchone()
            rows = self._conn.execute("SELECT id, metadata, value FROM records ORDER BY id").fetchall()
        head = self._genesis()
        for _, metadata, payload in rows:
            record = json.loads(metadata)
            value = self._decode(payload, metadata.encode("utf-8"))
            if not verify_hash(value, record["sha256"]):
                raise ValueError("record checksum mismatch")
            head = self._chain_step(head, metadata.encode("utf-8"))
        expected = stored[0] if stored else self._genesis()
        if not hmac.compare_digest(head, expected):
            raise ValueError("evidence chain broken: records were deleted, reordered or altered")
        return {"records": len(rows), "chain_head": head, "verified": True,
                "keyed": self._key is not None}

    def records(self) -> Iterator[dict]:
        # Bound iteration to the initial high-water mark, without a long read lock.
        with self._lock:
            maximum = self._conn.execute("SELECT COALESCE(MAX(id), 0) FROM records").fetchone()[0]
        last = 0
        while last < maximum:
            with self._lock:
                rows = self._conn.execute("SELECT id, metadata, value FROM records WHERE id>? AND id<=? ORDER BY id LIMIT ?",
                                          (last, maximum, 256)).fetchall()
            if not rows:
                break
            for last, metadata, payload in rows:
                record = json.loads(metadata)
                record["value"] = self._decode(payload, metadata.encode("utf-8"))
                if not verify_hash(record["value"], record["sha256"]):
                    raise ValueError("record checksum mismatch")
                yield record

    def get_state(self, key: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return None if row is None else self._decode(row[0], ("state:" + key).encode())

    def set_state(self, key: str, value: dict) -> None:
        if not isinstance(value, dict):
            raise ValueError("state must be a dictionary")
        payload = self._encode(value, ("state:" + key).encode())
        with self._lock, self._conn:
            self._conn.execute("INSERT INTO state VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, payload))

    def close(self) -> None:
        with self._lock:
            self._conn.close()
