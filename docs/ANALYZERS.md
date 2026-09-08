# Analyzers

Nine offline engines under `crotdalam.analyzers`, plus a `graph_from_corpus`
helper. Every one is pure computation over records — no HTTP, no DNS, no
reputation service, no model download.

Six operate per record (`ScamDetector`, `PhishingDetector`, `BotDetector`,
`EngagementAnalyzer`, `SentimentAnalyzer`, `TemporalAnalyzer`). Three are
cross-corpus OSINT engines added in 0.3.0 (`SelectorExtractor`,
`CoordinationAnalyzer`, and `NetworkAnalyzer` fed by `graph_from_corpus`).

```python
from crotdalam.analyzers import ScamDetector
result = ScamDetector().analyze(record)
```

## The shared contract

Analyzers accept a raw value dict, a contract record with a `value` dict, or a
list of either (maximum 10,000). Scoring analyzers return:

```json
{
  "score": 45,
  "risk_level": "medium",
  "evidence": [ { "signal": "urgency", "weight": 10, "matches": ["act now"] } ],
  "uncertainty": [ "Indicators are not proof of fraud; …" ],
  "method": "offline_heuristic",
  "is_probability": false
}
```

| Field | Meaning |
|---|---|
| `score` | Sum of matched weights, capped at 100 |
| `risk_level` | `high` ≥ 60, `medium` ≥ 30, `low` below |
| `evidence` | Exactly what matched and what it contributed |
| `uncertainty` | How this result can be wrong |
| `is_probability` | Always `false` — the score is an ordinal, not a likelihood |

**`is_probability: false` is the point.** A score of 60 is not "60% likely to be
a scam". It means matched indicators summed to 60 under published weights. The
weights are editorial judgement, not calibration against a labelled corpus.

Text is read from explicit content fields only — `text`, `desc`, `description`,
`signature`, `bio`, `title`, `nickname`. Dictionary keys and arbitrary metadata
are never treated as content.

---

## ScamDetector

Bilingual (English/Indonesian) phrase matching with word-boundary anchoring,
tuned in 0.3.0 for fraud common on TikTok Indonesia. Each category contributes
**once**, regardless of how often it repeats — twenty occurrences of "act now"
score the same as one.

| Signal | Weight | Example phrases |
|---|---|---|
| `credential_request` | 35 | send your otp · kirim otp · kode verifikasi · pin atm · data rekening |
| `guaranteed_returns` | 30 | guaranteed profit · profit pasti · cuan pasti · bunga harian |
| `advance_fee` | 25 | pay upfront · biaya admin · biaya pencairan · gestun · flip saldo |
| `investment_lure` | 20 | robot trading · titip dana · kelola dana · sinyal trading · grup vip |
| `impersonation` | 20 | admin resmi · cs resmi · akun resmi · official account |
| `loan_lure` | 15 | pinjol · pinjaman cepat · cair tanpa bi checking · tanpa slip gaji |
| `gambling` | 15 | slot gacor · judol · maxwin · scatter hitam · rtp tinggi |
| `prize_bait` | 15 | you have won · anda menang · saldo gratis · pemenang undian |
| `urgency` | 10 | act now · buruan · slot terbatas · promo berakhir |
| `off_platform` | 5 | chat wa · klik link di bio · gabung telegram · link di komentar |
| `credential_bait_combination` | +15 | `credential_request` together with `prize_bait` or `advance_fee` |

The interaction term exists because credential harvesting paired with a prize or
fee pretext is a materially stronger signal than either alone. Because each
category caps at its weight and the total caps at 100, a post hitting several
Indonesian fraud categories (robot trading + admin resmi + off-platform)
reaches `high` quickly — as the sample "Robot trading profit harian pasti,
titip dana ke admin resmi, chat wa!" does, scoring 75.

**Known false positives:** quoted scam text, journalism, scam-warning posts,
security education and satire all match. The detector cannot tell use from
mention. An empty text field adds an explicit uncertainty line — a low score on
absent text does not mean safe.

Edit the lexicon in `crotdalam/config/keywords.py`. It is deliberately small and
auditable rather than large and opaque.

---

## PhishingDetector

Lexical URL triage. **No URL is fetched.** DNS, redirects, TLS certificates,
domain age, WHOIS and page content are all unknown to this analyzer.

Accepts a string, or a record with `url`, `urls`, `source_url` or text fields.
At most 100 URLs, each at most 4,096 characters.

| Signal | Weight | Trigger |
|---|---|---|
| `userinfo_obscures_host` | 25 | `https://trusted.example@evil.test/` |
| `ambiguous_url_syntax` | 20 | `%` in the authority, or a backslash |
| `literal_ip_host` | 15 | Host is a bare IP address |
| `sensitive_action_words` | 15 | login, verify, password, wallet, otp, seed, verifikasi |
| `unencrypted_http` | 10 | Scheme is `http` |
| `many_host_labels` | 10 | Five or more dot-separated labels |
| `internationalized_hostname` | 10 | Any `xn--` label |
| `unusual_port` | 5 | Port is not 80, 443 or absent |
| `long_url` | 5 | Over 200 characters |

The aggregate score is the **maximum** of the individual URL scores, not a sum —
five unrelated links should not add up to a high-risk verdict.

Malformed and non-HTTP(S) URLs are reported with `"valid": false` and a `null`
score rather than being dropped silently.

**Interpretation limits.** Every signal here also occurs on legitimate URLs.
Corporate SSO links contain "login". Valid international domains are punycode.
HTTPS establishes transport encryption, not trustworthiness. Treat the output as
a triage queue, never a block list.

---

## BotDetector

Automation *indicators*, explicitly not a bot classification. Accepts a profile
dict with a `posts` list, or a list of activity records.

| Signal | Weight | Requires |
|---|---|---|
| `high_text_repetition` | 30 | ≥ 10 non-empty texts, ≥ 70% duplicated |
| `regular_posting_intervals` | 25 | ≥ 10 timestamps, ≥ 1 h span, interval CV < 0.1 |
| `high_observed_post_rate` | 20 | Over 100 posts/day across the observed span |
| `following_imbalance` | 10 | Following ≥ 1,000 and ≥ 50× followers |

The coefficient of variation (standard deviation ÷ mean of gaps) measures how
metronomic the posting is. Humans are irregular; schedulers are not.

Below the sample thresholds the result is `"status": "insufficient_data"` rather
than a low score, because those are different claims.

**Interpretation limits.** Scheduling tools, cross-posting platforms, brand
accounts and high-volume creators all produce these patterns legitimately. The
analyzer also assumes the supplied activity belongs to one account — it cannot
verify that, and it cannot detect a network from a single account's data.

---

## EngagementAnalyzer

Descriptive metrics with explicit denominators and missingness. Recognizes both
TikTok field names (`diggCount`, `playCount`, …) and generic ones (`likes`,
`views`, …).

Returns per-record counts, an `interactions` total, `missing_interactions`,
`rate_by_views_percent`, `rate_by_followers_percent`, and a corpus-level
`weighted_rate_by_views_percent`.

**All three of likes, comments and shares must be present** for a rate to be
computed; otherwise `interactions` is `null`. A missing counter is not zero.

Rates may legitimately exceed 100% — views and followers are different
populations, and a video can be shared more often than its author has followers.
The analyzer reports the arithmetic; it does not flag anomalies.

---

## SentimentAnalyzer

A small bilingual lexicon baseline. Sentences split on `.!?;` and newlines;
negation flips polarity within a three-token window and resets at sentence
boundaries, so "not good" scores −1 while "not. good" scores +1.

Returns a signed mean of matched-token polarities in −1..1, and a label:
`positive` above 0.1, `negative` below −0.1, otherwise `mixed_or_neutral`. Text
with no lexicon match returns `null` and `unknown` — not neutral.

**Interpretation limits.** The vocabulary is deliberately small. Sarcasm, slang,
code-switching, emoji and long-distance negation are not resolved. The score is
not a calibrated probability. Use it to sort, not to conclude.

The lexicon holds single tokens only, because the tokenizer cannot match
phrases. (`terima kasih` was removed in 0.2.0 for exactly this reason — it split
into `terima` and `kasih`, which alone mean "accept" and "give".)

---

## NetworkAnalyzer

Directed graph analysis over imported edges via NetworkX. Accepts
`{"edges": [{"source", "target"}], "nodes": [...]}` or a list of edge records.

Returns node and edge counts, `duplicate_edges`, `excluded_self_loops`,
`density`, per-node `degree` / `betweenness` / `in_degree` / `out_degree`, and
`communities` from greedy modularity on the undirected projection.

Bounds: 2,000 nodes, 10,000 edge records, node IDs are non-empty strings up to
256 characters. Above 200 nodes, betweenness is sampled from 64 pivots with a
fixed seed and `betweenness_approximate` is set — the numbers stay comparable
across runs but are estimates.

**Interpretation limits.** Centrality describes *the graph you imported*, not
influence and not coordination. A node is central because of the edges you
happened to collect. Communities come from an undirected projection and can
change substantially when edges are missing — which, in a partial capture, they
always are.

---

## TemporalAnalyzer

UTC activity distributions from observed timestamps: hour, weekday and daily
counts, first and last seen, median interval, duplicate count and peak UTC hour.

Accepts Unix seconds or timezone-aware ISO 8601. **Naive timestamps are
rejected**, counted in `excluded_count`, never assumed to be local time.

**Interpretation limits.** Observation times may be collection times rather than
event times. A UTC distribution cannot establish a poster's location — that
inference requires a timezone this data does not contain — and cannot by itself
establish automation.

---

## SelectorExtractor

The OSINT pivot engine. Pulls the identifiers an investigator follows out of
record text: URLs, `@mentions`, `#hashtags`, emails, phone numbers, BTC and ETH
addresses, and messaging handles (`t.me`, `wa.me`, `chat.whatsapp.com`,
`signal.group`, `discord.gg`, `line.me`) — including the scheme-less forms
(`wa.me/628…`) that dominate scam posts.

```python
from crotdalam.analyzers import SelectorExtractor
result = SelectorExtractor().analyze(records)
```

Returns, per selector type: the values with occurrence counts (`selectors`), a
total (`counts`), a distinct count (`distinct`), and `by_target` — which account
each selector appeared under. `by_target` is the pivot: a wallet or handle that
recurs across many targets is exactly what to chase next. On the sample capture
it surfaced 142 distinct hashtags, 33 mentions and a phone number.

Bounds: reads only explicit text fields (see the shared contract); 100,000
characters per record. Phone matches are shape-filtered to 8–15 digits.

**Interpretation limits.** This is lexical extraction. Nothing is resolved,
validated against a live service, or contacted. A short link's destination is
unknown, a handle may be spoofed or reused, and the phone and crypto patterns
match by shape and yield false positives. Feed extracted URLs to
`PhishingDetector` for triage — but that too fetches nothing.

## CoordinationAnalyzer

Cross-account coordination indicators — the signal `BotDetector` cannot give,
because it looks within one account. This looks across the corpus for the same
normalized caption or the same contact selector shared by distinct identities.

```python
from crotdalam.analyzers import CoordinationAnalyzer
result = CoordinationAnalyzer(min_accounts=2).analyze(records)
```

| Output | Meaning |
|---|---|
| `shared_captions` | Normalized captions posted by ≥ `min_accounts` accounts (weight 30) |
| `shared_selectors` | Links/handles/wallets shared by ≥ `min_accounts` accounts (weight 25) |
| `coordinated_account_sets` | Connected components of accounts linked by the above |

Captions are folded on case and whitespace so trivial edits do not hide reuse;
hashtags are excluded from selectors because they are too common to imply
coordination. `min_accounts` must be ≥ 2 — one account repeating itself is not
coordination.

**Interpretation limits.** `is_probability` is `false`. Shared content also
arises from duets, reposts, quoting, templates and news events. Distinct
usernames prove neither distinct people nor a single operator — identity is
unverified. A partial corpus over-represents whatever it captured. This is a
lead generator, not a determination.

## graph_from_corpus + NetworkAnalyzer

`NetworkAnalyzer` ranks a graph but ships with no way to build one from records.
`graph_from_corpus` bridges that gap: it derives an authorship/interaction graph
from the corpus and emits the `{"nodes", "edges"}` shape `NetworkAnalyzer` eats.

```python
from crotdalam.analyzers import graph_from_corpus, NetworkAnalyzer
graph = graph_from_corpus(records)
analysis = NetworkAnalyzer().analyze(graph)
```

Edges, by record type:

| From → to | Relation | Source |
|---|---|---|
| author → video | `posted` | video records |
| commenter → video | `commented_on` | comment records |
| commenter → replied-to user | `replied_to` | comment reply linkage |

Node IDs are namespaced (`user:`, `video:`) so an id reused across kinds does
not collapse two entities into one node. Bounds match `NetworkAnalyzer`: 2,000
nodes, 10,000 edges. It invents no relationship not explicit in a record; a
sparse capture yields a sparse graph, and centrality describes that graph, not
real influence.

## Composing analyzers

Nothing chains them for you; that is deliberate, so weighting across engines is
your explicit choice rather than a hidden default.

```python
from crotdalam.analyzers import ScamDetector, PhishingDetector
from crotdalam.utils.database import Database

db = Database("evidence.sqlite")
try:
    for record in db.records():
        scam = ScamDetector().analyze(record)
        phish = PhishingDetector().analyze(record)
        if scam["score"] >= 30 or phish["score"] >= 30:
            print(record["target"], scam["risk_level"], phish["risk_level"])
            print("  ", [e["signal"] for e in scam["evidence"] + phish["evidence"]])
finally:
    db.close()
```

To surface analyzer output in a report, write the label into the record's
`value` as `risk` or `severity` — `HTMLReport` counts those into its risk chart
and never infers a score of its own. See [`REPORTS.md`](REPORTS.md).
