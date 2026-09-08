"""Offline regression tests: python -B -m unittest discover -s tests -v."""

import asyncio
import io
import json
import unittest
from unittest.mock import patch

from crotdalam.collectors import ProfileCollector, VideoCollector, FollowerCollector, CommentCollector
from crotdalam.collectors.hydration import objects
from crotdalam.collectors.base import validate_record
from crotdalam.search import KeywordSearch, FuzzySearch, RegexSearch, BulkSearch
from crotdalam.analyzers import (ScamDetector, PhishingDetector, BotDetector,
                                EngagementAnalyzer, SentimentAnalyzer, NetworkAnalyzer, TemporalAnalyzer)


def record(text="", **value):
    return {"data_type": "video", "target": "alice", "value": {"text": text, **value}}


class AnalysisTests(unittest.TestCase):
    def test_scam_weighted_and_not_probability(self):
        detector = ScamDetector()
        result = detector.analyze(record("Anda menang! Kirim OTP, biaya admin, segera transfer"))
        self.assertEqual(result["score"], 100)
        self.assertFalse(result["is_probability"])
        self.assertGreater(len(result["evidence"]), 3)
        self.assertEqual(detector.analyze(record("guaranteed profit " * 10))["score"], 30)
        self.assertEqual(detector.analyze(record("pasti untungnya tidak benar"))["score"], 0)
        with self.assertRaises(ValueError):
            detector.analyze([])

    def test_phishing_offline_and_invalid(self):
        result = PhishingDetector().analyze("http://trusted.example@127.0.0.1:8080/verify/password")
        self.assertEqual(result["score"], 70)
        self.assertEqual(result["urls"][0]["host"], "127.0.0.1")
        self.assertEqual(PhishingDetector().analyze("https://example.com")["score"], 0)
        self.assertEqual(PhishingDetector().analyze("https://host:bad")["status"], "insufficient_data")
        self.assertEqual(PhishingDetector().analyze({"urls": ["javascript:alert(1)"]})["assessed_urls"], 0)
        with self.assertRaises(ValueError):
            PhishingDetector().analyze({"urls": ["https://a.com"] * 101})

    def test_engagement_missing_and_weighted(self):
        result = EngagementAnalyzer().analyze([
            record(stats={"diggCount": 10, "commentCount": 5, "shareCount": 5, "playCount": 100}),
            record(likes=10, comments=0, shares=0, views=200),
            record(likes=100, views=10)])
        self.assertEqual(result["weighted_rate_by_views_percent"], 10)
        self.assertIsNone(result["records"][2]["interactions"])
        self.assertIsNone(EngagementAnalyzer().analyze(record(likes=True, comments=0, shares=0))["records"][0]["interactions"])

    def test_sentiment_bilingual_negation(self):
        result = SentimentAnalyzer().analyze([record("tidak bagus"), record("not bad"), record("baik. buruk"), record("xyz")])
        self.assertEqual([r["label"] for r in result["records"]], ["negative", "positive", "mixed_or_neutral", "unknown"])
        self.assertEqual(SentimentAnalyzer().analyze(record("not. good"))["score"], 1)

    def test_temporal_utc_and_missing(self):
        result = TemporalAnalyzer().analyze([
            record(createTime=0), record(timestamp="2026-01-01T07:00:00+07:00"),
            record(timestamp="2026-01-01T00:00:00"), record(timestamp="bad")])
        self.assertEqual(result["valid_count"], 2)
        self.assertEqual(result["excluded_count"], 2)
        self.assertEqual(result["hour_counts"]["0"], 2)
        self.assertIsNone(TemporalAnalyzer().analyze([])["peak_hour_utc"])

    def test_bot_requires_observations(self):
        result = BotDetector().analyze({"posts": [{"text": "same", "createTime": i * 600} for i in range(12)]})
        self.assertEqual(result["score"], 75)
        self.assertEqual(BotDetector().analyze({})["status"], "insufficient_data")
        activity = [dict(record("same"), timestamp=i * 600) for i in range(12)]
        self.assertEqual(BotDetector().analyze(activity)["timestamp_sample_size"], 12)

    def test_network_edges_and_isolates(self):
        result = NetworkAnalyzer().analyze({"edges": [{"source": "a", "target": "b"},
                                                     {"source": "a", "target": "b"},
                                                     {"source": "b", "target": "c"},
                                                     {"source": "a", "target": "a"}], "nodes": ["isolated"]})
        self.assertEqual(result["node_count"], 4)
        self.assertEqual(result["edge_count"], 2)
        self.assertEqual(result["duplicate_edges"], 1)
        self.assertEqual(result["excluded_self_loops"], 1)
        self.assertGreater(result["centrality"]["b"]["betweenness"], 0)
        self.assertEqual(NetworkAnalyzer().analyze([])["communities"], [])
        with self.assertRaises(ValueError):
            NetworkAnalyzer().analyze({"source": None, "target": "b"})

    def test_record_validation(self):
        for invalid in ({}, {"data_type": "x", "target": 1, "value": {}}, record(x=float("nan"))):
            with self.assertRaises(ValueError):
                validate_record(invalid)


class SearchTests(unittest.TestCase):
    def test_keyword_casefold_limits_detached(self):
        corpus = [record("BAGUS"), record("bad")]
        search = KeywordSearch(corpus)
        self.assertEqual(len(search.search("bagus")), 1)
        found = search.search("bagus")
        found[0]["value"]["text"] = "changed"
        self.assertEqual(search.search("bagus")[0]["value"]["text"], "BAGUS")
        self.assertEqual(search.search("bagus", 0), [])
        for query, limit in (("", 1), ("x", -1), ("x", True), ("x" * 513, 1)):
            with self.assertRaises(ValueError):
                search.search(query, limit)

    def test_fuzzy_and_regex(self):
        self.assertEqual(len(FuzzySearch([record("investasi")]).search("investsi")), 1)
        self.assertEqual(len(RegexSearch([record("Profit 123")]).search(r"(?i)profit\s+\d+")), 1)
        with self.assertRaises(ValueError):
            RegexSearch([]).search("[")
        with self.assertRaises(ValueError):
            RegexSearch([record("a" * 90000 + "!")], timeout=0.00001).search(r"(a+)+$")

    def test_search_bounds(self):
        with self.assertRaises(ValueError):
            KeywordSearch([record("x" * 100001)])
        with self.assertRaises(ValueError):
            KeywordSearch(record() for _ in range(10001))


class CollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_profile_universal(self):
        payload = {"__DEFAULT_SCOPE__": {"webapp.user-detail": {"userInfo": {
            "user": {"id": "1", "uniqueId": "alice", "nickname": "Alice", "signature": "hello"},
            "stats": {"followerCount": 42}}}}}

        class Engine:
            async def fetch(self, url):
                return '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">' + json.dumps(payload) + '</script>'

        result = await ProfileCollector(Engine()).collect("@alice")
        self.assertEqual(result["value"]["stats"]["followerCount"], 42)
        self.assertEqual(result["data_type"], "profile")
        with self.assertRaises(ValueError):
            await ProfileCollector(Engine()).collect("bob")
        with self.assertRaises(ValueError):
            await ProfileCollector(Engine()).collect("../evil")

    async def test_profile_sigi_and_video(self):
        payload = {"UserModule": {"users": {"alice": {"uniqueId": "alice", "nickname": "Alice"}},
                                  "stats": {"alice": {"followerCount": 5}}},
                   "ItemModule": {"12345": {"id": "12345", "desc": "hello", "video": {"duration": 12}}}}

        class Engine:
            async def fetch(self, url):
                return '<script id="SIGI_STATE">' + json.dumps(payload) + '</script>'

        self.assertEqual((await ProfileCollector(Engine()).collect("alice"))["value"]["stats"]["followerCount"], 5)
        video = await VideoCollector(Engine()).collect("https://www.tiktok.com/@alice/video/12345?tracking=1")
        self.assertEqual(video["value"]["video"]["duration"], 12)
        self.assertNotIn("?", video["source_url"])
        for url in ("http://www.tiktok.com/@alice/video/12345", "https://evil.com/@alice/video/12345",
                    "https://www.tiktok.com@evil.com/@alice/video/12345", "https://vm.tiktok.com/abc"):
            with self.assertRaises(ValueError):
                await VideoCollector(Engine()).collect(url)

    async def test_unavailable_and_local_imports(self):
        class Engine:
            async def fetch(self, url):
                return '<html>Please log in<script type="application/json">invalid</script></html>'

        with self.assertRaises(ValueError):
            await VideoCollector(Engine()).collect("https://www.tiktok.com/@alice/video/12345")
        with self.assertRaises(ValueError):
            await FollowerCollector().collect("alice")
        with self.assertRaises(ValueError):
            CommentCollector(Engine())
        imported = {"data_type": "follower", "target": "alice", "value": {"username": "bob"}}
        self.assertEqual((await FollowerCollector([imported]).collect("alice"))["value"]["count"], 1)

    async def test_author_stub_is_not_profile(self):
        class Engine:
            async def fetch(self, url):
                return '<script type="application/json">{"author":{"uniqueId":"alice","nickname":"Alice"}}</script>'

        with self.assertRaises(ValueError):
            await ProfileCollector(Engine()).collect("alice")

    def test_hydration_budget(self):
        with self.assertRaises(ValueError):
            objects("x" * 5000001)
        with self.assertRaises(ValueError):
            objects('<script type="application/json">' + '[' * 66 + '0' + ']' * 66 + '</script>')
        with self.assertRaises(ValueError):
            objects('<script type="application/json">{}</script>' * 65)


class BulkTests(unittest.IsolatedAsyncioTestCase):
    async def test_bounded_workers_order_and_failure(self):
        class Engine:
            active = peak = 0

            async def search(self, keyword, limit=20):
                self.active += 1
                self.peak = max(self.peak, self.active)
                try:
                    await asyncio.sleep(0.001)
                    if keyword == "bad":
                        raise ValueError("unsupported")
                    return [] if keyword == "empty" else [record(keyword)]
                finally:
                    self.active -= 1

        engine = Engine()
        with patch("pathlib.Path.open", return_value=io.BytesIO(b'keyword,other\ngood,x\nbad,x\nempty,x\nlast,x\n')):
            result = await BulkSearch(engine).run("input.csv", threads=2)
        self.assertEqual(engine.peak, 2)
        self.assertEqual([r["data_type"] for r in result], ["video", "search_error", "search_status", "video"])
        self.assertEqual(result[1]["target"], "bad")

    async def test_plain_lines_and_invalid_csv(self):
        class Engine:
            async def search(self, keyword, limit=20):
                return []

        with patch("pathlib.Path.open", return_value=io.BytesIO(b'\xef\xbb\xbfhello\n\nworld\n')):
            self.assertEqual(len(await BulkSearch(Engine()).run("input.txt")), 2)
        with patch("pathlib.Path.open", return_value=io.BytesIO(b'wrong\nhello')):
            with self.assertRaises(ValueError):
                await BulkSearch(Engine()).run("input.csv")
        with self.assertRaises(ValueError):
            await BulkSearch(Engine()).run("input.txt", threads=0)


if __name__ == "__main__":
    unittest.main()
