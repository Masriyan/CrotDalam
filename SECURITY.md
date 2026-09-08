# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | Yes |
| < 0.2 | No |

## Reporting a vulnerability

Report privately through
[GitHub Security Advisories](https://github.com/Masriyan/CrotDalam/security/advisories/new).
Do not open a public issue for an unfixed vulnerability.

Please include the affected module and version, reproduction steps, a minimal
proof of concept, and the impact you observed. Expect an acknowledgement within
7 days and a status update within 30 days.

**Never attach a real HAR capture or evidence database to a report.** They
contain personal data. Build a minimal synthetic reproducer instead — the test
suite in `tests/` shows how to construct one.

## What counts as a vulnerability here

CrotDalam processes **untrusted input by design**: HAR captures, hydration HTML
and record values all originate from a third party. Anything that lets that
input escape its boundary is in scope:

- Report injection — record content escaping HTML/CSV/PDF escaping, for example
  script execution in a generated HTML report or formula execution in CSV.
- Path traversal through a record field, output path or filename.
- Resource exhaustion that defeats the documented bounds in
  [`docs/HAR-IMPORT.md`](docs/HAR-IMPORT.md) (memory, CPU, recursion).
- Secret disclosure — a credential, token, cookie or proxy password reaching a
  log, report or summary despite `crotdalam.utils.logger` redaction.
- Cryptographic flaws in `crotdalam.utils.crypto` or its use in
  `crotdalam.utils.database`.
- Privacy leaks in `--inspect` output, which is documented as safe to share.

## What is not a vulnerability

- CrotDalam does not bypass TikTok anti-bot controls. "It cannot collect live
  data" is the documented design, not a bug — see [`docs/SCOPE.md`](docs/SCOPE.md).
- The absence of `crotdalam.core.engine` is a known, documented gap.
- Analyzer scores are heuristics with published weights. A false positive or
  false negative is an accuracy issue; open a normal issue.
- Evidence databases contain personal data by design. That is a handling
  responsibility, described in [`docs/LEGAL-AND-ETHICS.md`](docs/LEGAL-AND-ETHICS.md).

## Security properties this project tries to hold

| Property | Mechanism | Tested in |
|---|---|---|
| Reports never execute record content | HTML escaping on every field, CSP `default-src 'none'`, no scripts | `tests/test_reports.py` |
| CSV resists formula injection | Leading `=`, `+`, `-`, `@` and whitespace prefixed with `'` | `tests/test_reports.py` |
| Logs never carry secrets | `RedactingFormatter` over messages and formatted tracebacks | `tests/test_storage.py` |
| HAR import cannot exhaust memory | Byte, entry, node and depth ceilings, fail-closed | `tests/test_har.py` |
| `--inspect` output is shareable | Host, path-segment and JSON-key allowlists; values never emitted | `tests/test_har.py` |
| Databases are not world-readable | `O_NOFOLLOW` open, `fchmod` 0600, new parents 0700 | `tests/test_storage.py` |
| Values can be encrypted at rest | AES-256-GCM with record metadata bound as AAD | `tests/test_storage.py` |
| The shell cannot reach the OS | `shlex` + `argparse` only; no `eval`, `subprocess` or shell escape | `tests/test_reports.py` |

## Known limitations

- SHA-256 checksums detect accidental corruption. They are stored beside the
  data and do not prevent deliberate rewriting of a database you do not control.
- Encryption covers record values and monitor state. Metadata, checksums,
  timestamps and targets remain plaintext.
- HAR parsing loads the document into memory; peak RSS can exceed file size.
- ReportLab's default fonts do not cover every Unicode glyph in PDF output.
