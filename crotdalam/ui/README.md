# Interfaces and Reports

Console entry point: `crotdalam.ui.cli:main`. Without packaging registration,
run `python -m crotdalam.ui.cli --help`.

## Supported Commands

```text
search --keyword TEXT [--limit 20]
search --username NAME
analyze --username NAME
analyze --input records.json
report --format all|json|html|pdf|csv --input FILE --output PATH
crawl --csv keywords.csv --threads 4
validate --input FILE [--format json|sqlite]
extract --input FILE
correlate --input FILE [--min-accounts 2]
config show
session list [--file sessions.json]
proxy list [--file proxies.json]
monitor --keyword TEXT --rounds 3 --interval 60
shell
gui
```

`--corpus` and `--database` work before or after a command. Input suffixes:
`.json`, `.db`, `.sqlite`, `.sqlite3`. JSON accepts a record array or a version
1.0 report envelope. `analyze` gives descriptive counts only. Search output is
the full database snapshot, including existing records. BulkSearch performs
keyword searches from a CSV with `keyword`, `username`, or `target` header;
it is not a general-purpose web crawler. Monitor performs a bounded number
of searches, not a background service or an alerting system.

Session/proxy listing reads an explicitly supplied JSON array; it does not
create sessions, test proxies, or configure routing. Shell history stays in
memory, with readline editing/completion when available. Commands are parsed
with shlex and argparse, never executed by an OS shell.

GUI implements only keyword search, a record table, selected-record details,
status, and report export. Engine work and export use worker threads; Tk
updates use a queue on the main thread. Closing is blocked while work is
active so the engine can clean up its database. There is no cancellation UI.

## APIs

`HTMLReport`, `PDFReport`, `CSVReport`, `JSONReport` are exported from
`crotdalam.reports`. Each exposes:

```python
generate(records, output, case_id="UNASSIGNED", analyst="Not specified") -> Path
```

The package also exports
`generate(records, output, format="html", case_id="UNASSIGNED", analyst="Not specified")`.
The `all` format belongs to CLI orchestration: output is a directory containing
`report.html`, `report.json`, `report.csv`, and `report.pdf`. Missing ReportLab
does not prevent other formats from being written, but yields exit status 1
with an explicit PDF error. Explicit output files are overwritten.

HTML is self-contained, script-free, escaped, responsive, and printable. Risk
charts count supplied `value.risk` or `value.severity` labels only. Supplied
hashes are displayed, not independently verified. CSV has UTF-8 BOM and
apostrophe protection for spreadsheet formulas. JSON has schema version 1.0,
case ID, analyst, generation timestamp, and records.

## Dependencies

- Standard library for reports (except PDF), CLI, bulk, and shell.
- Optional `reportlab` for PDF. Default PDF fonts do not guarantee all Unicode glyphs.
- Optional OS Tkinter package and a graphical display for GUI.
- Runtime core contract: `crotdalam.core.engine.Engine`,
  `crotdalam.config.settings.Settings`, `crotdalam.utils.database.Database`.

No database is opened by importing these modules. Engine contexts manage
collection database lifecycle. Standalone SQLite reading closes its Database
instance in `finally`.
