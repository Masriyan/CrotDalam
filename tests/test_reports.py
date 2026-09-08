import asyncio
import csv
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from crotdalam.reports import CSVReport, HTMLReport, JSONReport, PDFReport, generate
from crotdalam.reports.common import load_json
from crotdalam.ui.bulk import BulkSearch
from crotdalam.ui.cli import build_parser, main, run_engine
from crotdalam.ui.shell import InvestigationShell


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.record = {"data_type": "username", "target": "alice", "value": {"name": "Alice", "risk": "high"},
                       "source_url": "https://example.test/alice", "timestamp": "2026-09-08T00:00:00Z"}

    def test_html_escapes_every_untrusted_field(self):
        attack = '<script>alert("x")</script>&\'"'
        record = {key: attack for key in self.record}
        record["value"] = {"payload": attack, "risk": attack}
        record["sha256"] = attack
        path = HTMLReport().generate([record], self.root / "nested/report.html", attack, attack)
        html = path.read_text()
        self.assertNotIn("<script>", html)
        self.assertNotIn(attack, html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("unrated: 1", html)
        self.assertIn("Content-Security-Policy", html)
        self.assertNotIn("<script src", html)

    def test_html_empty_and_supplied_risk(self):
        path = HTMLReport().generate([], self.root / "empty.html")
        self.assertIn("No records were supplied", path.read_text())
        path = HTMLReport().generate([self.record], self.root / "risk.html")
        self.assertIn("high: 1", path.read_text())
        self.assertIn("Not supplied", path.read_text())

    def test_csv_bom_and_formula_protection(self):
        for attack in ("=1+1", "+CMD()", "-1+1", "@SUM(A1)", "  =1", "\t=1", "\r=1", "\n=1"):
            with self.subTest(attack=attack):
                record = dict(self.record, target=attack, source_url=attack)
                path = CSVReport().generate([record], self.root / "out.csv", attack, attack)
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                with path.open(encoding="utf-8-sig", newline="") as stream:
                    row = next(csv.DictReader(stream))
                for key in ("target", "source_url", "case_id", "analyst"):
                    self.assertEqual(row[key], "'" + attack)
                self.assertEqual(json.loads(row["value"]), self.record["value"])

    def test_json_round_trip_schema_and_unicode(self):
        record = dict(self.record, value={"name": "Ren\u00e9", "nested": {"x": [1, 2]}})
        path = JSONReport().generate(iter([record]), self.root / "out.json", "CASE-1", "Analyst")
        payload = json.loads(path.read_text())
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["case_id"], "CASE-1")
        self.assertEqual(load_json(path), [record])

    def test_validation_before_writing(self):
        for format in ("html", "csv", "json"):
            output = self.root / f"invalid.{format}"
            with self.assertRaises(ValueError):
                generate([dict(self.record, value="invalid")], output, format)
            self.assertFalse(output.exists())
        with self.assertRaises(ValueError):
            generate([], self.root / "invalid", "exe")

    def test_unknown_json_schema_rejected(self):
        path = self.root / "bad.json"
        path.write_text('{"schema_version":"99","records":[]}')
        with self.assertRaises(ValueError):
            load_json(path)

    @unittest.skipUnless(importlib.util.find_spec("reportlab"), "ReportLab optional")
    def test_pdf_real_output_and_markup(self):
        record = dict(self.record, value={"markup": "<script>&"})
        path = PDFReport().generate([record], self.root / "out.pdf", "<case>", "A&B")
        self.assertTrue(path.read_bytes().startswith(b"%PDF-"))

    def test_cli_report_validate_and_analyze(self):
        source = JSONReport().generate([self.record], self.root / "source.json")
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["report", "--format", "html", "--input", str(source), "--output", str(self.root / "cli.html")]), 0)
            self.assertEqual(main(["validate", "--format", "json", "--input", str(source)]), 0)
            self.assertEqual(main(["analyze", "--input", str(source)]), 0)
        self.assertIn("Valid: 1 records", output.getvalue())

    def test_cli_parser_global_and_local_corpus(self):
        parser = build_parser()
        self.assertEqual(parser.parse_args(["--corpus", "a", "search", "--keyword", "b"]).corpus, "a")
        self.assertEqual(parser.parse_args(["search", "--corpus", "a", "--username", "b"]).corpus, "a")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["monitor", "--keyword", "a", "--interval", "nan"])

    def test_bulk_bounded_workers(self):
        source = self.root / "keywords.csv"
        source.write_text("keyword\na\nb\na\nc\n")
        calls = []
        active = 0
        peak = 0

        async def search(keyword, limit=20):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.001)
            calls.append(keyword)
            active -= 1

        result = asyncio.run(BulkSearch(SimpleNamespace(search=search), 2).run(source))
        self.assertEqual(result, ["a", "b", "c"])
        self.assertEqual(set(calls), {"a", "b", "c"})
        self.assertLessEqual(peak, 2)

    def test_shell_rejects_os_commands(self):
        shell = InvestigationShell()
        shell.stdout = io.StringIO()
        with patch("crotdalam.ui.cli.main") as dispatch:
            shell.onecmd("!touch unsafe")
            shell.onecmd("__import__('os').system('id')")
            dispatch.assert_not_called()
        self.assertIn("Unknown command", shell.stdout.getvalue())
        self.assertIn("search", shell.completenames("se"))

    def test_engine_context_and_bounded_monitor(self):
        from unittest.mock import AsyncMock
        calls = []
        record = self.record

        class FakeEngine:
            def __init__(self, settings):
                self.db = SimpleNamespace(records=lambda: [record])

            async def __aenter__(self):
                calls.append("enter")
                return self

            async def __aexit__(self, *args):
                calls.append("close")

            async def search(self, keyword, limit=20):
                calls.append((keyword, limit))

            async def collect(self, kind, target):
                calls.append((kind, target))

        module = SimpleNamespace(Engine=FakeEngine)
        with patch.dict("sys.modules", {"crotdalam.core.engine": module}), patch("crotdalam.ui.cli.settings_for", return_value=None):
            args = build_parser().parse_args(["monitor", "--keyword", "needle", "--rounds", "2", "--interval", "0"])
            with patch("crotdalam.ui.cli.asyncio.sleep", new_callable=AsyncMock) as sleep, redirect_stderr(io.StringIO()):
                result = asyncio.run(run_engine(args))
                self.assertEqual(sleep.await_count, 1)
            self.assertEqual(calls, ["enter", ("needle", 20), ("needle", 20), "close"])
            self.assertEqual(result["records"], [record])
            calls.clear()
            args = build_parser().parse_args(["search", "--username", "alice"])
            asyncio.run(run_engine(args))
            self.assertEqual(calls, ["enter", ("username", "alice"), "close"])


if __name__ == "__main__":
    unittest.main()
