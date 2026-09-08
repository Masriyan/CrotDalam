"""Fixed-delay async polling. No cron support; each job is strictly serial."""

import asyncio
import math
from collections.abc import Awaitable, Callable

from crotdalam.utils.logger import get_logger


class Scheduler:
    def __init__(self, max_concurrency: int = 4, max_jobs: int = 100):
        if any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in (max_concurrency, max_jobs)):
            raise ValueError("bounds must be positive integers")
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_jobs = max_jobs
        self._jobs: dict[str, tuple[Callable[[], Awaitable[object]], float]] = {}
        self._tasks: list[asyncio.Task] = []
        self._running = False
        self._stop = asyncio.Event()
        self._logger = get_logger(__name__)

    def add_job(self, name: str, callback: Callable[[], Awaitable[object]], interval: float) -> None:
        if self._running:
            raise RuntimeError("cannot add jobs while running")
        if not name or name in self._jobs or len(self._jobs) >= self._max_jobs:
            raise ValueError("job name must be unique and job limit must not be exceeded")
        if isinstance(interval, bool) or not isinstance(interval, (float, int)) or not math.isfinite(interval) or interval <= 0:
            raise ValueError("interval must be finite and positive")
        if not callable(callback):
            raise ValueError("callback must be an async callable")
        self._jobs[name] = callback, interval

    async def _poll(self, name: str, callback: Callable[[], Awaitable[object]], interval: float) -> None:
        while not self._stop.is_set():
            try:
                async with self._semaphore:
                    if self._stop.is_set():
                        return
                    await callback()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception("Polling job %s failed; continuing", name)
            await asyncio.sleep(interval)

    async def run(self) -> None:
        if self._running:
            raise RuntimeError("scheduler is already running")
        self._running = True
        self._stop.clear()
        try:
            self._tasks = [asyncio.create_task(self._poll(name, callback, interval), name=name)
                           for name, (callback, interval) in self._jobs.items()]
            await self._stop.wait()
        finally:
            self._stop.set()
            for task in self._tasks:
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()
            self._running = False

    async def stop(self) -> None:
        self._stop.set()
        current = asyncio.current_task()
        for task in self._tasks:
            if task is not current:
                task.cancel()
        await asyncio.gather(*(task for task in self._tasks if task is not current), return_exceptions=True)
