# Monitors

Monitors detect change between snapshots. Each `check()` compares a new record
against persisted state, emits alerts for what changed, and stores the new
baseline.

```python
from crotdalam.monitors import ProfileMonitor
from crotdalam.utils.database import Database

db = Database("evidence.sqlite")
alerts = ProfileMonitor(db).check(record)
```

Monitors are synchronous and do not fetch anything. You supply each snapshot;
they tell you what moved. To poll on a schedule, drive them with
`crotdalam.core.Scheduler`.

## Alert shape

```json
{
  "type": "profile_bio_changed",
  "target": "someuser",
  "timestamp": "2026-09-08T00:00:00Z",
  "details": { "before": "…", "after": "…" },
  "id": "<sha256 of the four fields above>"
}
```

`id` is a content hash, so redelivering the same alert is detectable and
downstream delivery can be made idempotent.

## Shared semantics

These rules hold for every monitor and are the reason the output is trustworthy.

**First observation is a baseline, never an alert.** You cannot have changed
from nothing.

**Missing means unknown, not deleted.** A field absent from a snapshot leaves
the stored value untouched and raises nothing. A partial capture must not look
like a deletion.

**Event time, not wall-clock time.** Comparison uses the record's `timestamp`. A
snapshot older than or equal to the stored state is discarded as stale and
returns no alerts, so replaying an old capture cannot rewrite newer state.

**Identity is stable across renames.** State keys derive from `id`, `user_id` or
`sec_uid` where present, falling back to `target`. A username change is
therefore detected as a change rather than seen as a new account.

**State is one row per subject.** `check()` is transactional per write but is
not a multi-process compare-and-swap. Do not run two monitors against the same
database row concurrently.

---

## ProfileMonitor

```python
ProfileMonitor(db, follower_spike_threshold=100,
                   follower_spike_ratio=0.2, window_seconds=3600)
```

Reads `username`, `bio`, `follower_count` and an identity field from `value`.

| Alert | Raised when |
|---|---|
| `profile_username_changed` | A known username differs |
| `profile_bio_changed` | A known bio differs |
| `profile_follower_spike` | Growth clears both thresholds within the window |

A spike requires **both** an absolute gain (`≥ threshold`) and a relative gain
(`≥ ratio × baseline`). Requiring both stops a 100-follower gain from alerting
on an account with two million followers, and stops a 50% gain from alerting on
an account with four.

The baseline is the oldest sample still inside the event-time window. Samples
outside it are dropped, and the sample list resets after a spike fires so one
growth event alerts once.

## KeywordMonitor

```python
KeywordMonitor(db, ["giveaway", "kirim otp"])
```

Case-insensitive substring matching over **string values only**, recursively
through nested dictionaries and lists. Dictionary keys and metadata are never
searched — a keyword matching a field name is not a match.

Emits `keyword_match` with the matched keyword in `details`.

Deduplication is persistent and keyed on
`(data_type, target, value, keyword)` — the whole value, not just the target. The
same keyword in the same unchanged content alerts once, ever. If the content
changes and still matches, that is a new alert, because it is new evidence.

Keywords are normalized to casefolded, stripped strings on construction. Passing
a bare string raises, since iterating one would monitor its characters.

## HashtagMonitor

Reads `video_count`, `view_count`, `video_ids` and `complete` from `value`.

| Alert | Raised when |
|---|---|
| `hashtag_video_count_changed` | Count differs; `details` carries `delta` |
| `hashtag_view_count_changed` | Count differs; `details` carries `delta` |
| `hashtag_videos_changed` | IDs added, or removed from a complete snapshot |

The `complete` flag is what makes removals meaningful:

- `complete: true` — the snapshot is the full set, so missing IDs are genuine
  removals, reported as `removed_from_snapshot`, and state is replaced.
- Otherwise — the snapshot is partial, so IDs are **merged** into the known set
  and no removal is ever reported.

This is the central discipline of the module: absence of data is not evidence of
deletion.

## LivestreamMonitor

Reads `is_live`, `room_id`, `title` and `viewer_count`.

| Alert | Raised when |
|---|---|
| `livestream_started` | `is_live` goes false → true |
| `livestream_ended` | `is_live` goes true → false |
| `livestream_room_changed` | The room ID changes while live |
| `livestream_title_changed` | The title changes while live |
| `livestream_viewer_count_changed` | The viewer count changes while live |

A non-boolean or missing `is_live` does **not** end a stream — a failed check is
not an ending. Room, title and viewer state are tracked only while live, and
reset on a state or room change so a new stream does not inherit the old one's
title.

---

## Polling

`Scheduler` runs fixed-delay async jobs, each strictly serial, bounded by a
semaphore.

```python
import asyncio
from crotdalam.core.scheduler import Scheduler
from crotdalam.monitors import ProfileMonitor
from crotdalam.utils.database import Database

db = Database("evidence.sqlite")
monitor = ProfileMonitor(db)
scheduler = Scheduler(max_concurrency=4)

async def check_target():
    snapshot = build_snapshot()          # your code supplies the record
    for alert in monitor.check(snapshot):
        print(alert["type"], alert["target"])

scheduler.add_job("target-1", check_target, interval=300)
asyncio.run(scheduler.run())             # stop() ends it cleanly
```

A job that raises is logged through the redacting logger and the loop continues
— one failing target does not stop the others. Jobs cannot be added while
running. There is no cron expression support; intervals are fixed delays
measured from the end of the previous run.

## What this is not

There is no alert delivery. Webhooks, Telegram and Discord notification are not
implemented — `check()` returns alerts and you decide what to do with them.

There is also no collection: something must supply each snapshot. In this
release that means [`import-har`](HAR-IMPORT.md) or your own transport, since
the `monitor` CLI command needs the engine described in [`SCOPE.md`](SCOPE.md).
