import base64
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crotdalam.collectors.har_collector import import_har, sanitize_url
from crotdalam.ui.cli import main, load_records


def entry(payload=None, *, encoded=False, url="https://www.tiktok.com/api/post/item_list/?token=QUERY_SECRET"):
    content = {"mimeType": "application/json"}
    if payload is not None:
        text = json.dumps(payload)
        content["text"] = base64.b64encode(text.encode()).decode() if encoded else text
        if encoded:
            content["encoding"] = "base64"
    return {"request": {"method": "GET", "url": url,
                        "headers": [{"name": "Cookie", "value": "COOKIE_SECRET"}],
                        "postData": {"text": "POST_SECRET"}},
            "response": {"status": 200, "content": content,
                         "headers": [{"name": "Set-Cookie", "value": "RESPONSE_SECRET"}]}}


class HARTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "synthetic.har"
        self.video = {"id": "123", "desc": "PRIVATE_CAPTION", "createTime": 1234,
                      "video": {"duration": 15, "playAddr": "https://cdn.test/?token=MEDIA_SECRET"},
                      "author": {"id": "456", "uniqueId": "PRIVATE_USERNAME", "secUid": "SECUID_SECRET"},
                      "stats": {"playCount": 12, "token": "METRIC_SECRET"}, "token": "BODY_SECRET"}

    def write(self, entries):
        self.path.write_text(json.dumps({"log": {"entries": entries}}))

    def test_normalization_dedup_provenance_and_privacy(self):
        profile = {"id": "456", "uniqueId": "PRIVATE_USERNAME", "signature": "PRIVATE_BIO", "token": "BODY_SECRET"}
        comment = {"cid": "789", "text": "PRIVATE_COMMENT", "aweme_id": "123", "user": {"uid": "456", "nickname": "PRIVATE_NAME", "token": "BODY_SECRET"}}
        self.write([entry({"itemList": [self.video, self.video], "userInfo": {"user": profile, "stats": {"followerCount": 5}}, "comments": [comment]}, encoded=True),
                    entry({"UserModule": {"users": {"PRIVATE_USERNAME": profile}, "stats": {"PRIVATE_USERNAME": {"followerCount": 5}}}})])
        records, summary = import_har(self.path)
        self.assertEqual(summary["data_types"], {"video": 1, "profile": 1, "comment": 1})
        self.assertEqual(summary["duplicates"], 2)
        self.assertEqual(summary["body_availability"], {"json": 2})
        self.assertTrue(all(r["source_url"] == "https://www.tiktok.com/api/post/item_list/" for r in records))
        provenance = records[0]["provenance"]
        self.assertEqual(provenance["collector"], "har")
        self.assertEqual(provenance["entry_index"], 0)
        self.assertEqual(provenance["source_name"], "synthetic.har")
        self.assertEqual(len(provenance["source_sha256"]), 64)
        # Every record cites the same source file hash for this capture.
        self.assertEqual({r["provenance"]["source_sha256"] for r in records}, {provenance["source_sha256"]})
        self.assertEqual(summary["source"]["sha256"], provenance["source_sha256"])
        self.assertNotIn("SECRET", json.dumps(records))
        self.assertNotIn("PRIVATE", json.dumps(summary))
        self.assertNotIn("SECRET", json.dumps(summary))
        inspected, inspection = import_har(self.path, inspect_only=True)
        self.assertEqual(inspected, [])
        self.assertEqual(inspection, summary)

    def test_aliases_and_changed_content(self):
        changed = dict(self.video, desc="different")
        self.write([entry({"item_list": [self.video]}), entry({"items": [self.video, changed, {"id": "999"}]})])
        records, summary = import_har(self.path)
        self.assertEqual(len(records), 2)
        self.assertEqual(summary["duplicates"], 1)
        self.assertEqual(summary["rejected_candidates"], 1)

    def test_body_availability(self):
        entries = [entry(), entry(), entry(), entry(), entry(), entry()]
        contents = [e["response"]["content"] for e in entries]
        contents[1]["text"] = ""
        contents[2]["text"] = "<html>PRIVATE_BODY</html>"
        contents[3].update(text="!!!", encoding="base64")
        contents[4].update(text=base64.b64encode(b"not json").decode(), encoding="base64")
        contents[5].update(text="private", encoding="gzip")
        self.write(entries)
        records, summary = import_har(self.path)
        self.assertFalse(records)
        self.assertEqual(summary["body_availability"], {"missing": 1, "empty": 1, "opaque": 2, "invalid_base64": 1, "unsupported_encoding": 1})

    def test_redaction(self):
        for path in ("/@PRIVATE/video/123", "/user/PRIVATE/456", "/%40PRIVATE/video/%31%32%33"):
            url = sanitize_url("https://AUTH:SECRET@www.tiktok.com" + path + "?query=SECRET#SECRET")
            self.assertNotIn("PRIVATE", url)
            self.assertNotIn("SECRET", url)
            self.assertNotIn("123", url)
        self.assertEqual(sanitize_url("https://PRIVATE.example/path"), "https://redacted.invalid/[redacted]")
        self.assertEqual(sanitize_url("https://[bad"), "https://redacted.invalid/")

    def test_untrusted_origin_and_malformed_entries(self):
        bad = entry({"items": [self.video]}, url="https://www.tiktok.com.evil.test/api/post/item_list/")
        malformed = entry({"PRIVATE_KEY": "PRIVATE_VALUE"})
        malformed["request"]["method"] = []
        malformed["response"]["status"] = "PRIVATE_STATUS"
        malformed["response"]["content"]["mimeType"] = "PRIVATE_MIME"
        self.write([None, bad, malformed, {"request": [], "response": []}])
        records, summary = import_har(self.path)
        self.assertFalse(records)
        self.assertNotIn("PRIVATE", json.dumps(summary))
        self.assertEqual(summary["body_availability"]["malformed_entry"], 1)

    def test_limits_and_invalid_input(self):
        self.write([entry({"items": [self.video]})])
        for constant, limit in (("MAX_FILE_BYTES", 8), ("MAX_ENTRIES", 0), ("MAX_NODES", 1), ("MAX_DEPTH", 1)):
            with patch("crotdalam.collectors.har_collector." + constant, limit):
                with self.assertRaises(ValueError):
                    import_har(self.path)
        with patch("crotdalam.collectors.har_collector.MAX_BODY_BYTES", 8):
            self.assertEqual(import_har(self.path)[1]["body_availability"], {"oversized": 1})
        for raw in ("PRIVATE_INVALID", "[]", '{"log": {}}', "[" * 2000):
            self.path.write_text(raw)
            with self.assertRaises(ValueError) as context:
                import_har(self.path)
            self.assertNotIn("PRIVATE", str(context.exception))

    def test_cli_sqlite_and_no_engine_or_network(self):
        self.write([entry({"items": [self.video]})])
        db = self.root / "evidence.sqlite"
        output = io.StringIO()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), redirect_stdout(output):
            self.assertEqual(main(["import-har", str(self.path), "--database", str(db)]), 0)
        summary = json.loads(output.getvalue())
        self.assertEqual(summary["stored"], 1)
        self.assertNotIn("PRIVATE", output.getvalue())
        self.assertNotIn("SECRET", output.getvalue())
        self.assertEqual(len(load_records(db)), 1)
        inspect_db = self.root / "not-created.sqlite"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["import-har", str(self.path), "--inspect", "--database", str(inspect_db)]), 0)
        self.assertFalse(inspect_db.exists())
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["import-har", str(self.path)]), 1)


if __name__ == "__main__":
    unittest.main()
