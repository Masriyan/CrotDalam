# Testing

The suite uses `unittest` from the standard library — there is no pytest
dependency.

```sh
python -m unittest discover -s tests            # 79 tests, well under a second
python -m unittest tests.test_har               # one module
python -m unittest tests.test_har.HARTests.test_redaction   # one case
python -m unittest discover -s tests -v         # verbose
```

## Coverage

```sh
pip install -e ".[dev]"
python -m coverage run -m unittest discover -s tests
python -m coverage report --include="crotdalam/*"
python -m coverage html && open htmlcov/index.html
```

Current: **84% branch overall**, **88% excluding `ui/gui.py`**, which needs a
display and has no automated coverage. Coverage must not regress in a pull
request.

## Layout

| File | Covers |
|---|---|
| `test_har.py` | HAR import: normalization, dedup, provenance, redaction, limits, malformed input |
| `test_storage.py` | Database permissions, WAL, state, encryption, checksums, log redaction |
| `test_analysis.py` | The per-record analyzers, the four search engines, hydration budgets |
| `test_monitors.py` | Four monitors, staleness, spike windows, alert dedup, scheduler |
| `test_reports.py` | Four formats, escaping, validation ordering, CLI, shell safety |
| `test_config.py` | Settings validation, environment parsing, engine absence, optional provenance |
| `test_custody.py` | Source hashing, `collected_at`, and the tamper-evident evidence chain |
| `test_osint.py` | Selector extraction, cross-account coordination, corpus→graph building |

## Conventions

**Group related assertions into one well-named test.** The suite favours
`test_normalization_dedup_provenance_and_privacy` over six one-line tests. The
name states the property being protected.

**Test the boundary, not just the happy path.** Every bound has a test that
exceeds it and asserts the failure:

```python
with self.assertRaises(ValueError):
    NetworkAnalyzer().analyze({"edges": [...2001 nodes...]})
```

**Never use real data as a fixture.** Build the minimal synthetic HAR or record
inline. `test_har.py` shows the pattern.

**Async cases use `IsolatedAsyncioTestCase`**, not manual `asyncio.run`.

**Assert on messages where they matter.** Error text is a user interface; when a
message guides the user, test that it says the right thing:

```python
self.assertIn("import-har", err.getvalue())
self.assertNotIn("Traceback", err.getvalue())
```

## Testing without the engine

The collection engine is absent by design ([`SCOPE.md`](SCOPE.md)). Tests that
need one inject a stub through `sys.modules`:

```python
module = SimpleNamespace(Engine=FakeEngine)
with patch.dict("sys.modules", {"crotdalam.core.engine": module}), \
     patch("crotdalam.ui.cli.settings_for", return_value=None):
    result = asyncio.run(run_engine(args))
```

This tests the CLI's wiring against the `Engine` protocol without shipping a
transport. `tests/test_config.py::EngineAbsenceTests` covers the other side:
that a missing engine produces a helpful message and exit code 1, not a
traceback.

## Static checks

```sh
python -m pyflakes crotdalam/ tests/     # must be clean
```

One warning is expected and intentional — `test_storage.py` imports
`cryptography` to check availability.

## Full pre-release check

```sh
python -m unittest discover -s tests
python -m pyflakes crotdalam/ tests/
python -m coverage run -m unittest discover -s tests
python -m coverage report --include="crotdalam/*"

python -m venv /tmp/verify && /tmp/verify/bin/pip install .
/tmp/verify/bin/crotdalam config show
/tmp/verify/bin/python -c "import crotdalam; print(crotdalam.__version__)"

grep -rn "TODO\|FIXME" crotdalam/          # expect nothing
git status --short                          # expect no .har, .sqlite or data/
```

CI runs the equivalent on every push — see `.github/workflows/ci.yml`.
