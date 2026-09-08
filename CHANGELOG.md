# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-09-08

Chain-of-custody hardening and OSINT capability, addressing the audit gaps
recorded as A1–A3, B1–B3 and C in [`docs/QA-REPORT.md`](docs/QA-REPORT.md).

### Added
- **Tamper-evident evidence chain.** `Database` now seals the record log with a
  hash chain — HMAC-SHA256 keyed by the encryption key when encrypted, a bare
  SHA-256 chain otherwise. `Database.verify_chain()` recomputes it and detects
  deletion, truncation, reordering and metadata edits. `crotdalam validate`
  reports the seal for SQLite inputs and fails on a broken chain. Previously,
  deleting records from the database passed validation silently.
- **Source provenance.** HAR import now records the SHA-256 of the exact source
  file and its name on every record's `provenance`, and in the summary, so a
  finding ties back to a specific capture.
- **Distinct collection time.** Records carry `collected_at`, parsed from the
  HAR entry's `startedDateTime`, separate from the import `timestamp`.
  `TemporalAnalyzer` prefers content time, then `collected_at`, so it no longer
  describes the analyst's import run.
- **`SelectorExtractor`** (`crotdalam.analyzers.selectors`) — pulls URLs,
  @mentions, #hashtags, emails, phone numbers, BTC/ETH addresses and messaging
  handles (`t.me`, `wa.me`, …) from record text, with per-target attribution.
  Offline lexical extraction only; nothing is resolved or contacted.
- **`CoordinationAnalyzer`** (`crotdalam.analyzers.correlation`) — finds
  accounts across the corpus that share a normalized caption or a contact
  selector, and groups them into coordinated sets. The cross-account signal
  BotDetector could not provide.
- **`graph_from_corpus`** (`crotdalam.analyzers.graph`) — derives an
  authorship/interaction graph from video and comment records so
  `NetworkAnalyzer` has edges to rank; node IDs are namespaced so a reused id
  cannot merge a user and a video.
- **`extract` and `correlate` CLI commands**, plus shell completion for them.
- **Indonesian scam lexicon**, expanded from 6 to 10 categories: robot trading,
  titip dana, flip/gestun, pinjol ilegal, judol/slot, and "admin resmi"
  impersonation, alongside the existing English/Indonesian phrases.
- `tests/test_custody.py` and `tests/test_osint.py` — 20 new tests (59 → 79).

### Changed
- The record contract gains optional `collected_at` and a typed `provenance`;
  `validate_record` validates both. Report `normalize` passes them through.

### Not added (deliberately)
- CAPTCHA solving, request-signature forging (`X-Bogus`, `msToken`), evasion
  proxy rotation and browser-fingerprint spoofing were requested and declined.
  Their function is to defeat a third party's access controls, and evidence
  obtained that way is the evidence most easily excluded — which defeats the
  tool's forensic purpose. See [`docs/SCOPE.md`](docs/SCOPE.md).

## [0.2.0] — 2026-09-08

First packaged release. A QA and QC pass audited every module; findings and
their resolutions are recorded in [`docs/QA-REPORT.md`](docs/QA-REPORT.md).

### Added
- Python packaging: `pyproject.toml`, `requirements.txt` and a `crotdalam`
  console entry point. The project is now installable with `pip install -e .`.
- `crotdalam/config/settings.py` — a validated, frozen `Settings` dataclass with
  `CROTDALAM_*` environment support. Encryption keys are referenced by variable
  name and never stored in configuration.
- `crotdalam/__init__.py`, `crotdalam/core/__init__.py`,
  `crotdalam/config/__init__.py` and `tests/__init__.py`, making the package
  discoverable by build backends rather than an implicit namespace package.
- `tests/test_config.py` — 10 regression tests covering settings validation,
  environment parsing, engine-absence handling and optional provenance.
- Complete documentation set under `docs/`, plus `SECURITY.md`,
  `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue and pull request templates and
  a CI workflow.
- Project banner in `images/banner.png`.

### Changed
- Commands that require the unshipped `crotdalam.core.engine` (`search`,
  `analyze --username`, `crawl`, `monitor`, `gui`) now fail with an actionable
  message naming the offline alternatives, instead of a raw
  `ModuleNotFoundError`.
- Report generators accept records without `source_url`, `timestamp` or
  `sha256`, matching the storage and collector contracts, which have always
  treated them as optional. Absent provenance renders as `Not supplied` rather
  than being invented or causing a failure.
- The sentiment lexicon no longer contains `terima kasih`, which the tokenizer
  split into `terima` and `kasih` — words that alone mean "accept" and "give"
  and produced false positives. `makasih` replaces it.
- `.gitignore` covers build artifacts, coverage output, virtual environments
  and the generated `data/` tree.

### Fixed
- `crotdalam/ui/README.md` referred to `crotdalam.core.database.Database`; the
  module is `crotdalam.utils.database.Database`.

### Known gaps
- `crotdalam.core.engine` is not implemented, so no command performs live
  collection. See [`docs/SCOPE.md`](docs/SCOPE.md) and
  [`docs/ROADMAP.md`](docs/ROADMAP.md).
- `crotdalam/search/bulk.py` and `crotdalam/ui/bulk.py` are two different
  `BulkSearch` implementations with different contracts. Consolidation is
  tracked in the roadmap.
- `crotdalam/ui/gui.py` has no automated coverage; it needs a display.

## [0.1.0] — unreleased

Initial offline HAR import, analyzers, monitors, search, reports and interfaces.
