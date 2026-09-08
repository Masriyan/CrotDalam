# Roadmap

## Permanent non-goals

These will not be built, and pull requests adding them will be closed. The
reasoning is in [`SCOPE.md`](SCOPE.md).

- CAPTCHA solving or solver-service integration
- Request-signature generation (`X-Bogus`, `msToken`, `_signature`, `GnuSlog`)
- Browser-fingerprint spoofing (WebGL, Canvas, AudioContext, JA3/TLS rotation)
- Proxy rotation for evasion, residential pools, device farms
- Decoy or noise traffic
- Behavioural humanization intended to defeat bot detection
- Private or undocumented API clients

## Open items

Carried from [`QA-REPORT.md`](QA-REPORT.md).

### Consolidate the two `BulkSearch` classes — QA-07

`crotdalam/search/bulk.py` and `crotdalam/ui/bulk.py` have incompatible
contracts, and the CLI `crawl` command uses the version that discards search
results. The `search` implementation is the better one: it returns records and
converts a failed query into a `search_error` record rather than aborting the
batch.

Proposal: make `search.bulk.BulkSearch` canonical, extend it to accept
`username` and `target` headers, add an optional deduplication flag, and reduce
`ui/bulk.py` to a re-export. Both are currently covered by tests with different
expectations, so this needs a deprecation note in `CHANGELOG.md`.

### GUI test coverage — QA-08

`ui/gui.py` is 133 statements at 0%. Covering it needs a headless X server
(`xvfb`) in CI. Worth doing if the GUI gains functionality.

## Done in 0.3.0

These shipped after the initial roadmap was written. Details in
[`QA-REPORT.md`](QA-REPORT.md) and [`CHANGELOG.md`](../CHANGELOG.md).

- **Chain of custody** — source-file hashing, `collected_at` distinct from
  import time, and a tamper-evident hash chain verified by `crotdalam validate`.
- **Selector extraction** (`SelectorExtractor`) — the pivot engine.
- **Cross-account coordination** (`CoordinationAnalyzer`).
- **Corpus → graph bridge** (`graph_from_corpus`) feeding `NetworkAnalyzer`.
- **Expanded Indonesian scam lexicon** — 6 → 10 categories.

## Planned

### Near term

- **Streaming HAR parser.** The document is currently parsed in memory, peaking
  at 4–5× file size. An incremental parser would remove the 200 MiB ceiling and
  make large captures practical on modest hardware.
- **Cross-run deduplication on import.** Importing a capture twice appends
  records. A content-addressed upsert keyed on `(data_type, target, sha256)`
  would make re-import idempotent while still preserving genuine changes as new
  records.
- **`analyze --input` runs the analyzers.** Today it prints descriptive counts
  only. It should be able to run the scoring engines over a stored corpus and
  write the labels back into record values, so `HTMLReport` can chart them
  without a separate script.
- **Alert delivery.** `check()` returns alerts and nothing consumes them.
  A pluggable sink (file, webhook, local notification) would close the loop,
  with delivery kept separate from detection.

### Medium term

- **More HAR containers.** Only `itemList`, `item_list`, `items`, `comments`,
  `userInfo` and `UserModule.users` are recognized. Adding containers is
  low-risk and additive — unrecognized schemas are never guessed.
- **HTML hydration import from HAR.** `text/html` bodies in a capture are
  currently skipped, although `collectors/hydration.py` can already parse the
  embedded JSON. Wiring the two together would extract records the importer
  currently discards.
- **Report templating.** `HTMLReport` builds markup inline. A template layer
  would let analysts customize reports without editing Python, provided
  escaping stays mandatory rather than opt-in.
- **Timeline visualization** in HTML reports, using the data
  `TemporalAnalyzer` already produces.
- **Perceptual hashing** for avatars and thumbnails, to correlate reused imagery
  across accounts within an existing corpus.

### Longer term

- **Cross-platform correlation** on data you already hold — extending
  `CoordinationAnalyzer` and `SelectorExtractor` to match usernames, bio text
  and content hashes across corpora from different platforms. Strictly offline
  correlation of imported records, not collection.
- **Perceptual hashing** for avatars and thumbnails, so `CoordinationAnalyzer`
  can cluster on reused imagery, not just text and selectors.
- **Optional ML module.** TF-IDF classification, isolation-forest anomaly
  detection and clustering, kept in an optional extra so the core stays at four
  dependencies. Any model must produce evidence and uncertainty like the
  existing analyzers, not an opaque score.
- **PostgreSQL backend** for multi-analyst cases, behind the existing `Database`
  interface.
- **Report signing.** Checksums today detect corruption, not tampering.
  Detached signatures over a report and its inputs would give real chain of
  custody.

## Not planned, but accepted

If you need live collection, implement the `Engine` protocol
(`collectors/base.py`) yourself. Everything downstream — hydration collectors,
search, analyzers, monitors, reports — already works against it. That is your
decision and your responsibility; see [`SCOPE.md`](SCOPE.md).

## Contributing

Pick anything above and open an issue before starting substantial work. See
[`../CONTRIBUTING.md`](../CONTRIBUTING.md).
