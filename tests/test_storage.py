import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import tempfile
import unittest

from crotdalam.utils.database import Database
from crotdalam.utils.crypto import generate_key, encrypt, decrypt, verify_hash
from crotdalam.utils.helpers import sha256_value
from crotdalam.utils.validators import validate_username, validate_tiktok_url
from crotdalam.utils.geo import validate_coordinates
from crotdalam.utils.logger import RedactingFormatter, redact


class StorageTests(unittest.TestCase):
    def test_roundtrip_permissions_wal_and_state(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "private" / "nested" / "db.sqlite"
            db = Database(str(path))
            self.addCleanup(db.close)
            record = {"data_type": "profile", "target": "x'; DROP TABLE state;--", "value": {"z": "é", "a": 3}}
            stored = db.store(record)
            self.assertNotIn("timestamp", record)
            self.assertTrue(stored["timestamp"].endswith("Z"))
            expected = hashlib.sha256(json.dumps(record["value"], sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            self.assertEqual(stored["sha256"], expected)
            self.assertEqual(list(db.records()), [stored])
            db.set_state(record["target"], {"n": 1})
            db.set_state(record["target"], {"n": 2})
            self.assertEqual(db.get_state(record["target"]), {"n": 2})
            self.assertIsNone(db.get_state("absent"))
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with sqlite3.connect(path) as conn:
                self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            other = Database(str(path))
            self.addCleanup(other.close)
            self.assertEqual(list(other.records()), [stored])

    def test_encryption_and_reopen(self):
        try:
            import cryptography
        except ImportError:
            self.skipTest("cryptography not installed")
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / "db")
            key = generate_key()
            db = Database(path, key)
            record = db.store({"data_type": "p", "target": "x", "value": {"secret": "sensitive-value"}})
            db.set_state("monitor", {"secret": "sensitive-state"})
            db.close()
            with sqlite3.connect(path) as conn:
                self.assertNotIn("sensitive-value", conn.execute("SELECT value FROM records").fetchone()[0])
                self.assertNotIn("sensitive-state", conn.execute("SELECT value FROM state").fetchone()[0])
            db = Database(path, key)
            self.addCleanup(db.close)
            self.assertEqual(list(db.records()), [record])
            self.assertEqual(db.get_state("monitor"), {"secret": "sensitive-state"})
            with self.assertRaises(ValueError):
                Database(path)
            from cryptography.exceptions import InvalidTag
            with self.assertRaises(InvalidTag):
                Database(path, generate_key())
            payload = encrypt(b"abc", key, aad=b"one")
            self.assertEqual(decrypt(payload, key, aad=b"one"), b"abc")
            with self.assertRaises(InvalidTag):
                decrypt(payload, key, aad=b"two")

    def test_invalid_and_hash(self):
        db = Database(":memory:")
        self.addCleanup(db.close)
        for value in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                db.store({"data_type": "x", "target": "y", "value": {"x": value}})
        self.assertTrue(verify_hash({"x": 1}, sha256_value({"x": 1})))
        self.assertFalse(verify_hash({"x": 2}, sha256_value({"x": 1})))

    def test_validation(self):
        self.assertEqual(validate_username("@valid.name"), "valid.name")
        for name in ("a.", "../x", "", "x" * 25):
            with self.assertRaises(ValueError):
                validate_username(name)
        self.assertEqual(validate_tiktok_url("https://www.tiktok.com/@a"), "https://www.tiktok.com/@a")
        for url in ("http://tiktok.com", "https://tiktok.com.evil.test", "https://u:p@tiktok.com", "https://127.0.0.1", "https://tiktok.com:444", "https://tiktok.com\\@evil.test", " https://tiktok.com", "https://tiktok.com./"):
            with self.assertRaises(ValueError):
                validate_tiktok_url(url)
        self.assertEqual(validate_coordinates(-90, 180), (-90.0, 180.0))
        for lat, lon in ((91, 0), (0, 181), (float("nan"), 0), (True, 0)):
            with self.assertRaises(ValueError):
                validate_coordinates(lat, lon)

    def test_redaction(self):
        text = redact("https://alice:password@proxy.test token=abc&x=1\nCookie: sessionid=xyz; other=hidden\nAuthorization: Bearer SECRET")
        for secret in ("alice", "password", "abc", "xyz", "hidden", "SECRET"):
            self.assertNotIn(secret, text)
        record = logging.LogRecord("test", 40, "", 1, "token=%s", ("very-secret",), None)
        self.assertNotIn("very-secret", RedactingFormatter().format(record))


if __name__ == "__main__":
    unittest.main()
