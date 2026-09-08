# Search

Four engines under `crotdalam.search`, all operating on a **local corpus** you
already hold. None of them queries TikTok.

```python
from crotdalam.search import KeywordSearch
results = KeywordSearch(records).search("giveaway", limit=20)
```

Each engine indexes `target` plus the JSON serialization of `value`, so a match
can occur anywhere in the record. Results are returned in corpus order as
**detached copies** — mutating a result cannot corrupt the corpus.

## Shared bounds

| Bound | Value |
|---|---|
| Records per corpus | 10,000 |
| Searchable characters per record | 100,000 |
| Query length | 1–512 characters |
| `limit` | 0–1,000 (`0` returns `[]`) |

An oversized record raises at construction rather than being silently truncated,
so you never search a partial corpus without knowing it.

## KeywordSearch

Casefolded literal substring matching. No wildcards, no tokenization, no
stemming. Predictable and fast.

```python
KeywordSearch(records).search("kirim otp", limit=50)
```

## FuzzySearch

Bounded edit-distance matching via the `regex` package, tolerating up to
`max_edits` insertions, deletions or substitutions.

```python
FuzzySearch(records, max_edits=1, timeout=0.02).search("giveaway")
```

| Parameter | Range | Meaning |
|---|---|---|
| `max_edits` | 0–3 | Also capped at `len(query) - 1` |
| `timeout` | 0 < t ≤ 0.1 s | Per record; 2 s total across the corpus |

Matches are anchored to whole-word boundaries, so a short query cannot match an
arbitrary substring inside a longer word. Capping edits below the query length
stops a two-character query from matching everything.

Use it for deliberate obfuscation — `g1veaway`, `f r e e`, character swaps.

## RegexSearch

Full regular expressions with a hard timeout.

```python
RegexSearch(records, timeout=0.02).search(r"(?i)wa\.me/\d+")
```

Matching is case-sensitive; use inline `(?i)`. An invalid pattern raises
`ValueError` rather than propagating a `regex.error`.

Both `FuzzySearch` and `RegexSearch` enforce **20 ms per record and 2 s per
search**, and raise on timeout rather than returning partial results. A
catastrophically backtracking pattern degrades into a clear error, not a hung
process.

## BulkSearch

Runs many queries against an `Engine` concurrently. Note there are two classes
with this name — see the warning below.

```python
from crotdalam.search import BulkSearch
records = await BulkSearch(engine).run("keywords.csv", threads=8, limit=20)
```

| Parameter | Bound |
|---|---|
| Input file | 1 MB |
| Queries | 1,000 |
| `threads` | 1–32 |
| Timeout | 30 s per engine call |

A `.csv` input needs exactly one `keyword` column (case-insensitive); any other
file is read as one query per non-blank line. Input order and duplicate queries
are preserved.

Failure is data, not an exception: a failed query yields a `search_error`
record, and a successful query with no results yields a `search_status` record.
One bad query never aborts the batch.

```json
{ "data_type": "search_error", "target": "…",
  "value": { "status": "failed", "error_type": "ValueError",
             "error": "…", "query_index": 3 } }
```

> **Two `BulkSearch` classes exist.** `crotdalam.search.bulk.BulkSearch` is the
> one documented here. `crotdalam.ui.bulk.BulkSearch` is a separate, weaker
> implementation used by the `crawl` CLI command: it accepts `keyword`,
> `username` or `target` headers, deduplicates queries, and **returns only the
> keyword list, discarding the search results**. Consolidating them is tracked
> in [`ROADMAP.md`](ROADMAP.md) and recorded in [`QA-REPORT.md`](QA-REPORT.md).

Both require an `Engine`, which this release does not ship — see
[`SCOPE.md`](SCOPE.md).

## Choosing an engine

| Need | Use |
|---|---|
| Exact phrase, fastest | `KeywordSearch` |
| Typos or deliberate obfuscation | `FuzzySearch` |
| Structured patterns — URLs, handles, IDs | `RegexSearch` |
| Many queries against a transport | `BulkSearch` |

## Searching a stored database

```python
from crotdalam.search import RegexSearch
from crotdalam.utils.database import Database

db = Database("evidence.sqlite")
try:
    hits = RegexSearch(list(db.records())).search(r"(?i)(t\.me|wa\.me)/", limit=100)
finally:
    db.close()

for hit in hits:
    print(hit["data_type"], hit["target"])
```

`list(db.records())` loads the corpus into memory; the 10,000-record ceiling
applies. For larger evidence sets, filter as you stream from `db.records()`
instead of building a corpus.
