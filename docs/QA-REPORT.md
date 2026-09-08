# QA / QC Report

**Audit date:** 2026-09-08 · **Version:** 0.2.0, with a 0.3.0 follow-up · **Platform:** Linux, Python 3.14.7

A full quality audit of every module, with each finding verified by execution
rather than by reading. This document records what was checked, what was found,
what was fixed and what remains open. The **0.3.0 Follow-up** section near the
end records the capability and chain-of-custody work that came after the audit.

## Verdict

The codebase is in good shape. Input validation, resource bounding and output
escaping are applied consistently, and the module docstrings state limitations
honestly. The audit found **one blocking defect**, **one contract
inconsistency**, and a set of packaging and hygiene gaps that mattered for a
public release. All are fixed. Two design issues remain open and are tracked.

## Baseline

| Metric | Before | After |
|---|---|---|
| Tests passing | 49 | **59** |
| Branch coverage | 87% (imported modules only) | **83%** overall / **88%** excluding the GUI |
| Source lines | 2,205 | 2,492 |
| Test lines | 780 | 860 |
| Modules importable | 52 / 52 | 55 / 55 |
| CLI commands functional | 7 / 12 | **8 / 12** (10 / 14 after 0.3.0) |
| `pyflakes` warnings | 0 | 0 |
| Placeholders (`TODO`, bare `pass`) | 0 | 0 |
| Pip-installable | No | **Yes** |

Coverage appears to drop because measurement changed: `pyproject.toml` now sets
`source = ["crotdalam"]`, which counts `ui/gui.py` (133 statements, 0%, needs a
display). Previously it was excluded by never being imported. Excluding it, the
comparable figure rose from 87% to 88%.

---

## Findings

### QA-01 · Blocking · Five CLI commands crashed with a raw import error — **fixed**

`crotdalam/ui/cli.py` imported `crotdalam.core.engine` and
`crotdalam.config.settings`. Neither module existed.

```
$ python -m crotdalam.ui.cli search --keyword test
crotdalam: No module named 'crotdalam.core.engine'
$ python -m crotdalam.ui.cli config show
crotdalam: No module named 'crotdalam.config.settings'
```

`search`, `analyze --username`, `crawl`, `monitor` and `gui` were all
unreachable. The test suite passed regardless, because
`tests/test_reports.py` stubs the engine through
`patch.dict("sys.modules", …)` — a contract test against a module that was never
written.

**Fixed** in two parts:

- `crotdalam/config/settings.py` was implemented — a validated frozen dataclass
  with `CROTDALAM_*` environment support. `config show` now works, taking
  functional commands from 7 to 8.
- A `load_engine()` helper now converts the absent engine into an actionable
  message naming the offline alternatives, instead of leaking an import error:

```
crotdalam: The network-facing collection engine (crotdalam.core.engine) is not
part of this release, so 'search' cannot run. Offline workflows are available:
'import-har' to ingest an authorized capture, then 'validate', 'analyze --input'
and 'report'. See docs/SCOPE.md and docs/ROADMAP.md.
```

The engine itself remains unimplemented by design — see [`SCOPE.md`](SCOPE.md).

### QA-02 · High · Storage accepted records that reporting rejected — **fixed**

`utils/models.validate_record` and `collectors/base.validate_record` treat
`source_url` as optional. `reports/common.normalize` required it. A record
stored through the public API was therefore unreportable in every format:

```python
db.store({"data_type": "profile", "target": "alice", "value": {"x": 1}})   # accepted
generate(list(db.records()), "out.json", "json")
# ValueError: Record 0 missing fields: source_url
```

HAR-imported records always set `source_url`, so the CLI path never hit it. The
library path failed on the first record.

**Fixed** by making the report layer agree with the contract the rest of the
codebase already used: `data_type`, `target` and `value` are required;
`source_url`, `timestamp` and `sha256` are optional and render as
`Not supplied`. Type checking on optional fields is unchanged, so genuinely
malformed records are still rejected. Covered by
`tests/test_config.py::OptionalProvenanceTests` (3 cases).

### QA-03 · Medium · Not installable as a package — **fixed**

No `pyproject.toml`, no `setup.py`, no `requirements.txt`, and
`crotdalam/__init__.py`, `crotdalam/core/__init__.py`,
`crotdalam/config/__init__.py` and `tests/__init__.py` were all missing. The
project worked only as an implicit namespace package from its own directory:
`find_packages()` discovered nothing, and `crotdalam.__version__` did not exist.

**Fixed.** Added the four `__init__.py` files and `pyproject.toml` declaring
dependencies, extras (`pdf`, `dev`, `all`) and a `crotdalam` console script.
Verified by installing into a clean virtual environment:

```
$ pip install .            → OK
$ crotdalam config show    → JSON configuration
$ python -c "import crotdalam; print(crotdalam.__version__)"   → 0.2.0
```

All 10 packages are now discovered by setuptools.

### QA-04 · Low · Sentiment lexicon produced false positives — **fixed**

`POSITIVE_WORDS` was built by `.split()` on a string containing the phrase
`terima kasih` ("thank you"). The tokenizer (`[^\W_]+`) cannot match phrases, so
the entry became two independent tokens — `terima` ("accept") and `kasih`
("give"), both common and neutral:

```
"kasih uang ke saya"  ("give me money")  →  positive
```

**Fixed.** Both tokens removed, `makasih` added, with a comment explaining why
the lexicon holds single tokens only. Re-verified: the phrase now scores
`unknown`, and `makasih banyak` scores `positive`.

### QA-05 · Low · Documentation named a non-existent module — **fixed**

`crotdalam/ui/README.md` referenced `crotdalam.core.database.Database`. The
module is `crotdalam.utils.database.Database`. Corrected.

### QA-06 · Low · `.gitignore` missed build and tooling artifacts — **fixed**

Evidence exclusions were already correct — the 144 MB HAR and the SQLite
database in the working tree were both properly ignored. Missing were `build/`,
`dist/`, `*.egg-info/`, `.coverage`, `htmlcov/`, `.venv/`, `.mypy_cache/`,
`.ruff_cache/` and the generated `data/` tree. Added.

---

## Open findings

### QA-07 · Medium · Two different `BulkSearch` classes

`crotdalam/search/bulk.py` and `crotdalam/ui/bulk.py` both define `BulkSearch`
with incompatible contracts:

| | `search.bulk` | `ui.bulk` |
|---|---|---|
| Constructor | `(engine)` | `(engine, threads=4)` |
| CSV header | exactly one `keyword` | `keyword`, `username` or `target` |
| Duplicate queries | preserved | deduplicated |
| Returns | contract records | **keyword list; results discarded** |
| Failure handling | `search_error` record per query | propagates |

The CLI `crawl` command uses `ui.bulk` — the version that throws away search
results. Results reach the database only as a side effect of the engine.

Not fixed here: both are covered by tests with different expectations, so
consolidation is a behaviour change rather than a QA fix, and it is moot while
the engine is absent. Tracked in [`ROADMAP.md`](ROADMAP.md) and documented in
[`SEARCH.md`](SEARCH.md) so nobody picks the wrong one by accident.

### QA-08 · Low · `crotdalam/ui/gui.py` has no automated coverage

133 statements, 0%. It needs a display and an engine. Testing it would require a
headless X server in CI. Accepted for now; it is optional and isolated.

---

## What was verified

### Functional

| Check | Result |
|---|---|
| All 55 modules import cleanly | Pass |
| 12 CLI commands invoked individually | 8 work, 4 fail with the documented message |
| Real 144 MB / 1,696-entry HAR, inspect mode | 156 records, 0.93 s, 640 MB peak RSS |
| Full pipeline: import → validate → analyze → report | Pass, 156 records through all four formats |
| `report --format all` | `report.{html,json,csv,pdf}` all written |
| Clean-venv install and console script | Pass |
| Documented code examples in `docs/` | Executed; run as written |
| Documented analyzer weights and thresholds | Match `config/keywords.py` and `analyzers/common.py` exactly |

### Security and privacy

| Check | Result |
|---|---|
| Hardcoded secrets in source | None |
| Files that would be committed | No file over 1 MB except the intended banner |
| 144 MB HAR and evidence SQLite ignored by Git | Confirmed — both matched by existing rules |
| HAR `--inspect` output leaks no record values | Confirmed; hosts, paths and keys redacted |
| HTML report escapes every untrusted field | Covered by `test_html_escapes_every_untrusted_field` |
| CSV formula-injection protection | Covered by `test_csv_bom_and_formula_protection` |
| Log redaction, including formatted tracebacks | Covered by `test_redaction` |
| Database permissions `0600`, `O_NOFOLLOW` | Covered by `test_roundtrip_permissions_wal_and_state` |
| AES-256-GCM round trip and mode mismatch | Covered by `test_encryption_and_reopen` |
| Shell cannot reach the OS | Covered by `test_shell_rejects_os_commands` |

The 144 MB HAR in the working tree contains real personal data and is correctly
excluded from Git. **It must not be committed, and `.gitignore` does not untrack
a file that was already added.**

### Code quality

| Check | Result |
|---|---|
| `pyflakes` over `crotdalam/` and `tests/` | Clean (one intentional availability check in a test) |
| `TODO` / `FIXME` / placeholder bodies | None |
| `NotImplementedError` | Only in the `Engine` `Protocol` definition, which is correct |
| Module docstrings stating limitations | Present on every module |
| Bounds documented and enforced | Consistent across HAR, hydration, search, analyzers |

---

## 0.3.0 Follow-up — chain of custody and OSINT capability

After the audit, a capability review found the tool was strong at *importing*
but thin at the two things that make it forensic and investigative: provable
custody, and pivoting. Both were addressed. Each item below was verified by
execution.

| Gap | Status | Evidence |
|---|---|---|
| Record timestamp was the import time, not the collection time | **Fixed** | `collected_at` from HAR `startedDateTime`; import: 05:25:33Z vs collected: 04:49:52Z |
| Source HAR file was never hashed | **Fixed** | `source_sha256` on every record and in the summary |
| Deleting records passed validation silently | **Fixed** | Hash chain; deleting 20 of 156 rows now fails `validate` with a clear error |
| No selector extraction (no pivot) | **Added** | `SelectorExtractor`; 142 hashtags, 33 mentions, 1 phone from the sample |
| `NetworkAnalyzer` had nothing to feed it | **Added** | `graph_from_corpus` derives author/comment edges |
| No cross-account coordination detection | **Added** | `CoordinationAnalyzer` clusters accounts by shared caption/selector |
| Indonesian scam lexicon too thin | **Expanded** | 6 → 10 categories; robot trading + admin resmi + off-platform scores 75 |

Verified against the real capture end to end:

```
validate  → Valid: 156 records; evidence chain intact (unkeyed seal a5647f6468a8da34…)
(delete 20 rows via SQL)
validate  → crotdalam: evidence chain broken: records were deleted, reordered or altered   (exit 1)
extract   → {"hashtag": 185, "mention": 41, "phone": 1}
correlate → 86 accounts analyzed, 0 coordinated sets (an organic capture, as expected)
```

Deliberately **not** done: CAPTCHA solving, request-signature forging, evasion
proxy rotation and fingerprint spoofing. These were requested and declined —
their function is to defeat a third party's access controls, and evidence
gathered that way is the evidence most readily excluded, defeating the tool's
forensic purpose. See [`SCOPE.md`](SCOPE.md) and [`ROADMAP.md`](ROADMAP.md).

Tests grew 59 → **79** (`tests/test_custody.py`, `tests/test_osint.py`).
QA-07 (two `BulkSearch` classes) and QA-08 (GUI coverage) remain open and
unchanged.

---

## Reproducing this audit

```sh
pip install -e ".[pdf,dev]"

python -m unittest discover -s tests                    # 79 tests
python -m pyflakes crotdalam/ tests/                    # clean
python -m coverage run -m unittest discover -s tests
python -m coverage report --include="crotdalam/*"

for c in "config show" "search --keyword t" "validate --input evidence.sqlite"; do
    crotdalam $c; echo "exit=$?"
done

grep -rn "TODO\|FIXME\|NotImplementedError" crotdalam/
```

See [`TESTING.md`](TESTING.md).
