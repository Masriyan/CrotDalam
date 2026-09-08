# Reports

Four generators under `crotdalam.reports`, sharing one interface:

```python
generate(records, output, case_id="UNASSIGNED", analyst="Not specified") -> Path
```

```python
from crotdalam.reports import generate, HTMLReport

generate(records, "report.html", "html", "CD-2026-001", "Your Name")
HTMLReport().generate(records, "report.html", "CD-2026-001", "Your Name")
```

```sh
crotdalam report --input evidence.sqlite --format all --output ./exports \
    --case-id CD-2026-001 --analyst "Your Name"
```

## Guarantees common to every format

**Validation happens before writing.** An invalid corpus raises and no file is
created — a report is never half-written. Required fields are `data_type`,
`target` and `value`; `source_url`, `timestamp` and `sha256` are optional and
render as `Not supplied` when absent, matching the record contract in
[`DATA-MODEL.md`](DATA-MODEL.md).

**Record content is untrusted.** Every field originates from a third party and
is escaped for its destination format.

**Hashes are displayed, never verified.** A report shows the `sha256` it was
given and says so explicitly. It does not recompute it — use
`crotdalam validate` for that.

## HTML — the primary format

Self-contained, script-free, printable, and safe to open.

- Every untrusted field passes through `html.escape(quote=True)`.
- `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline';
  img-src data:; base-uri 'none'; form-action 'none'` — even if escaping were
  bypassed, there is no script execution, no network fetch and no form target.
- No JavaScript, no external stylesheet, no web font, no remote image. The file
  works offline, forever, from any directory.
- The risk chart is inline SVG with an accessible `<title>`.
- Print stylesheet avoids breaking headings from their content.
- Responsive down to 640 px.

Structure: masthead (case ID, analyst, generation time) · summary (record count,
distinct targets, risk-label chart) · evidence register (one numbered article
per record with type, target, capture time, source, supplied hash, and the value
as formatted JSON) · footer stating the schema version and the hash caveat.

The risk chart counts `value.risk` or `value.severity` where the label is
`critical`, `high`, `medium`, `low` or `info`. Anything else counts as
`unrated`. **The report infers no score of its own** — to populate the chart,
write an analyzer's label into the record value:

```python
record["value"]["risk"] = ScamDetector().analyze(record)["risk_level"]
```

## PDF

Same content through ReportLab. Requires the optional dependency:

```sh
pip install -e ".[pdf]"
```

Without it, `PDFReport` raises `RuntimeError` naming the fix. With
`--format all`, the other three formats are still written and the command exits
1 with a PDF-specific message on stderr.

Long values flow across pages line by line rather than overflowing a single
frame. Document metadata carries the title and analyst.

**Limitation:** ReportLab's default fonts do not cover every Unicode glyph.
Non-Latin scripts and emoji in captions may render as boxes. HTML and JSON
preserve them correctly; prefer HTML when the source text is multilingual.

## CSV

One row per record, columns `case_id, analyst, data_type, target, value,
source_url, timestamp, sha256`. The `value` column holds compact JSON.

- **UTF-8 with BOM**, so Excel detects the encoding.
- **Formula-injection protection**: any cell starting with `=`, `+`, `-`, `@`,
  or leading whitespace is prefixed with `'`. Without this, a caption reading
  `=HYPERLINK(...)` would execute when the analyst opens the file.

## JSON

Schema version 1.0 — the machine-readable format for pipelines.

```json
{
  "schema_version": "1.0",
  "case_id": "CD-2026-001",
  "analyst": "Your Name",
  "generated_at": "2026-09-08T12:25:00.123456+00:00",
  "records": [ … ]
}
```

Round-trips through `load_json`, which accepts this envelope or a bare record
array and **rejects an unrecognized `schema_version`** rather than parsing it
optimistically. Unicode is preserved (`ensure_ascii=False`); `NaN` and
`Infinity` are rejected.

## `--format all`

Writes `report.html`, `report.json`, `report.csv` and `report.pdf` into the
directory given by `--output`. A missing PDF backend does not prevent the other
three. Explicit output files are overwritten without prompting.

## Before you share a report

A report contains everything the records contain: captions, biographies,
usernames, user IDs and comment text — personal data about real people, some of
whom are uninvolved third parties.

- Review and redact before distribution.
- Set `--case-id` and `--analyst`; an unattributed forensic report is hard to
  defend later.
- Reports inherit their directory's permissions, unlike the evidence database,
  which is created `0600`. Place exports somewhere appropriately restricted.
- Read [`LEGAL-AND-ETHICS.md`](LEGAL-AND-ETHICS.md) on disclosure and retention.

## Adding a format

Implement `generate(records, output, case_id, analyst) -> Path`, call
`normalize()` or `envelope()` first so validation precedes writing, and register
the class in the `REPORTS` map in `reports/__init__.py`. The CLI picks it up
automatically, including in `--format all`.
