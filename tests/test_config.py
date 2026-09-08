"""Regression tests for configuration, engine absence and optional provenance."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import asdict
from pathlib import Path

from crotdalam.config.settings import Settings
from crotdalam.reports import generate
from crotdalam.reports.common import normalize
from crotdalam.ui.cli import main


class SettingsTests(unittest.TestCase):
    def test_defaults_are_local_and_printable(self):
        payload = asdict(Settings())
        self.assertEqual(payload["concurrency"], 4)
        self.assertIsNone(payload["corpus"])
        json.dumps(payload)  # config show must always be serializable

    def test_invalid_values_are_rejected(self):
        for kwargs in ({"concurrency": 0}, {"concurrency": 33}, {"concurrency": True},
                       {"request_timeout": 0}, {"request_timeout": float("inf")},
                       {"database": " "}, {"analyst": ""}, {"corpus": ""}):
            with self.assertRaises(ValueError, msg=kwargs):
                Settings(**kwargs)

    def test_from_env_parses_and_validates(self):
        settings = Settings.from_env({"CROTDALAM_CONCURRENCY": "8", "CROTDALAM_CASE_ID": "OP-1"})
        self.assertEqual((settings.concurrency, settings.case_id), (8, "OP-1"))
        self.assertEqual(Settings.from_env({"CROTDALAM_CONCURRENCY": ""}).concurrency, 4)
        with self.assertRaises(ValueError):
            Settings.from_env({"CROTDALAM_CONCURRENCY": "abc"})
        with self.assertRaises(ValueError):
            Settings.from_env({"CROTDALAM_CONCURRENCY": "0"})

    def test_key_is_referenced_by_name_not_value(self):
        settings = Settings(encryption_key_env="CROTDALAM_KEY")
        self.assertNotIn("secret", json.dumps(asdict(settings)))
        self.assertEqual(settings.encryption_key({"CROTDALAM_KEY": "secret"}), "secret")
        with self.assertRaises(ValueError):
            settings.encryption_key({})
        self.assertIsNone(Settings().encryption_key({}))

    def test_with_overrides_ignores_unset(self):
        base = Settings(database="a.sqlite")
        self.assertEqual(base.with_overrides(database=None).database, "a.sqlite")
        self.assertEqual(base.with_overrides(database="b.sqlite").database, "b.sqlite")


class EngineAbsenceTests(unittest.TestCase):
    def test_engine_commands_fail_with_guidance_not_tracebacks(self):
        for argv in (["search", "--keyword", "x"], ["analyze", "--username", "x"],
                     ["crawl", "--csv", "x.csv"], ["monitor", "--keyword", "x"]):
            err = io.StringIO()
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                status = main(argv)
            self.assertEqual(status, 1, argv)
            self.assertIn("crotdalam.core.engine", err.getvalue())
            self.assertIn("import-har", err.getvalue())
            self.assertNotIn("Traceback", err.getvalue())

    def test_offline_commands_still_work_without_engine(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["config", "show"]), 0)
        self.assertEqual(json.loads(out.getvalue())["concurrency"], 4)


class OptionalProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_records_without_provenance_are_reportable(self):
        record = {"data_type": "profile", "target": "alice", "value": {"x": 1}}
        for format in ("json", "html", "csv"):
            path = generate([record], self.root / f"r.{format}", format)
            self.assertTrue(path.exists())
        self.assertIn("Not supplied", (self.root / "r.html").read_text(encoding="utf-8"))

    def test_required_fields_are_still_enforced(self):
        for bad in ({"data_type": "a", "target": "b"},
                    {"data_type": "a", "target": "b", "value": "no"},
                    {"data_type": 1, "target": "b", "value": {}},
                    {"data_type": "a", "target": "b", "value": {}, "source_url": 5}):
            with self.assertRaises(ValueError, msg=bad):
                normalize([bad])

    def test_null_provenance_is_accepted_and_shown_as_unknown(self):
        record = {"data_type": "a", "target": "b", "value": {}, "source_url": None, "timestamp": None}
        html = generate([record], self.root / "n.html", "html").read_text(encoding="utf-8")
        self.assertEqual(html.count("Not supplied"), 3)


if __name__ == "__main__":
    unittest.main()
