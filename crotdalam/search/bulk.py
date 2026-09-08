"""Bounded asynchronous engine search from local CSV or UTF-8 lines."""

import asyncio
import csv
import io
from pathlib import Path
from .keyword import check_query
from ..collectors.base import validate_record


class BulkSearch:
    """run(path, threads=4, limit=20) -> flattened contract records.

    CSV needs a keyword header (case-insensitive). Other files use nonblank
    lines. Preserves input order and duplicate queries. Each failed query
    emits a search_error record; successful empty queries emit search_status.
    At most 1 MB, 1000 queries, 32 workers, 30 seconds per engine call.
    """

    def __init__(self, engine):
        self.engine = engine

    async def run(self, path, threads: int = 4, limit: int = 20) -> list[dict]:
        check_query("bulk", limit)
        if isinstance(threads, bool) or not isinstance(threads, int) or not 1 <= threads <= 32:
            raise ValueError("threads must be an integer in 1..32")

        def read_queries():
            source = Path(path)
            with source.open("rb") as handle:
                raw = handle.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("Bulk input exceeds 1 MB")
            text = raw.decode("utf-8-sig")
            if source.suffix.lower() == ".csv":
                reader = csv.DictReader(io.StringIO(text))
                headers = reader.fieldnames or []
                keys = [h for h in headers if h.strip().casefold() == "keyword"]
                if len(keys) != 1:
                    raise ValueError("CSV requires exactly one keyword column")
                values = ((row.get(keys[0]) or "").strip() for row in reader)
            else:
                values = (line.strip() for line in text.splitlines())
            queries = []
            for value in values:
                if value:
                    queries.append(value)
                    if len(queries) > 1000:
                        raise ValueError("Bulk input exceeds 1000 queries")
            return queries

        queries = await asyncio.to_thread(read_queries)
        results = [[] for _ in queries]
        queue = asyncio.Queue()
        for index, query in enumerate(queries):
            queue.put_nowait((index, query))

        async def worker():
            while not queue.empty():
                index, query = queue.get_nowait()
                try:
                    check_query(query, limit)
                    async with asyncio.timeout(30):
                        records = await self.engine.search(query, limit=limit)
                    if not isinstance(records, list) or len(records) > limit:
                        raise ValueError("Engine search must return a list no longer than limit")
                    results[index] = [validate_record(record) for record in records]
                    if not records:
                        results[index] = [{"data_type": "search_status", "target": query,
                                           "value": {"status": "empty", "query_index": index}}]
                except Exception as exc:
                    results[index] = [{"data_type": "search_error", "target": query,
                                       "value": {"status": "failed", "error_type": type(exc).__name__,
                                                 "error": str(exc)[:1000], "query_index": index}}]
                finally:
                    queue.task_done()

        await asyncio.gather(*(worker() for _ in range(min(threads, len(queries)))))
        return [record for group in results for record in group]
