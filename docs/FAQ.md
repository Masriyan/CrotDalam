# FAQ

**Does this scrape TikTok?**
No. There is no live collection path in this release. Data enters through
[`import-har`](HAR-IMPORT.md) or the library API. See [`SCOPE.md`](SCOPE.md).

**Where is the CAPTCHA solver / signature generation / proxy rotation?**
Deliberately absent, permanently. Those techniques exist to defeat access
controls rather than to analyze evidence. [`SCOPE.md`](SCOPE.md) explains the
reasoning; [`ROADMAP.md`](ROADMAP.md) lists them as permanent non-goals.

**Then what is it for?**
Doing the analysis and reporting rigorously on evidence you already lawfully
hold: normalizing it, hashing it, sealing it in a tamper-evident chain,
extracting pivotable selectors, correlating coordinated accounts, scoring it
with explainable heuristics, detecting change, and producing forensic reports.

**How do I pivot from an imported capture?**
`crotdalam extract --input evidence.sqlite` pulls URLs, @mentions, #hashtags,
emails, phones, wallets and messaging handles, attributed to the accounts they
appear under. `crotdalam correlate` then groups accounts that share a caption or
a contact selector. Both are offline — nothing is resolved or contacted. See
[`ANALYZERS.md`](ANALYZERS.md).

**Can I detect a coordinated scam network?**
`CoordinationAnalyzer` (the `correlate` command) surfaces accounts posting the
same caption or the same link/handle/wallet. That is a lead, not a verdict:
duets, reposts and templates produce the same pattern, and distinct usernames
do not prove distinct people. Corroborate before you act.

**Why do `search` and `crawl` exist if they do not work?**
They are wired to the `Engine` protocol. Supply a transport and they work
unchanged. Without one they exit 1 with an explanation rather than a traceback.

**Can I add my own collection engine?**
Yes — implement `fetch`, `collect` and `search` from
`crotdalam/collectors/base.py`. Everything downstream already works against it.
That is your decision and your responsibility.

**How do I get a HAR?**
DevTools → Network tab → browse the pages you are authorized to examine →
Export HAR. Details in [`HAR-IMPORT.md`](HAR-IMPORT.md).

**The import found 0 records.**
Usually normal. Run `--inspect` and check `body_availability`. Mostly `opaque`
or `missing` means the capture holds media and scripts rather than API JSON.
See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

**Is `--inspect` output safe to share?**
Yes, by design. Hosts, path segments and JSON keys outside the allowlists are
redacted, and record values are never printed. The *database* is a different
matter — it holds personal data.

**Is the imported data anonymized?**
No. Removing tokens is not anonymization. Captions, biographies, usernames and
comment text remain personal data. See [`LEGAL-AND-ETHICS.md`](LEGAL-AND-ETHICS.md).

**Can I import the same capture twice?**
You can, but it appends. Deduplication is local to one import. Cross-run upsert
is on the roadmap.

**How much memory does import need?**
Roughly 4–5× the file size — the document is parsed in memory. A 144 MB capture
peaked at 640 MB RSS and finished in 0.93 s.

**Does a scam score of 60 mean 60% likely a scam?**
No. Every result sets `is_probability: false`. It means matched indicators
summed to 60 under published weights, which are editorial judgement rather than
calibration. See [`ANALYZERS.md`](ANALYZERS.md).

**Why do the analyzers refuse to give a verdict?**
Because the evidence does not support one. Quoted scam text matches a scam
detector. Schedulers match bot detectors. Corporate SSO links match phishing
heuristics. The analyzers surface signals for a human to judge.

**Can I use this as court evidence?**
CrotDalam records the source file's hash and collection time and seals the log
with a tamper-evident chain that `validate` checks — so deletion and edits are
detectable. But an unencrypted chain can be rebuilt by someone with write
access, and reports are not signed, so the tool does not establish court-grade
custody by itself. Anchor the original capture externally too. Read the
chain-of-custody section of [`LEGAL-AND-ETHICS.md`](LEGAL-AND-ETHICS.md).

**Will you add a CAPTCHA solver / signature forging / evasion proxy?**
No — requested and declined, permanently. Their only function is to defeat
TikTok's access controls, and evidence obtained by circumventing access controls
is the evidence most easily thrown out, which defeats a forensic tool. See
[`SCOPE.md`](SCOPE.md).

**Is the database encrypted?**
Only if you supply a key. Then AES-256-GCM protects record values and monitor
state; `data_type`, `target`, `source_url`, timestamps and checksums stay
plaintext. See [`STORAGE.md`](STORAGE.md).

**What happens if I lose the key?**
The values are unrecoverable. There is no escrow.

**Which Python versions?**
3.11 or newer, tested through 3.14.

**Why only four dependencies?**
Fewer dependencies mean a smaller supply-chain surface and a tool that still
installs in a few years. `reportlab` and Tkinter are optional and isolated.

**PDF export fails.**
`pip install -e ".[pdf]"`. With `--format all`, the other three formats are
still written.

**Which `BulkSearch` should I use?**
`crotdalam.search.bulk.BulkSearch`. The one in `crotdalam.ui.bulk` discards
results and is used only by the `crawl` command. Consolidation is tracked in
[`ROADMAP.md`](ROADMAP.md).

**Is the GUI usable?**
It exists but needs Tkinter, a display and the absent engine. The CLI is the
supported interface.

**How do I run it without installing?**
`pip install beautifulsoup4 networkx regex cryptography`, then
`python -m crotdalam.ui.cli`.

**What does the name mean?**
**C**ollection & **R**econnaissance **O**f **T**ikTok — **D**iscovery,
**A**nalysis, **L**ogging **A**nd **M**onitoring.
