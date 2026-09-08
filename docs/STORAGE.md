# Storage

`crotdalam.utils.database.Database` is a small SQLite layer for evidence records
and monitor state.

```python
from crotdalam.utils.database import Database

db = Database("evidence.sqlite")            # or Database(path, key) to encrypt
try:
    stored = db.store(record)               # returns the record with sha256 + timestamp
    for record in db.records():             # streaming, checksum-verified
        ...
finally:
    db.close()
```

## Schema

| Table | Columns | Holds |
|---|---|---|
| `records` | `id`, `metadata`, `value` | Evidence; metadata plaintext, value optionally encrypted |
| `state` | `key`, `value` | Monitor state, optionally encrypted |
| `metadata` | `key`, `value` | Encryption mode and key check |

Metadata is the record minus `value`: `data_type`, `target`, `source_url`,
`collected_at`, `timestamp`, `sha256` and `provenance`. It stays queryable in
plaintext even when values are encrypted. The `metadata` table also holds the
`chain_head` seal (below) and, when encrypted, the mode and key check.

## File handling

The database is created carefully:

- Opened with `O_NOFOLLOW`, so a symlink at the path cannot redirect the write.
- `fchmod` to `0600` — owner read/write only — on every open, not just creation.
- Missing parent directories are created `0700`. **Existing** parents keep their
  permissions; the layer does not tighten a directory you already had.
- WAL journal mode with a 5-second busy timeout, so readers do not block writers.
- `check_same_thread=False` with an `RLock`, so the GUI can read from a worker
  thread.

Reports written next to the database do **not** inherit these permissions.

## Integrity

`store()` computes `sha256` over the canonical JSON of `value` (sorted keys,
compact separators, `allow_nan=False`) and stores it in metadata.

`records()` recomputes the checksum on every read and raises
`record checksum mismatch` on a mismatch. `crotdalam validate` is a full pass
over the database doing exactly this.

**What a checksum proves.** It detects accidental corruption of one record's
value — bad disk, partial write, buggy edit. On its own it is not tamper
evidence: it is stored beside the data, and it does not cover deletion of a
whole record. That gap is what the chain below closes.

`records()` pages in batches of 256 against a high-water mark taken at the start,
so a long read does not hold a lock and rows added during iteration are not
included.

## Tamper-evident evidence chain

Per-record checksums cannot detect a record being **deleted** — the row simply
vanishes and everything else still verifies. Before 0.3.0, deleting rows from an
evidence database passed `validate` silently. The chain fixes that.

Each `store()` advances a running seal held in `metadata.chain_head`:

```
head₀ = SHA-256("crotdalam-chain-v1|" + mode)          # genesis
headᵢ = step(headᵢ₋₁, canonical_metadataᵢ)
```

`step` is **HMAC-SHA256 keyed by the encryption key** when the database is
encrypted, and a bare SHA-256 chain otherwise. Because each step folds in the
previous head and the record's canonical metadata (which includes the value's
`sha256`), the final head commits to every record, in order.

```python
db.verify_chain()
# {"records": 156, "chain_head": "997f…", "verified": True, "keyed": False}
```

`verify_chain()` recomputes the seal from genesis over all records in id order,
re-verifies each value checksum along the way, and compares to the stored head.
It raises `evidence chain broken: records were deleted, reordered or altered` on
any mismatch. `crotdalam validate` runs it for SQLite inputs.

**What the chain proves, and its limit.** It detects deletion, truncation,
reordering and metadata edits. In **plain** mode an editor with write access can
recompute the whole chain, so it defends against accidental and naive tampering,
not a motivated editor. In **keyed** mode rebuilding requires the encryption
key, which raises the bar substantially. For a court-grade anchor, still hash
the original capture externally and record that digest independently — see
[`LEGAL-AND-ETHICS.md`](LEGAL-AND-ETHICS.md). The record itself also carries the
source capture's `source_sha256` ([`DATA-MODEL.md`](DATA-MODEL.md)).

## Encryption at rest

Optional AES-256-GCM over record values and monitor state.

```python
from crotdalam.utils.crypto import generate_key
key = generate_key()                        # base64 of 32 random bytes
db = Database("evidence.sqlite", key)
```

Or via configuration, so the key never enters source or arguments:

```sh
export CROTDALAM_KEY="$(python -c 'from crotdalam.utils.crypto import generate_key; print(generate_key())')"
export CROTDALAM_ENCRYPTION_KEY_ENV=CROTDALAM_KEY
```

Each value gets a fresh 12-byte nonce, and the record's **metadata is bound as
additional authenticated data**. Moving a ciphertext to a different record fails
authentication rather than decrypting into the wrong context.

A database records its mode at creation and stores an encrypted key check.
Opening a plaintext database with a key, or an encrypted one without, fails with
`database encryption mode does not match supplied key`. A wrong key fails the
key check immediately rather than producing garbage later.

### What encryption does and does not cover

| Encrypted | Plaintext |
|---|---|
| Record `value` payloads | `data_type`, `target`, `source_url` |
| Monitor `state` payloads | `timestamp`, `sha256` |
| | Table structure, row counts, state keys |

Targets and source URLs stay readable. Someone with the file learns *who* was
collected and *from where*, without the key. Checksums are of plaintext, so they
also confirm a guess about a low-entropy value.

**There is no key recovery.** Lose the key and the values are gone. Store it in a
secret manager, never beside the database.

## Concurrency

Operations are individually transactional. Reads and writes across threads in
one process are serialized by an `RLock`, and WAL allows concurrent readers.

A monitor `check()` is a read-modify-write and is **not** a multi-process
compare-and-swap. Two processes monitoring the same subject against the same
database can lose an update. Partition subjects across processes, or use one
writer.

## Practical notes

Importing the same capture twice **appends**; there is no cross-run upsert.
Deduplication happens within a single import ([`HAR-IMPORT.md`](HAR-IMPORT.md)).

`Database(":memory:")` gives an ephemeral database for tests, skipping all file
handling.

Always `close()` in a `finally` block, or WAL files may linger.

`.gitignore` covers `*.db`, `*.sqlite`, `*.sqlite3` and their WAL/SHM
companions. Ignore rules do not untrack an already-committed file.
