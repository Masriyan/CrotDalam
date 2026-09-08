# Data Model

## The record contract

A record is a plain JSON object. It is the single currency between collectors,
storage, search, analyzers, monitors and reports.

```json
{
  "data_type": "video",
  "target": "7123456789012345678",
  "value": { "id": "7123456789012345678", "desc": "...", "stats": {} },
  "source_url": "https://www.tiktok.com/api/post/item_list/",
  "collected_at": "2026-09-08T04:49:52.393Z",
  "timestamp": "2026-09-08T05:25:33Z",
  "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "provenance": {
    "collector": "har",
    "entry_index": 201,
    "source_name": "capture.har",
    "source_sha256": "8102bd145d02cc9197704fc21c22c9cf00c5b26c6d0e560661a575b1e8593a5a"
  }
}
```

### Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `data_type` | non-empty string | **yes** | Record kind: `video`, `profile`, `comment`, `follower`, `following`, `hashtag`, `search_status`, `search_error` |
| `target` | non-empty string | **yes** | Identifier this record is about |
| `value` | object | **yes** | The payload; structure depends on `data_type` |
| `source_url` | string | no | Sanitized origin. Absent means provenance was not recorded |
| `collected_at` | string | no | When the evidence was **observed at its source** (HAR `startedDateTime`), aware ISO 8601 |
| `timestamp` | string | no | When the record **entered this database**, aware ISO 8601. Naive timestamps are rejected |
| `sha256` | string | no | Checksum of the canonical `value`, added by `Database.store` |
| `provenance` | object | no | Collector detail: `collector`, `entry_index`, `source_name`, `source_sha256` |

Three fields are required. The rest are optional at every layer — storage,
collectors and reports agree on this. A report renders absent provenance as
`Not supplied` rather than failing or inventing a value.

**`collected_at` versus `timestamp`.** These are deliberately distinct.
`collected_at` is when the capture observed the data; `timestamp` is when it was
imported. Conflating them — as versions before 0.3.0 did — makes temporal
analysis describe the analyst's import run instead of the target's activity.
`TemporalAnalyzer` prefers a content timestamp (`createTime`), then
`collected_at`, and never falls back to import time.

**`source_sha256`.** The SHA-256 of the exact HAR file bytes ingested. Every
record from one capture carries the same digest, so a finding ties back to a
specific source file, not merely to an entry index in some unnamed capture. See
the chain-of-custody section of [`LEGAL-AND-ETHICS.md`](LEGAL-AND-ETHICS.md).

### Constraints

| Constraint | Value | Enforced in |
|---|---|---|
| Records per corpus | 10,000 | `collectors/base.import_records` |
| Bytes per record | 1,000,000 | `collectors/base.validate_record` |
| Searchable characters per record | 100,000 | `search/keyword.KeywordSearch` |
| Text characters per analyzed field set | 100,000 | `analyzers/common.text_of` |
| Records per analysis | 10,000 | `analyzers/common.rows` |

Values must be JSON-compatible with `allow_nan=False`. `NaN` and `Infinity` are
rejected, not coerced.

## Canonical form and checksums

`utils/helpers.canonical_json` produces the byte string that is hashed:

```python
json.dumps(value, sort_keys=True, ensure_ascii=False,
           separators=(",", ":"), allow_nan=False).encode("utf-8")
```

Sorted keys and fixed separators make the digest stable across runs and
platforms. `sha256` covers the `value` object only, not metadata.

A checksum detects accidental corruption. It is stored beside the data and does
not establish authenticity — anyone who can rewrite the value can rewrite the
checksum. See [`STORAGE.md`](STORAGE.md).

## Timestamps

All timestamps are timezone-aware, normalized to UTC, and serialized with `Z`.

`utils/helpers.parse_timestamp` rejects a naive timestamp outright. Analyzers
accept either a Unix-seconds number or an aware ISO 8601 string; anything naive
is counted as excluded rather than assumed to be local time. This matters for
`TemporalAnalyzer`, which would otherwise silently shift activity distributions.

## Value shapes by type

These are the shapes the HAR importer produces. Fields are allowlisted — an
unrecognized field is dropped, not carried through.

### `video`

```json
{
  "id": "…", "desc": "…", "createTime": 1725753600,
  "video":  { "duration": 15, "width": 1080, "height": 1920 },
  "author": { "id": "…", "uniqueId": "…", "nickname": "…", "verified": false },
  "stats":  { "diggCount": 0, "playCount": 0, "commentCount": 0,
              "shareCount": 0, "collectCount": 0 },
  "availability": "local_har_response_only"
}
```

### `profile`

```json
{
  "id": "…", "uniqueId": "…", "nickname": "…", "signature": "…",
  "verified": false, "privateAccount": false,
  "stats": { "followerCount": 0, "followingCount": 0,
             "heartCount": 0, "videoCount": 0, "diggCount": 0 },
  "availability": "local_har_response_only"
}
```

`uniqueId` is required; a profile without one is rejected.

### `comment`

```json
{
  "cid": "…", "aweme_id": "…", "text": "…", "create_time": 1725753600,
  "digg_count": 0, "reply_comment_total": 0, "reply_id": "…",
  "user": { "uid": "…", "unique_id": "…", "nickname": "…" },
  "availability": "local_har_response_only"
}
```

`text` is required; a comment without one is rejected.

### `availability`

| Value | Meaning |
|---|---|
| `local_har_response_only` | Came from a HAR response body; not re-fetched or verified |
| `public_hydration_only` | Parsed from a public page's embedded JSON |

This field records how far the evidence can be trusted, and is preserved into
reports.

## Report schema (version 1.0)

`JSONReport` and the `envelope` helper produce:

```json
{
  "schema_version": "1.0",
  "case_id": "CD-2026-001",
  "analyst": "Your Name",
  "generated_at": "2026-09-08T12:25:00.123456+00:00",
  "records": [ /* normalized records */ ]
}
```

`load_json` accepts either this envelope or a bare record array. An envelope
with a different `schema_version` is rejected rather than parsed optimistically.

Bump `SCHEMA_VERSION` in `reports/common.py` for any change to record structure
that a downstream consumer would notice.

## Validation layers

Three functions validate records; they are intentionally not identical.

| Function | Used by | Checks |
|---|---|---|
| `utils.models.validate_record` | `Database.store`, monitors | Required fields, types, timestamp awareness, JSON-serializability |
| `collectors.base.validate_record` | Collectors, search | The above, plus a 1 MB ceiling; **returns a detached deep copy** |
| `reports.common.normalize` | All report generators | Required fields, optional-field types; returns detached copies |

The collector and report variants return copies, so a caller cannot mutate a
corpus by holding a reference to a result. That is why search results are safe
to modify.

## Alerts

Monitors emit alerts, which are not records:

```json
{
  "type": "profile_bio_changed",
  "target": "someuser",
  "timestamp": "2026-09-08T00:00:00Z",
  "details": { "before": "…", "after": "…" },
  "id": "sha256 of the above four fields"
}
```

The `id` is a content hash, which makes deduplication and idempotent alert
delivery possible. See [`MONITORS.md`](MONITORS.md).
