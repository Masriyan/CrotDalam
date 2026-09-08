"""Bounded bulk keyword search using one context-managed engine."""

import asyncio
import csv
from pathlib import Path


class BulkSearch:
    def __init__(self, engine, threads=4):
        if threads < 1:
            raise ValueError("threads must be positive")
        self.engine = engine
        self.threads = threads

    async def run(self, csv_path, limit=20):
        with Path(csv_path).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames or []
            column = next((key for key in ("keyword", "username", "target") if key in fields), None)
            if column is None:
                raise ValueError("CSV requires a keyword, username, or target header")
            keywords = list(dict.fromkeys(row[column].strip() for row in reader if row.get(column, "").strip()))
        queue = asyncio.Queue()
        for keyword in keywords:
            queue.put_nowait(keyword)

        async def worker():
            while not queue.empty():
                keyword = queue.get_nowait()
                try:
                    await self.engine.search(keyword, limit=limit)
                finally:
                    queue.task_done()

        tasks = [asyncio.create_task(worker()) for _ in range(min(self.threads, len(keywords)))]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        return keywords
