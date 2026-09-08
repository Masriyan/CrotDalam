# Configuration

Configuration lives in `crotdalam.config.settings.Settings`, a frozen dataclass.
Every value is validated on construction; an invalid value raises `ValueError`
rather than falling back to a silent default.

```python
from crotdalam.config.settings import Settings

settings = Settings.from_env()                       # CROTDALAM_* variables
settings = settings.with_overrides(database="a.db")  # None values are ignored
```

## Settings

| Field | Type | Default | Constraint |
|---|---|---|---|
| `corpus` | `str \| None` | `None` | Non-empty if set |
| `database` | `str` | `data/db/crotdalam.sqlite` | Non-empty |
| `output_dir` | `str` | `data/exports` | Non-empty |
| `concurrency` | `int` | `4` | 1–32; `bool` rejected |
| `request_timeout` | `float` | `30.0` | Finite, 0 < t ≤ 600 |
| `case_id` | `str` | `UNASSIGNED` | Non-empty |
| `analyst` | `str` | `Not specified` | Non-empty |
| `encryption_key_env` | `str \| None` | `None` | Non-empty if set |

## Environment variables

Each field maps to `CROTDALAM_` + the uppercased field name. An unset or empty
variable leaves the default in place; a malformed one raises.

```sh
export CROTDALAM_DATABASE=/secure/case-001/evidence.sqlite
export CROTDALAM_OUTPUT_DIR=/secure/case-001/exports
export CROTDALAM_CONCURRENCY=8
export CROTDALAM_CASE_ID=CD-2026-001
export CROTDALAM_ANALYST="Your Name"
export CROTDALAM_ENCRYPTION_KEY_ENV=CROTDALAM_KEY
```

| Variable | Field |
|---|---|
| `CROTDALAM_CORPUS` | `corpus` |
| `CROTDALAM_DATABASE` | `database` |
| `CROTDALAM_OUTPUT_DIR` | `output_dir` |
| `CROTDALAM_CONCURRENCY` | `concurrency` |
| `CROTDALAM_REQUEST_TIMEOUT` | `request_timeout` |
| `CROTDALAM_CASE_ID` | `case_id` |
| `CROTDALAM_ANALYST` | `analyst` |
| `CROTDALAM_ENCRYPTION_KEY_ENV` | `encryption_key_env` |

```sh
crotdalam config show     # prints the effective configuration as JSON
```

## Precedence

Command-line flags override environment variables, which override defaults:

```
defaults  →  CROTDALAM_* variables  →  --corpus / --database
```

## Encryption keys

`encryption_key_env` holds the **name** of the variable containing the key, not
the key. The key value is read on demand and never appears in `config show`,
logs or reports.

```sh
python -c "from crotdalam.utils.crypto import generate_key; print(generate_key())"
export CROTDALAM_KEY="<the generated key>"
export CROTDALAM_ENCRYPTION_KEY_ENV=CROTDALAM_KEY
```

```python
key = Settings.from_env().encryption_key()   # raises if the variable is empty
```

The key is base64 of exactly 32 random bytes (AES-256). Store it in a secret
manager, not in the repository, not in shell history, not in the database
directory. **A database encrypted with a lost key is unrecoverable** — there is
no escrow and no recovery path.

A database records its mode on creation. Opening a plaintext database with a key,
or an encrypted one without, fails with
`database encryption mode does not match supplied key`. See [`STORAGE.md`](STORAGE.md).

## Configuration that does not exist

There is no setting for proxies, user agents, request signing, CAPTCHA
services, rate-limit evasion or browser fingerprints. `request_timeout` and
`concurrency` describe how a transport *you* supply should behave; they enable
nothing on their own. See [`SCOPE.md`](SCOPE.md).

`session list` and `proxy list` read a JSON array you pass with `--file` and
echo it back. They do not create sessions, test proxies or configure routing.
