import asyncio
from pathlib import Path
import tempfile
import unittest

from crotdalam.utils.database import Database
from crotdalam.monitors import ProfileMonitor, KeywordMonitor, HashtagMonitor, LivestreamMonitor
from crotdalam.core.scheduler import Scheduler


def record(value, second=0, target="alice", kind="profile"):
    return {"data_type": kind, "target": target, "value": value,
            "timestamp": f"2026-01-01T00:{second // 60:02d}:{second % 60:02d}Z"}


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.addCleanup(self.db.close)

    def test_profile_identity_unknown_spike_and_stale(self):
        monitor = ProfileMonitor(self.db)
        self.assertEqual(monitor.check(record({"id": "42", "username": "alice", "bio": "old", "follower_count": 100})), [])
        alerts = monitor.check(record({"id": "42", "username": "new", "bio": "", "follower_count": 210}, 1, "new"))
        self.assertEqual({a["type"] for a in alerts}, {"profile_username_changed", "profile_bio_changed", "profile_follower_spike"})
        self.assertEqual(monitor.check(record({"id": "42", "bio": None}, 2)), [])
        self.assertEqual(monitor.check(record({"id": "42", "bio": "old"}, 0)), [])
        self.assertEqual(monitor.check(record({"id": "42", "follower_count": 211}, 3)), [])

    def test_window_expiration(self):
        monitor = ProfileMonitor(self.db, window_seconds=10)
        monitor.check(record({"follower_count": 1}))
        self.assertEqual(monitor.check(record({"follower_count": 1000}, 11)), [])

    def test_keyword_persistent_dedup(self):
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / "db")
            db = Database(path)
            item = record({"text": "A NEEDLE here"})
            self.assertEqual(len(KeywordMonitor(db, ["needle"]).check([item, item])), 1)
            db.close()
            db = Database(path)
            self.addCleanup(db.close)
            self.assertEqual(KeywordMonitor(db, ["needle"]).check([item]), [])

    def test_hashtag_partial_and_complete(self):
        monitor = HashtagMonitor(self.db)
        monitor.check(record({"video_ids": ["a", "b"], "view_count": 10}))
        alerts = monitor.check(record({"video_ids": ["c"], "view_count": 20}, 1))
        self.assertEqual(alerts[-1]["details"], {"added": ["c"], "removed_from_snapshot": []})
        self.assertEqual(monitor.check(record({}, 2)), [])
        alerts = monitor.check(record({"video_ids": [], "complete": True}, 3))
        self.assertEqual(alerts[0]["details"]["removed_from_snapshot"], ["a", "b", "c"])

    def test_livestream_unknown_and_deltas(self):
        monitor = LivestreamMonitor(self.db)
        monitor.check(record({"is_live": False}))
        self.assertEqual(monitor.check(record({"is_live": True, "room_id": "a", "viewer_count": 1}, 1))[0]["type"], "livestream_started")
        self.assertEqual(monitor.check(record({"is_live": None}, 2)), [])
        self.assertEqual(monitor.check(record({"is_live": True, "viewer_count": 2}, 3))[0]["type"], "livestream_viewer_count_changed")
        self.assertEqual(monitor.check(record({"is_live": False}, 4))[0]["type"], "livestream_ended")


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_bound_errors_continue_and_stop(self):
        scheduler = Scheduler(max_concurrency=1, max_jobs=2)
        active = 0
        peak = 0
        calls = 0
        ready = asyncio.Event()

        async def job():
            nonlocal active, peak, calls
            active += 1
            peak = max(peak, active)
            calls += 1
            try:
                await asyncio.sleep(0.001)
                if calls == 1:
                    raise RuntimeError("token=secret")
                if calls >= 4:
                    ready.set()
            finally:
                active -= 1

        scheduler.add_job("a", job, 0.001)
        scheduler.add_job("b", job, 0.001)
        task = asyncio.create_task(scheduler.run())
        try:
            await asyncio.wait_for(ready.wait(), 2)
            await scheduler.stop()
            await asyncio.wait_for(task, 2)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(peak, 1)
        self.assertEqual(active, 0)
        self.assertGreaterEqual(calls, 4)

    async def test_external_cancel_cleanup(self):
        scheduler = Scheduler()
        entered = asyncio.Event()
        cleaned = asyncio.Event()

        async def job():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

        scheduler.add_job("job", job, 1)
        task = asyncio.create_task(scheduler.run())
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(cleaned.is_set())


if __name__ == "__main__":
    unittest.main()
