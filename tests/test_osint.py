"""Selector extraction, cross-account coordination, and corpus graph building."""

import unittest

from crotdalam.analyzers import SelectorExtractor, CoordinationAnalyzer, graph_from_corpus, NetworkAnalyzer
from crotdalam.analyzers.selectors import extract


class SelectorExtractionTests(unittest.TestCase):
    def test_extracts_each_selector_type(self):
        text = ("DM @crypto_king email me at boss@evil.co call +62 812-3456-7890 "
                "visit https://bit.ly/x #richquick wallet 0x" + "a" * 40)
        found = extract(text)
        self.assertEqual(found["mention"], ["crypto_king"])
        self.assertEqual(found["email"], ["boss@evil.co"])
        self.assertEqual(found["hashtag"], ["richquick"])
        self.assertEqual(found["url"], ["https://bit.ly/x"])
        self.assertEqual(found["eth"], ["0x" + "a" * 40])
        self.assertTrue(found["phone"])

    def test_messaging_from_scheme_and_bare(self):
        self.assertEqual(extract("join https://t.me/scamgroup")["messaging"], ["telegram:scamgroup"])
        self.assertEqual(extract("chat wa.me/628123456789 now")["messaging"], ["whatsapp:628123456789"])

    def test_phone_shape_filtering(self):
        self.assertNotIn("phone", extract("call 123"))          # too few digits
        self.assertIn("phone", extract("call 081234567890"))

    def test_rejects_oversized_and_nonstring(self):
        with self.assertRaises(ValueError):
            extract("x" * 100_001)
        with self.assertRaises(ValueError):
            extract(None)

    def test_corpus_attribution_and_counts(self):
        corpus = [{"value": {"desc": "join @admin", "uniqueId": "acct1"}},
                  {"value": {"desc": "also @admin here", "id": "vid2"}}]
        result = SelectorExtractor().analyze(corpus)
        self.assertEqual(result["counts"]["mention"], 2)
        self.assertEqual(result["distinct"]["mention"], 1)
        targets = {t for t, d in result["by_target"].items() if "admin" in d.get("mention", [])}
        self.assertEqual(targets, {"acct1", "vid2"})
        self.assertFalse(result["selectors"].get("url"))


class CoordinationTests(unittest.TestCase):
    def test_shared_caption_across_accounts(self):
        corpus = [{"value": {"desc": "Guaranteed profit join now", "author": {"uniqueId": "a"}}},
                  {"value": {"desc": "guaranteed   PROFIT   join now", "author": {"uniqueId": "b"}}},
                  {"value": {"desc": "totally unrelated post text", "author": {"uniqueId": "c"}}}]
        result = CoordinationAnalyzer().analyze(corpus)
        self.assertEqual(len(result["shared_captions"]), 1)
        self.assertEqual(result["shared_captions"][0]["accounts"], ["a", "b"])
        self.assertIn(["a", "b"], result["coordinated_account_sets"])

    def test_shared_selector_links_accounts(self):
        corpus = [{"value": {"desc": "x wa.me/628", "author": {"uniqueId": "d"}}},
                  {"value": {"desc": "y wa.me/628", "author": {"uniqueId": "e"}}}]
        result = CoordinationAnalyzer().analyze(corpus)
        self.assertEqual(result["shared_selectors"][0]["accounts"], ["d", "e"])

    def test_single_account_is_not_coordination(self):
        corpus = [{"value": {"desc": "same caption here", "author": {"uniqueId": "a"}}},
                  {"value": {"desc": "same caption here", "author": {"uniqueId": "a"}}}]
        result = CoordinationAnalyzer().analyze(corpus)
        self.assertEqual(result["shared_captions"], [])

    def test_not_a_probability_and_min_accounts_guard(self):
        self.assertFalse(CoordinationAnalyzer().analyze([])["is_probability"])
        with self.assertRaises(ValueError):
            CoordinationAnalyzer(min_accounts=1)


class GraphBuildingTests(unittest.TestCase):
    def test_edges_feed_network_analyzer(self):
        corpus = [{"value": {"id": "v1", "video": {"duration": 5}, "author": {"uniqueId": "creator"}}},
                  {"value": {"cid": "c1", "aweme_id": "v1", "text": "hi", "user": {"unique_id": "fan"}}},
                  {"value": {"cid": "c2", "aweme_id": "v1", "text": "bot", "user": {"unique_id": "bot"}}}]
        graph = graph_from_corpus(corpus)
        self.assertIn("video:v1", graph["nodes"])
        self.assertIn("user:creator", graph["nodes"])
        relations = {(e["source"], e["relation"], e["target"]) for e in graph["edges"]}
        self.assertIn(("user:creator", "posted", "video:v1"), relations)
        self.assertIn(("user:fan", "commented_on", "video:v1"), relations)
        analysis = NetworkAnalyzer().analyze(graph)
        self.assertEqual(analysis["node_count"], 4)
        self.assertEqual(analysis["edge_count"], 3)

    def test_namespacing_keeps_reused_ids_distinct(self):
        # A video and a user sharing the raw id must not collapse into one node.
        corpus = [{"value": {"id": "42", "video": {"duration": 1}, "author": {"uniqueId": "42"}}}]
        graph = graph_from_corpus(corpus)
        self.assertIn("video:42", graph["nodes"])
        self.assertIn("user:42", graph["nodes"])


if __name__ == "__main__":
    unittest.main()
