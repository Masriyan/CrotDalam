# Legal and Ethical Use

CrotDalam processes data about real people. This document is not legal advice.
Get advice appropriate to your jurisdiction and your case.

## Authorization comes first

Use CrotDalam only on data you are authorized to process. Authorization is
specific — it has a source, a scope and an expiry:

| Source | Typical scope |
|---|---|
| Employment or engagement with a lawful investigative mandate | Defined by the mandate |
| A written client agreement naming the targets and purpose | Defined by the agreement |
| Legal process — warrant, court order, regulatory authority | Defined by the instrument |
| Your own accounts and your own data | Yours |
| Documented research protocol with ethics-board approval | Defined by the protocol |

"It is publicly visible" is **not** authorization. Public availability affects
one element of one legal test in some jurisdictions. It does not by itself make
collection, storage, analysis or disclosure lawful.

If you cannot name your authorization, its scope and its expiry, stop.

## Applicable law

Depending on where you, your subjects and your data are located, this activity
may engage:

- **Data protection law** — the GDPR in the EU/UK, Indonesia's PDP Law
  (UU 27/2022), and equivalents. Collecting personal data needs a lawful basis,
  a defined purpose, data minimization and a retention limit. Investigative
  purposes do not exempt you from these; they change which basis applies.
- **Computer misuse law** — unauthorized access provisions in the CFAA,
  the UK Computer Misuse Act, Indonesia's ITE Law and similar. Relevant chiefly
  to *how* data was obtained.
- **Platform terms of service** — contractual, and separate from the above.
- **Evidence law** — if the output may be used in proceedings, admissibility
  depends on provenance, integrity and chain of custody. See below.

## Special categories

Some data attracts stricter rules almost everywhere: information revealing
health, sexual orientation, religion, political opinions, trade-union
membership, ethnicity, biometrics, and anything concerning children. TikTok
content routinely contains all of these.

If your collection sweeps in special-category data — and a hashtag or keyword
sweep will — you likely need an additional lawful basis, and you should minimize
and delete aggressively.

## Third parties

An investigation into one account collects data about many uninvolved people:
commenters, followers, people appearing in videos. They did not become subjects
by your choosing them, and they have the same rights as your actual target.

Minimize what you collect about them. Redact them from reports. Delete them when
the case closes.

## Chain of custody

CrotDalam supports evidence handling but does not establish provenance on its
own.

**What it gives you.** Each record carries a sanitized `source_url`, the SHA-256
of the source capture file (`source_sha256`), the zero-based `entry_index`
within it, and `collected_at` — when the data was observed, kept separate from
the import time. Values are hashed with SHA-256 in canonical form, and the whole
record log is sealed with a tamper-evident hash chain (HMAC-keyed when
encrypted). `crotdalam validate` re-verifies every checksum **and** the chain,
so deletion, truncation, reordering and edits are detected. The `availability`
field records how the data was obtained.

**What it does not give you.** In an unencrypted database, an editor with write
access can rebuild the entire chain; keyed (encrypted) mode raises that to
requiring the key, but neither is a substitute for external anchoring. CrotDalam
does not sign reports, and a checksum sitting beside its data is not proof of
authenticity on its own. Treat the chain as strong tamper-evidence within the
tool, not as court-grade custody by itself.

**If the output may be used in proceedings:**

1. Hash the original capture with an external tool before importing, and record
   that digest independently of CrotDalam.
2. Preserve the original capture read-only. The database is a derived work.
3. Record who captured what, when, under what authority, in what timezone.
4. Set `--case-id` and `--analyst` on every report.
5. Document your methodology, including the limitations these docs state.
6. Note that analyzer scores are heuristics with published weights and are
   explicitly not probabilities — see [`ANALYZERS.md`](ANALYZERS.md).

## Analytical honesty

Every analyzer returns an `uncertainty` list and sets `is_probability: false`.
Those fields exist to be read and reproduced, not stripped.

- A scam score of 60 means matched indicators summed to 60 under published
  weights. It does not mean 60% likely to be a scam.
- Bot indicators match scheduling tools and high-volume legitimate creators.
- Phishing signals match corporate SSO links and valid international domains.
- Centrality describes the graph you imported, not real-world influence.
- UTC activity patterns cannot establish location.

Presenting a heuristic score as a determination is misrepresentation, whatever
the tool's documentation says. Never let a score alone justify accusing,
reporting or naming a person.

## Data handling

**Treat the raw HAR as a credential.** It contains your session cookies and
authentication headers. CrotDalam ignores those fields, but the file on disk
still holds them. Store it encrypted; delete it when the import is verified.

**Token removal is not anonymization.** Captions, biographies, usernames, user
IDs and comment text remain personal data after import. The redaction in
`--inspect` output protects summaries, not the record set — the record set is
evidence and is meant to retain content.

**Practical measures:**

- Databases are created `0600`; keep them on encrypted storage. Reports do not
  inherit those permissions.
- Enable AES-256-GCM for values at rest ([`STORAGE.md`](STORAGE.md)). Targets
  and source URLs stay plaintext even then.
- Keep keys in a secret manager, never beside the database. There is no recovery.
- Set a retention period at the start of the case and hold to it.
- Never commit evidence to version control. `.gitignore` covers `*.har`,
  `*.sqlite` and `data/`, but does not untrack a file already committed.
- Never attach real data to a bug report.

## Disclosure

Before publishing or sharing findings: review and redact, remove uninvolved
third parties, state your methodology and its limits, and distinguish what you
observed from what you inferred.

Consider whether publication is proportionate. Naming a suspected individual on
heuristic evidence can cause serious harm to a person who turns out to be
uninvolved — and the analyzers in this project are explicitly not calibrated to
support that.

## Reporting harm

Suspected fraud generally belongs with the platform's reporting mechanism and
the relevant authority, not with public accusation. Preserve your evidence,
report through proper channels, and let a process with due-process protections
reach the conclusion.

## Summary

Have authorization you can name. Collect the minimum. Protect what you hold.
Report uncertainty honestly. Delete when done.
