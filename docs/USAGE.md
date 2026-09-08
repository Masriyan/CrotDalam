# Command Reference

```
crotdalam [--corpus PATH] [--database PATH] <command> [options]
```

`--corpus` and `--database` are accepted before or after the command name.
If you installed from a clone without `pip install`, substitute
`python -m crotdalam.ui.cli` for `crotdalam`.

## Command status

| Command | Runs offline | Notes |
|---|---|---|
| `import-har` | Yes | Primary ingestion path |
| `validate` | Yes | Recomputes checksums and verifies the evidence chain |
| `extract` | Yes | Pulls pivotable selectors from a corpus |
| `correlate` | Yes | Finds accounts sharing content or contact selectors |
| `analyze --input` | Yes | Descriptive counts |
| `report` | Yes | All four formats |
| `config show` | Yes | |
| `session list` / `proxy list` | Yes | Reads a supplied JSON array only |
| `shell` | Yes | Wraps the offline commands |
| `search` | **No** | Needs `crotdalam.core.engine` |
| `analyze --username` | **No** | Needs `crotdalam.core.engine` |
| `crawl` | **No** | Needs `crotdalam.core.engine` |
| `monitor` | **No** | Needs `crotdalam.core.engine` |
| `gui` | **No** | Needs the engine and Tkinter |

Unavailable commands exit 1 with an explanation. See [`SCOPE.md`](SCOPE.md).

---

## `import-har`

Ingest a local HAR capture. Never replays requests, never opens a network
connection, never extracts credentials.

```sh
crotdalam import-har CAPTURE.har --inspect
crotdalam import-har CAPTURE.har --database evidence.sqlite
```

| Flag | Meaning |
|---|---|
| `input` | Path to the HAR file (positional, required) |
| `--inspect` | Print sanitized metadata and counts; write nothing |
| `--database` | Destination SQLite file; required unless `--inspect` |

Prints a JSON summary: entry count, status and MIME distributions, body
availability, importable record counts by type, duplicates, sanitized endpoints,
JSON key shapes, and `stored` (records written by this invocation).

`--inspect` output is designed to be safe to share: hosts, path segments and
JSON keys outside the allowlist are redacted, and no record value is ever
printed. Full detail in [`HAR-IMPORT.md`](HAR-IMPORT.md).

Importing the same capture twice **appends**; it is not a cross-run upsert.

## `validate`

```sh
crotdalam validate --input evidence.sqlite
crotdalam validate --input records.json --format json
```

| Flag | Meaning |
|---|---|
| `--input` | `.json`, `.db`, `.sqlite` or `.sqlite3` file (required) |
| `--format` | Force `json` or `sqlite` when the suffix is ambiguous |

Loads every record, checks it against the contract, and for SQLite recomputes
each SHA-256 checksum **and verifies the tamper-evident evidence chain**:

```
Valid: 156 records; evidence chain intact (unkeyed seal a5647f6468a8da34…)
```

A checksum mismatch, or a chain broken by deleted, reordered or altered
records, raises and exits 1. The seal is HMAC-keyed when the database is
encrypted, a bare hash chain otherwise — see [`STORAGE.md`](STORAGE.md).

## `extract`

Pull pivotable selectors — the identifiers an investigator follows — out of a
corpus. Offline lexical extraction; nothing is resolved, validated or contacted.

```sh
crotdalam extract --input evidence.sqlite | jq '.counts, .distinct'
```

Finds URLs, `@mentions`, `#hashtags`, emails, phone numbers, BTC/ETH wallet
addresses and messaging handles (`t.me`, `wa.me`, `chat.whatsapp.com`, …).
Output carries, per selector type, the values with occurrence counts, the
distinct count, and `by_target` attribution so a value appearing under many
accounts stands out as a pivot. On the sample capture this surfaced 142
hashtags, 33 mentions and a phone number. See [`ANALYZERS.md`](ANALYZERS.md).

## `correlate`

Find accounts across the corpus that share a normalized caption or a contact
selector — the strongest offline signal of coordinated inauthentic behavior.

```sh
crotdalam correlate --input evidence.sqlite --min-accounts 2
```

| Flag | Default | Meaning |
|---|---|---|
| `--input` | required | `.json`, `.db`, `.sqlite` or `.sqlite3` |
| `--min-accounts` | `2` | Distinct accounts a cluster needs before it is reported |

Output lists shared captions, shared selectors, and the coordinated account
sets they connect. Shared content also arises from duets, reposts and templates,
and distinct usernames do not prove distinct people — the result is a lead, not
a determination. See [`ANALYZERS.md`](ANALYZERS.md).

## `analyze`

```sh
crotdalam analyze --input evidence.sqlite      # offline
crotdalam analyze --username someuser          # needs the engine
```

The `--input` form prints descriptive counts only — record total, distinct
targets and a breakdown by data type. It performs no risk inference. For scoring
heuristics, use the analyzer APIs in [`ANALYZERS.md`](ANALYZERS.md).

## `report`

```sh
crotdalam report --input evidence.sqlite --format all --output ./exports \
    --case-id CD-2026-001 --analyst "Your Name"
```

| Flag | Default | Meaning |
|---|---|---|
| `--input` | required | `.json`, `.db`, `.sqlite` or `.sqlite3` |
| `--output` | required | Output file, or a directory when `--format all` |
| `--format` | `html` | `html`, `json`, `csv`, `pdf` or `all` |
| `--case-id` | `UNASSIGNED` | Printed on the cover and every CSV row |
| `--analyst` | `Not specified` | Printed on the cover and in PDF metadata |

With `--format all`, the output directory receives `report.html`, `report.json`,
`report.csv` and `report.pdf`. If ReportLab is missing, the other three are
still written and the command exits 1 with a PDF-specific error. Existing files
are overwritten. Details in [`REPORTS.md`](REPORTS.md).

## `config show`

```sh
crotdalam config show
crotdalam --database ops.sqlite config show
```

Prints effective settings as JSON, after applying `CROTDALAM_*` variables and
command-line overrides. Encryption keys are referenced by variable *name*; no
key value is ever printed. See [`CONFIGURATION.md`](CONFIGURATION.md).

## `session list` / `proxy list`

```sh
crotdalam session list --file sessions.json
crotdalam proxy list --file proxies.json
```

Reads and echoes a JSON array you supply. These commands do not create sessions,
test proxies, configure routing or make connections. Without `--file` they print
a notice and exit 0.

## `shell`

```sh
crotdalam shell
```

An interactive wrapper over the same commands, with readline history and tab
completion where available. Input is parsed with `shlex` and `argparse` and is
never handed to an OS shell — there is no `eval`, no `subprocess` and no shell
escape. History is memory-only, capped at 500 entries.

Built-ins: `help`, `help <command>`, `history`, `exit` / `quit` / Ctrl-D.

Global options passed to `crotdalam shell` apply to every command in the session:

```sh
crotdalam --database evidence.sqlite shell
```

## `search`, `crawl`, `monitor`, `gui`

These require the unshipped collection engine and exit 1 immediately. Their
flags are documented in `crotdalam --help` and preserved for when a transport is
supplied. See [`SCOPE.md`](SCOPE.md).

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Handled error — bad input, missing file, absent engine, PDF backend missing |
| 2 | `argparse` usage error — unknown command or malformed flags |
| 130 | Interrupted with Ctrl-C |

Handled errors print `crotdalam: <message>` to stderr, never a traceback. JSON
output goes to stdout, so it can be piped:

```sh
crotdalam import-har capture.har --inspect | jq '.data_types'
```

## A complete offline workflow

```sh
crotdalam import-har capture.har --inspect                          # review first
crotdalam import-har capture.har --database evidence.sqlite         # ingest
crotdalam validate --input evidence.sqlite                          # verify + chain
crotdalam extract --input evidence.sqlite                           # pivot selectors
crotdalam correlate --input evidence.sqlite                         # coordination
crotdalam analyze --input evidence.sqlite                           # summarize
crotdalam report --input evidence.sqlite --format all \
    --output ./exports --case-id CD-2026-001 --analyst "Your Name"  # report
```

Measured on a 144 MB, 1,696-entry capture: 156 records in 0.93 s, 640 MB peak RSS.
