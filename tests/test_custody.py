"""Chain-of-custody: source hashing, collected_at, and tamper evidence."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crotdalam.collectors.har_collector import import_har, _collected_at
from crotdalam.utils.crypto import generate_key
from crotdalam.utils.database import Database


def entry(payload, started="2026-09-08T04:49:52.393Z"):
    body = json.dumps(payload)
    return {"startedDateTime": started,
            "request": {"method": "GET", "url": "https://www.tiktok.com/api/post/item_list/"},
            "response": {"status": 200, "content": {"mimeType": "application/json", "text": body}}}


class CollectedAtTests(unittest.TestCase):
    def test_parses_aware_and_rejects_naive(self):
        self.assertEqual(_collected_at("2026-09-08T04:49:52.393Z"), "2026-09-08T04:49:52.393000Z")
        self.assertIsNone(_collected_at("2026-09-08T04:49:52"))       # naive
        self.assertIsNone(_collected_at("not a date"))
        self.assertIsNone(_collected_at(None))


class SourceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "capture.har"
        video = {"id": "1", "desc": "x", "createTime": 111, "video": {"duration": 5},
                 "author": {"id": "9", "uniqueId": "u"}, "stats": {"diggCount": 1}}
        self.path.write_text(json.dumps({"log": {"entries": [entry({"itemList": [video]})]}}))

    def test_record_carries_source_hash_and_collected_at(self):
        records, summary = import_har(self.path)
        record = records[0]
        self.assertEqual(record["collected_at"], "2026-09-08T04:49:52.393000Z")
        self.assertEqual(record["provenance"]["source_name"], "capture.har")
        self.assertEqual(len(record["provenance"]["source_sha256"]), 64)
        self.assertEqual(summary["source"]["sha256"], record["provenance"]["source_sha256"])

    def test_source_hash_matches_file_contents(self):
        import hashlib
        expected = hashlib.sha256(self.path.read_bytes()).hexdigest()
        _, summary = import_har(self.path)
        self.assertEqual(summary["source"]["sha256"], expected)

    def test_missing_started_datetime_omits_collected_at(self):
        video = {"id": "2", "desc": "y", "video": {"duration": 5},
                 "author": {"id": "9", "uniqueId": "u"}, "stats": {"diggCount": 1}}
        e = entry({"itemList": [video]}); del e["startedDateTime"]
        self.path.write_text(json.dumps({"log": {"entries": [e]}}))
        records, _ = import_har(self.path)
        self.assertNotIn("collected_at", records[0])


class ChainOfCustodyTests(unittest.TestCase):
    def records(self):
        return [{"data_type": "video", "target": str(i), "value": {"id": str(i)},
                 "source_url": "https://www.tiktok.com/", "collected_at": "2026-09-08T04:00:00Z"}
                for i in range(10)]

    def _store(self, key=None):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = str(Path(self.temp.name) / "e.sqlite")
        db = Database(path, key)
        for r in self.records():
            db.store(r)
        db.close()
        return path

    def test_intact_chain_verifies(self):
        path = self._store()
        db = Database(path)
        try:
            seal = db.verify_chain()
        finally:
            db.close()
        self.assertTrue(seal["verified"])
        self.assertEqual(seal["records"], 10)
        self.assertFalse(seal["keyed"])

    def test_deletion_breaks_chain(self):
        path = self._store()
        con = sqlite3.connect(path); con.execute("DELETE FROM records WHERE id=5"); con.commit(); con.close()
        db = Database(path)
        try:
            with self.assertRaises(ValueError):
                db.verify_chain()
        finally:
            db.close()

    def test_metadata_edit_breaks_chain(self):
        path = self._store()
        con = sqlite3.connect(path)
        row = con.execute("SELECT id, metadata FROM records ORDER BY id LIMIT 1").fetchone()
        edited = row[1].replace('"target":"0"', '"target":"999"')
        self.assertNotEqual(edited, row[1])
        con.execute("UPDATE records SET metadata=? WHERE id=?", (edited, row[0])); con.commit(); con.close()
        db = Database(path)
        try:
            with self.assertRaises(ValueError):
                db.verify_chain()
        finally:
            db.close()

    def test_keyed_chain_is_hmac(self):
        key = generate_key()
        path = self._store(key)
        db = Database(path, key)
        try:
            self.assertTrue(db.verify_chain()["keyed"])
        finally:
            db.close()

    def test_reopen_and_append_continues_chain(self):
        path = self._store()
        db = Database(path)
        try:
            db.store({"data_type": "video", "target": "z", "value": {"id": "z"}})
            self.assertEqual(db.verify_chain()["records"], 11)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
