# Scope

This document explains what CrotDalam does, what it deliberately does not do,
and why. The CLI links here when a command cannot run.

## In scope

| Capability | Status |
|---|---|
| Import an authorized HAR capture, fully offline | Implemented |
| Record source-file hash and collection time on every record | Implemented |
| Normalize records into a verifiable contract | Implemented |
| Store evidence with checksums, a tamper-evident chain and optional AES-256-GCM | Implemented |
| Search a local corpus (keyword, fuzzy, regex, bulk) | Implemented |
| Analyze records with explainable offline heuristics | Implemented |
| Extract pivotable selectors from a corpus | Implemented |
| Correlate accounts sharing content or contact selectors | Implemented |
| Build an authorship/interaction graph from a corpus | Implemented |
| Detect change between snapshots and raise alerts | Implemented |
| Generate HTML, PDF, CSV and JSON forensic reports | Implemented |
| Parse public page hydration JSON into records | Implemented, needs a transport |
| Fetch public pages over HTTP | **Not shipped** |
| CAPTCHA solving, signature forging, evasion proxying, fingerprint spoofing | **Refused — permanent non-goal** |

## Explicitly out of scope

These are permanent non-goals. They will not be accepted as contributions.

| Excluded | Why |
|---|---|
| CAPTCHA solving, or integration with solver services | The purpose is to defeat a control that exists to stop automated collection |
| Request-signature generation (`X-Bogus`, `msToken`, `_signature`, `GnuSlog`) | Forging these exists only to reach endpoints the platform does not expose to you |
| Browser-fingerprint spoofing (WebGL, Canvas, AudioContext, JA3/TLS rotation) | Its function is to make automated traffic indistinguishable from a person's |
| Proxy rotation for evasion, residential proxy pools, device farms | Distributing traffic to avoid rate limits and attribution |
| Decoy or noise traffic | Obscuring an access pattern from the operator |
| Mouse and scroll humanization to defeat behavioural detection | Same purpose as fingerprint spoofing |
| Private/undocumented API clients | Reaching them requires the items above |

Each of these is a technique whose function is to defeat access controls rather
than to analyze evidence. A tool built on them produces evidence of uncertain
provenance, and its operator carries risk that the tool's documentation cannot
discharge.

## The consequence

CrotDalam has no live collection path. Data enters the system through:

1. **`import-har`** — a browser capture you produced under your own
   authorization. This is the primary and best-supported path.
2. **The library API** — records you construct or import programmatically
   through `crotdalam.collectors.base.import_records`.
3. **Hydration collectors** — `ProfileCollector` and `VideoCollector` parse the
   JSON embedded in a public page. They are implemented and tested, but require
   an object satisfying the `Engine` protocol
   (`crotdalam/collectors/base.py`) to supply the HTML. This release does not
   ship one.

## The `Engine` protocol

If you supply your own transport, everything downstream works. The contract is
three async methods:

```python
class Engine(Protocol):
    async def fetch(self, url: str) -> str: ...
    async def collect(self, kind: str, target: str) -> dict: ...
    async def search(self, keyword: str, limit: int = 20) -> list[dict]: ...
```

Supplying a transport is your decision and your responsibility. If you do,
respect `robots.txt`, the platform's terms, applicable law and a rate limit that
does not burden the service. CrotDalam will not help you hide that traffic.

## Commands affected

`search`, `analyze --username`, `crawl`, `monitor` and `gui` require the engine
and exit with status 1 and this message:

```
crotdalam: The network-facing collection engine (crotdalam.core.engine) is not
part of this release, so 'search' cannot run. Offline workflows are available:
'import-har' to ingest an authorized capture, then 'validate', 'analyze --input'
and 'report'. See docs/SCOPE.md and docs/ROADMAP.md.
```

Everything else runs offline. See [`USAGE.md`](USAGE.md).
