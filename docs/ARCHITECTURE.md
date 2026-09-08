# Architecture

## Data flow

```
   authorized HAR capture                 records you construct
            │                                      │
            ▼                                      ▼
  collectors/har_collector          collectors/base.import_records
   • allowlist extraction            • contract validation
   • redaction                       • 10k records, 1 MB each
   • dedup by kind+id+hash                    │
            └──────────────┬───────────────────┘
                           ▼
              ┌────────────────────────┐
              │   record contract      │   data_type, target, value
              │   (utils/models.py)    │   + optional provenance
              └────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┬─────────────────┐
        ▼                  ▼                  ▼                 ▼
  utils/database     analyzers/          search/           monitors/
  • SQLite WAL       • 6 per-record      • 4 engines       • 4 detectors
  • SHA-256 +          + 3 OSINT         • bounded         • persistent state
    hash chain       • evidence +          time/size       • alert dedup
  • AES-256-GCM        uncertainty
        │                  │                  │                 │
        └──────────────────┴────────┬─────────┴─────────────────┘
                                    ▼
                              reports/
                    HTML · PDF · CSV · JSON (schema 1.0)
```

## Package layout

| Package | Responsibility |
|---|---|
| `crotdalam.core` | Orchestration. Ships `Scheduler` only; the engine is absent by design |
| `crotdalam.collectors` | Turning external data into contract records |
| `crotdalam.analyzers` | Offline heuristics and OSINT engines over records; no I/O. Per-record (scam, phishing, bot, engagement, sentiment, temporal) and cross-corpus (`selectors`, `correlation`, `graph`) |
| `crotdalam.monitors` | Change detection between snapshots, with persistent state |
| `crotdalam.search` | Matching over a local corpus |
| `crotdalam.reports` | Rendering records into output formats |
| `crotdalam.ui` | CLI, interactive shell, optional Tk GUI |
| `crotdalam.utils` | Storage, crypto, hashing, validation, logging |
| `crotdalam.config` | Settings, lexicons, regular expressions |

## Design rules

These hold throughout the codebase. New code is expected to follow them; see
[`../CONTRIBUTING.md`](../CONTRIBUTING.md).

**1. Records are plain JSON dictionaries.** Not ORM entities, not custom
classes. `utils/models.py` defines a `TypedDict` for editor support and a
validation function; that is the whole model layer. Anything that round-trips
through `json.dumps`/`loads` is a valid record.

**2. Every boundary validates and fails closed.** Untrusted input is checked
against an allowlist, and a violation raises `ValueError` with a specific
message. Nothing is silently truncated, coerced or inferred. `har_collector`
raises rather than returning partial results when a traversal budget is
exceeded.

**3. Everything that touches untrusted input is bounded.** Bytes, item counts,
recursion depth and wall-clock time all have documented ceilings — 200 MiB per
HAR, 16 MiB per body, 100,000 entries, 500,000 traversal nodes, 64 levels of
nesting, 10,000 records, 100,000 characters per record, 20 ms per regex per
record. Limits live in module constants, are stated in the module docstring and
are covered by a test asserting the failure.

**4. Analyzers state their uncertainty.** Every analyzer returns `evidence`
(what matched, with weights) and `uncertainty` (how it can be wrong).
`risk_result` sets `is_probability: False` and `method: offline_heuristic` on
every score. No analyzer returns a verdict.

**5. Absent data stays absent.** A missing field is unknown, never zero, never
false, never a deletion. Monitors treat a missing value as "no observation", not
as a change. Reports render missing provenance as `Not supplied`.

**6. No module performs I/O at import.** Importing any part of `crotdalam`
opens no database, reads no configuration and makes no network call. Optional
and heavy dependencies (`reportlab`, `tkinter`, the engine) are imported inside
the function that needs them, so a missing optional dependency degrades one
feature rather than breaking the package.

**7. Secrets are referenced, never stored.** `Settings` holds
`encryption_key_env` — the *name* of an environment variable. The key value is
read on demand and never enters configuration output, logs or reports.

## Concurrency

The project is async where it waits and synchronous where it computes.

`Scheduler` (`core/scheduler.py`) runs fixed-delay polling jobs, each strictly
serial, bounded by a semaphore. A failing job is logged through the redacting
logger and the loop continues; it does not take down its siblings.

`BulkSearch` uses a pre-filled `asyncio.Queue` with a bounded worker pool.
Because `Queue.empty()` and `get_nowait()` are both synchronous, there is no
await between the check and the take, so no worker can race another.

`Database` guards its connection with an `RLock` and uses SQLite in WAL mode
with `check_same_thread=False`, so the Tk GUI can read from a worker thread.
`records()` pages against an initial high-water mark rather than holding a long
read lock.

## Trust boundaries

| Boundary | Untrusted side | Control |
|---|---|---|
| HAR file → records | Entire file | Host/path/key allowlists, size and traversal budgets, field allowlists |
| Page HTML → records | Entire document | JSON parsing only, never `eval`; script count, size and depth budgets |
| Record value → HTML report | Every field | `html.escape(quote=True)` on all output; CSP `default-src 'none'`; no scripts |
| Record value → CSV | Every field | `'` prefix on cells starting `=`, `+`, `-`, `@` or whitespace |
| Record value → log | Message and traceback | `RedactingFormatter` over credentials, tokens, cookies, proxy URLs |
| Shell input → command | Whole line | `shlex` + `argparse`; no `eval`, no `subprocess`, no OS escape |
| Config → key material | Key value | Referenced by variable name; never serialized |

## Extension points

`Engine` (`collectors/base.py`) is the transport protocol — implement `fetch`,
`collect` and `search` to supply your own. See [`SCOPE.md`](SCOPE.md) for the
responsibilities that come with it.

`ImportedCollector` is the base for local-only collectors. Subclassing it with a
`kind` attribute is the whole implementation; it refuses to accept an
engine-shaped object, so a subclass cannot quietly become a network client.

Report generators implement `generate(records, output, case_id, analyst) -> Path`
and register in the `REPORTS` map in `reports/__init__.py`.
