# Troubleshooting

Errors print as `crotdalam: <message>` on stderr and exit 1. Tracebacks indicate
a bug — please [report one](https://github.com/Masriyan/CrotDalam/issues).

## Command cannot run

> **The network-facing collection engine (crotdalam.core.engine) is not part of
> this release, so 'search' cannot run.**

Expected. `search`, `analyze --username`, `crawl`, `monitor` and `gui` need a
transport this release does not ship. Use the offline path:

```sh
crotdalam import-har capture.har --database evidence.sqlite
crotdalam analyze --input evidence.sqlite
```

See [`SCOPE.md`](SCOPE.md).

> **argument command: invalid choice: 'config show'**

The command and its argument are separate tokens. Write `crotdalam config show`,
not `crotdalam "config show"`. In zsh, an unquoted variable does not word-split
— use `${=cmd}` or an array.

## HAR import

> **HAR exceeds the 200 MiB file limit**

Capture a narrower session, or split the HAR by entry.

> **HAR requires log.entries with at most 100000 entries**

Either the file is not a HAR, or it exceeds the entry ceiling. Verify:

```sh
jq '.log.entries | length' capture.har
```

> **Invalid HAR JSON**

Truncated or malformed export. Re-export from DevTools; check the file is
complete with `jq . capture.har > /dev/null`.

> **HAR JSON traversal budget exceeded**

A response body exceeded 500,000 nodes or 64 levels of nesting. This is
fail-closed by design — no partial result is returned. Narrow the capture.

> **import-har requires --database unless --inspect is used**

Add `--database evidence.sqlite`, or use `--inspect` to review without writing.

### Import succeeded but found 0 records

Normal for many captures, and not an error. Check `--inspect` output:

```sh
crotdalam import-har capture.har --inspect | jq '.body_availability, .data_types'
```

- Mostly `opaque` or `missing` — the capture holds media and scripts, not API
  JSON. Browse profile and video pages, letting them load fully, before
  exporting.
- `json` bodies but zero `importable` — the responses are not in a recognized
  container. Unrecognized schemas are never guessed at. See
  [`HAR-IMPORT.md`](HAR-IMPORT.md).
- Records exist but `rejected_candidates` is high — required fields were
  missing: a `video` needs `video` and `id`, a `profile` needs `uniqueId`, a
  `comment` needs `text`.

### The import used far more memory than expected

The document is parsed in memory, not streamed. Budget 4–5× the file size; a
144 MB capture peaked at 640 MB RSS.

## Storage

> **database encryption mode does not match supplied key**

You opened a plaintext database with a key, or an encrypted one without.
A database's mode is fixed at creation. Check `CROTDALAM_ENCRYPTION_KEY_ENV`.

> **invalid key check**

Wrong key for this database. There is no recovery — see [`STORAGE.md`](STORAGE.md).

> **AES-256 requires a 32-byte key** / **key must be standard base64…**

Generate one properly:

```sh
python -c "from crotdalam.utils.crypto import generate_key; print(generate_key())"
```

> **record checksum mismatch**

A stored value no longer matches its checksum: file corruption, or the database
was modified outside CrotDalam. Re-import from the original capture.

> **database is locked**

Another process holds it. WAL allows concurrent readers but one writer; do not
run two monitors against the same row.

## Reports

> **PDF export requires ReportLab: pip install reportlab**

```sh
pip install -e ".[pdf]"
```

With `--format all`, the other three formats are still written; the command
exits 1 with this message.

> **Record N missing fields: value**

The record lacks a required field. Only `data_type`, `target` and `value` are
required; provenance is optional. See [`DATA-MODEL.md`](DATA-MODEL.md).

> **Unsupported or missing report schema_version**

The JSON is not a version 1.0 envelope. Pass a bare record array, or an envelope
with `"schema_version": "1.0"`.

### PDF shows boxes instead of text

ReportLab's default fonts lack glyphs for many scripts and emoji. Use HTML or
JSON for multilingual content.

### Excel mangles the CSV

CSV is written UTF-8 with BOM, which Excel honours. If columns run together,
import with comma as the delimiter rather than double-clicking the file.

## Search

> **Fuzzy search timed out; narrow the query/corpus**
> **Regex search total time budget exceeded**

Budgets are 20 ms per record and 2 s per search. Reduce the corpus, simplify the
pattern, or prefer `KeywordSearch` for literal matching.

> **Searchable record exceeds 100000 characters**

One record is too large to index. Filter it out before constructing the engine.

## Installation

> **ModuleNotFoundError: No module named 'bs4' / 'networkx' / 'regex'**

```sh
pip install -e .
```

> **GUI requires Tkinter (install your OS python3-tk package)**

```sh
sudo dnf install python3-tkinter     # Fedora
sudo apt install python3-tk          # Debian/Ubuntu
```

> **Cannot open GUI display**

No display available. The GUI cannot run over a plain SSH session; use the CLI.

### `crotdalam: command not found`

The virtual environment is not active, or you did not install. Either
`source .venv/bin/activate`, or run `python -m crotdalam.ui.cli` directly.

## Still stuck

Open an issue with your Python version, OS, the exact command, and the full
error. **Never attach a real HAR or evidence database** — build a minimal
synthetic reproducer instead.
