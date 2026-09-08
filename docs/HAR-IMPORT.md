# HAR Import

The HAR importer is CrotDalam's primary ingestion path. It reads a browser
capture you already lawfully hold and turns recognized TikTok responses into
contract records.

```sh
crotdalam import-har capture.har --inspect                     # review first
crotdalam import-har capture.har --database evidence.sqlite    # then ingest
```

```python
from crotdalam.collectors.har_collector import import_har
records, summary = import_har("capture.har", inspect_only=False)
```

## What it does not do

Import is strictly offline. The importer never replays a request, never opens a
socket, never logs in, never generates a signature and never extracts
credentials. It reads a file and writes a database.

Request headers, cookies, `postData`, timings and raw response objects are
discarded — none of them reach the record set. Query strings, URL fragments and
URL credentials are always dropped.

## Producing a capture

In Chrome or Firefox DevTools, open the **Network** tab, browse the pages you
are authorized to examine, then **Export HAR**. Capture only what your
authorization covers, and read [`LEGAL-AND-ETHICS.md`](LEGAL-AND-ETHICS.md)
before you start.

A HAR contains everything the browser sent and received, including your session
cookies and authentication headers. **Treat the raw HAR as a credential.**
CrotDalam ignores those fields, but the file on disk still holds them.

## Inspect before you import

`--inspect` parses the capture and reports what it found without writing
anything and without emitting a single record value.

```sh
crotdalam import-har capture.har --inspect | jq '.data_types, .body_availability'
```

Output on a real 144 MB capture:

```json
{
  "source": { "name": "capture.har", "sha256": "8102bd145d02cc91…" },
  "entries": 1696,
  "importable": 156,
  "data_types": { "video": 154, "profile": 2 },
  "duplicates": 1,
  "rejected_candidates": 0,
  "body_availability": { "opaque": 782, "missing": 443, "json": 442, "empty": 29 },
  "endpoints": [ /* 109 sanitized endpoints */ ],
  "json_key_shapes": [ /* 60 allowlisted key shapes */ ]
}
```

`source.sha256` is the SHA-256 of the exact file bytes ingested; it is the same
digest carried on every record's `provenance`, so a summary and the records it
produced can be tied to one capture.

`--inspect` output is designed to be safe to share with a colleague or attach to
a case note. Values are never included; only counts, allowlisted key names and
sanitized URLs.

### Body availability

| State | Meaning |
|---|---|
| `json` | Parsed successfully; the only state that can yield records |
| `opaque` | Present but not JSON — media, protobuf, HTML, binary |
| `missing` | The capture recorded no response body |
| `empty` | Zero-length body |
| `oversized` | Exceeds the 16 MiB per-body limit |
| `unsupported_encoding` | An encoding other than none or `base64` |
| `invalid_base64` | Declared `base64` but did not decode |
| `malformed_entry` | The HAR entry was not an object |

Most entries in a real capture are `opaque` or `missing`. That is normal: video
segments, images and scripts dominate a browsing session.

## Redaction model

Two allowlists govern what appears in a summary.

**Hosts.** Only TikTok service domains survive: `tiktok.com`, `tiktokv.com`,
`tiktokcdn.com`, `byteoversea.com`, `ibytedtos.com`, `ttwstatic.com`,
`muscdn.com`. Everything else becomes `redacted.invalid`. Subdomain labels
outside a known set are replaced with `redacted`.

**Path segments.** A segment is kept only if it appears in a fixed vocabulary of
~180 known API words (`api`, `item_list`, `user`, `detail`, `comment`, …).
Anything else — a username, a video ID, an arbitrary slug — becomes
`[redacted]`, because an unknown segment may itself be an identifier.

Real output:

```
https://www.tiktok.com/api/post/item_list/          ← fully recognized
https://www.tiktok.com/api/[redacted]/item_list/    ← unknown middle segment
https://mon.tiktokv.com/[redacted]/settings/[redacted]
https://redacted.invalid/[redacted]/v3/userinfo     ← non-TikTok host
```

**JSON key shapes** are reported the same way: a key is named only if it is in
the allowlist, otherwise it is counted as `<other>`. You learn the *shape* of the
data without learning its contents.

## Extraction

Only responses from `www.tiktok.com`, `tiktok.com`, `m.tiktok.com` and
`api.tiktok.com` may produce records — a recognized container on some other host
is ignored.

Supported containers:

| Container | Produces |
|---|---|
| `itemList`, `item_list`, `items` | `video` |
| `comments` | `comment` |
| `userInfo` (with `user` and `stats`) | `profile` |
| `UserModule.users` (with `UserModule.stats`) | `profile` |

Fields are allowlisted per type, and only scalar values are kept — strings,
finite numbers and booleans. Nested response objects and signed media URLs are
not retained. Shapes are listed in [`DATA-MODEL.md`](DATA-MODEL.md).

Records are rejected when a required field is missing: a `video` needs a `video`
object and an `id`, a `profile` needs a `uniqueId`, a `comment` needs `text`.
Rejections are counted in `rejected_candidates`.

**Unrecognized schemas are not inferred.** If TikTok changes a response shape,
the importer reports zero records for it rather than guessing.

## Deduplication

Identity is `(data_type, id, sha256(normalized value))`. Within one capture:

- The same record seen twice is counted in `duplicates` and stored once.
- The same ID with **changed** content is kept as a separate record — that
  change is evidence.

Deduplication is **local to one invocation**. Importing the same capture twice
appends the records again; it is not a cross-run upsert. `importable` counts
records after capture-local deduplication; `stored` counts what this invocation
wrote.

## Limits

| Limit | Value | Behaviour on breach |
|---|---|---|
| File size | 200 MiB | `ValueError` before parsing |
| Response body | 16 MiB decoded | Body marked `oversized`, import continues |
| HAR entries | 100,000 | `ValueError` before parsing |
| JSON traversal nodes | 500,000 | `ValueError`, no partial result |
| Nesting depth | 64 | `ValueError`, no partial result |

Document-level and traversal failures happen **before** the database is opened,
so a rejected capture cannot leave a half-written database. Individual writes
are transactional, but an import is not one atomic batch: an error partway
through leaves earlier records committed.

### Memory

The file is parsed in memory, not streamed. Peak RSS can substantially exceed
the file size. Measured: a 144 MB capture with 1,696 entries used **640 MB peak
RSS and completed in 0.93 s**. Budget roughly 4–5× the file size.

## Provenance

Each record carries:

```json
"source_url": "https://www.tiktok.com/api/post/item_list/",
"collected_at": "2026-09-08T04:49:52.393Z",
"provenance": {
  "collector": "har",
  "entry_index": 42,
  "source_name": "capture.har",
  "source_sha256": "8102bd145d02cc91…"
}
```

- `entry_index` is the zero-based position in `log.entries`, so a finding traces
  back to the exact entry in the original capture.
- `source_sha256` is the SHA-256 of the whole capture file, tying the record to
  a specific source rather than an entry index in an unnamed file.
- `collected_at` is parsed from the entry's `startedDateTime` — when the data
  was observed, kept distinct from the import time in `timestamp`. A naive or
  missing value is dropped, never guessed.

The sanitized URL is stored, not the raw one.

## Privacy

**Token removal is not anonymization.** Video captions, profile biographies,
usernames, user IDs and comment text are personal data, and they remain personal
data after import. The redaction described above protects *summaries*, not the
record set — the record set is evidence, and it is meant to retain content.

Consequently:

- Keep both the HAR and the resulting database access-restricted.
- Apply a retention policy and delete when the case closes.
- Review and redact before sharing any downstream report.
- Free text may itself contain sensitive material the importer cannot detect.

The database uses `0600` permissions but this command does **not** encrypt it.
For encryption at rest, see [`STORAGE.md`](STORAGE.md).

`.gitignore` covers `*.har` and `*.sqlite`. Ignore rules do not untrack a file
that was already committed.

## What cannot be imported

HTML hydration payloads, protobuf responses, media bodies, and entries whose
response body is absent or opaque. For public page hydration, use
`ProfileCollector` and `VideoCollector` — which need a transport this release
does not ship ([`SCOPE.md`](SCOPE.md)).
