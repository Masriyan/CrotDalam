# Contributing to CrotDalam

## Ground rules

1. **Nothing that defeats platform protections.** Pull requests adding CAPTCHA
   solving, request-signature generation (`X-Bogus`, `msToken`, `_signature`),
   fingerprint spoofing, proxy rotation for evasion or decoy traffic will be
   closed. This boundary is the project's design, documented in
   [`docs/SCOPE.md`](docs/SCOPE.md), not an oversight.
2. **Never commit real data.** No HAR captures, evidence databases, exports,
   screenshots of real accounts, tokens or cookies. `.gitignore` covers the
   common cases; you are still responsible for what you stage.
3. **State uncertainty.** Analyzers report evidence and limits, not verdicts.
   New heuristics must carry weights, an `uncertainty` list and a documented
   false-positive mode.

## Development setup

```sh
git clone https://github.com/Masriyan/CrotDalam.git
cd CrotDalam
python -m venv .venv && source .venv/bin/activate
pip install -e ".[pdf,dev]"
```

## Before you open a pull request

```sh
python -m unittest discover -s tests     # all tests must pass
python -m pyflakes crotdalam/ tests/     # must be clean
python -m coverage run -m unittest discover -s tests
python -m coverage report --include="crotdalam/*"
```

Coverage must not regress. New modules need tests in the same pull request.

## Code standards

The existing code has a consistent style; match it rather than introducing your
own. Concretely:

- **Every module opens with a docstring stating what it does and what it
  refuses to do.** This is the project's most important convention. Compare
  `crotdalam/analyzers/phishing.py`: "Offline lexical URL triage: no HTTP, DNS,
  reputation or arbitrary URL fetch."
- **Validate at the boundary and fail closed.** Reject bad input with a
  `ValueError` carrying a specific message. Never silently truncate, coerce or
  guess.
- **Bound everything that processes untrusted input** — bytes, item counts,
  recursion depth, wall-clock time. Document the limit in the docstring and
  test that exceeding it raises.
- **Reject `bool` where a number is expected.** `isinstance(True, int)` is
  `True` in Python; the codebase guards against it consistently.
- **Prefer the standard library.** Four runtime dependencies is a feature. A
  new one needs justification in the pull request.
- **Comments explain why, not what.** The existing comments are sparse and
  earn their place; follow that.
- **Type hints on public functions**, plain dictionaries for records — records
  are JSON, not ORM entities.

## Testing conventions

Tests use `unittest` from the standard library, not pytest. Async cases use
`unittest.IsolatedAsyncioTestCase`. Group related assertions into one test with
a descriptive name, as the existing suite does — see
`tests/test_har.py::test_normalization_dedup_provenance_and_privacy`.

Test the boundary conditions, not just the happy path: the limit that must
raise, the malformed record that must be rejected, the untrusted string that
must be escaped in every output format.

Never use a real capture as a fixture. Build the minimal synthetic HAR or record
your test needs inline.

## Commit and pull request format

Write commit subjects in the imperative mood, under 72 characters
(`Reject naive timestamps in temporal analysis`). Explain *why* in the body.

Pull requests should state what changed, why, how you tested it, and any
behaviour change downstream users would notice. Use the template.

## Where things live

| Adding | Goes in | Also update |
|---|---|---|
| A collector | `crotdalam/collectors/` | `collectors/__init__.py`, `docs/HAR-IMPORT.md` |
| An analyzer | `crotdalam/analyzers/` | `analyzers/__init__.py`, `docs/ANALYZERS.md` |
| A monitor | `crotdalam/monitors/` | `monitors/__init__.py`, `docs/MONITORS.md` |
| A report format | `crotdalam/reports/` | `reports/__init__.py` `REPORTS` map, `docs/REPORTS.md` |
| A CLI command | `crotdalam/ui/cli.py` | `docs/USAGE.md`, `ui/shell.py` command list |
| A setting | `crotdalam/config/settings.py` | `docs/CONFIGURATION.md` |

Every user-visible change also needs a `CHANGELOG.md` entry.
