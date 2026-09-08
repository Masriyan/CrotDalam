"""Argparse entry point. Core and optional UI dependencies are imported on use."""

import argparse
import asyncio
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

from crotdalam.reports import REPORTS, generate
from crotdalam.reports.common import load_json, normalize


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def duration(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be a finite nonnegative number")
    return number


def build_parser():
    parser = argparse.ArgumentParser(prog="crotdalam", description="Collect and report evidence; use only authorized sources.")
    parser.add_argument("--corpus", help="Local corpus path")
    parser.add_argument("--database", help="SQLite evidence database")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("search", "analyze", "report", "crawl", "monitor", "validate", "extract", "correlate", "config", "session", "proxy", "shell", "gui", "import-har"):
        sub = commands.add_parser(name)
        sub.add_argument("--corpus", default=argparse.SUPPRESS)
        sub.add_argument("--database", default=argparse.SUPPRESS)
        if name == "import-har":
            sub.add_argument("input", help="Local HAR capture (never replayed)")
            sub.add_argument("--inspect", action="store_true", help="Metadata/counts only; do not write records")
        elif name == "extract":
            sub.add_argument("--input", required=True, help="JSON report or SQLite database")
        elif name == "correlate":
            sub.add_argument("--input", required=True, help="JSON report or SQLite database")
            sub.add_argument("--min-accounts", type=positive, default=2)
        elif name == "search":
            group = sub.add_mutually_exclusive_group(required=True)
            group.add_argument("--keyword")
            group.add_argument("--username")
            sub.add_argument("--limit", type=positive, default=20)
        elif name == "analyze":
            group = sub.add_mutually_exclusive_group(required=True)
            group.add_argument("--username")
            group.add_argument("--input", help="JSON report or SQLite database")
        elif name == "report":
            sub.add_argument("--format", choices=("all", *REPORTS), default="html")
            sub.add_argument("--input", required=True, help="JSON report or SQLite database")
            sub.add_argument("--output", required=True, help="File path; directory for format all")
            sub.add_argument("--case-id", default="UNASSIGNED")
            sub.add_argument("--analyst", default="Not specified")
        elif name == "crawl":
            sub.add_argument("--csv", required=True)
            sub.add_argument("--threads", type=positive, default=4)
            sub.add_argument("--limit", type=positive, default=20)
        elif name == "monitor":
            sub.add_argument("--keyword", required=True)
            sub.add_argument("--rounds", type=positive, default=3)
            sub.add_argument("--interval", type=duration, default=60)
            sub.add_argument("--limit", type=positive, default=20)
        elif name == "validate":
            sub.add_argument("--input", required=True)
            sub.add_argument("--format", choices=("json", "sqlite"), default=None)
        elif name in ("config", "session", "proxy"):
            sub.add_argument("action", choices=("show",) if name == "config" else ("list",))
            if name != "config":
                sub.add_argument("--file", help="Optional JSON list file")
    return parser


def load_records(path, format=None):
    source = Path(path)
    if not source.is_file():
        raise ValueError(f"Input does not exist: {source}")
    kind = format or ("json" if source.suffix.lower() == ".json" else "sqlite" if source.suffix.lower() in (".db", ".sqlite", ".sqlite3") else None)
    if kind == "json":
        return load_json(source)
    if kind != "sqlite":
        raise ValueError("Expected a .json, .db, .sqlite, or .sqlite3 input")
    from crotdalam.utils.database import Database
    db = Database(str(source))
    try:
        return normalize(db.records())
    finally:
        db.close()


def settings_for(args):
    from crotdalam.config.settings import Settings
    settings = Settings.from_env()
    overrides = {key: getattr(args, key) for key in ("corpus", "database") if getattr(args, key, None) is not None}
    return replace(settings, **overrides)


def summarize(records):
    from collections import Counter
    return {"records": len(records), "targets": len({r["target"] for r in records}),
            "data_types": dict(Counter(r["data_type"] for r in records)),
            "note": "Descriptive counts only; no identity attribution or risk inference."}


ENGINE_ABSENT = (
    "The network-facing collection engine (crotdalam.core.engine) is not part of "
    "this release, so '{command}' cannot run. Offline workflows are available: "
    "'import-har' to ingest an authorized capture, then 'validate', 'analyze --input' "
    "and 'report'. See docs/SCOPE.md and docs/ROADMAP.md.")


def load_engine(command):
    """Import the optional engine, or explain precisely why the command cannot run."""
    try:
        from crotdalam.core.engine import Engine
    except ImportError as exc:
        raise RuntimeError(ENGINE_ABSENT.format(command=command)) from exc
    return Engine


async def run_engine(args):
    Engine = load_engine(args.command)
    settings = settings_for(args)
    if args.command == "crawl":
        settings = replace(settings, concurrency=args.threads)
    async with Engine(settings) as engine:
        if args.command == "search":
            if args.username:
                await engine.collect("username", args.username)
            else:
                await engine.search(args.keyword, limit=args.limit)
        elif args.command == "analyze":
            await engine.collect("username", args.username)
        elif args.command == "crawl":
            from .bulk import BulkSearch
            await BulkSearch(engine, args.threads).run(args.csv, args.limit)
        elif args.command == "monitor":
            for index in range(args.rounds):
                await engine.search(args.keyword, limit=args.limit)
                print(f"Completed round {index + 1}/{args.rounds}", file=sys.stderr)
                if index + 1 < args.rounds:
                    await asyncio.sleep(args.interval)
        records = normalize(engine.db.records())
    return summarize(records) if args.command == "analyze" else {"scope": "database snapshot (includes existing records)", "records": records}


def execute(args):
    if args.command == "import-har":
        from crotdalam.collectors.har_collector import import_har
        if not args.inspect and not args.database:
            raise ValueError("import-har requires --database unless --inspect is used")
        records, summary = import_har(args.input, inspect_only=args.inspect)
        summary["stored"] = 0
        if not args.inspect:
            from crotdalam.utils.database import Database
            db = Database(args.database)
            try:
                for record in records:
                    db.store(record)
                    summary["stored"] += 1
            finally:
                db.close()
        print(json.dumps(summary, ensure_ascii=True, indent=2))
        return 0
    if args.command == "report":
        records = load_records(args.input)
        formats = tuple(REPORTS) if args.format == "all" else (args.format,)
        failed = False
        for format in formats:
            output = Path(args.output) / f"report.{format}" if args.format == "all" else Path(args.output)
            try:
                print(generate(records, output, format, args.case_id, args.analyst))
            except RuntimeError as exc:
                if args.format != "all":
                    raise
                print(f"{format}: {exc}", file=sys.stderr)
                failed = True
        return 1 if failed else 0
    if args.command == "validate":
        count = len(load_records(args.input, args.format))
        source = Path(args.input)
        kind = args.format or ("json" if source.suffix.lower() == ".json"
                               else "sqlite" if source.suffix.lower() in (".db", ".sqlite", ".sqlite3") else None)
        if kind == "sqlite":
            from crotdalam.utils.database import Database
            db = Database(str(source))
            try:
                seal = db.verify_chain()
            finally:
                db.close()
            print(f"Valid: {count} records; evidence chain intact "
                  f"({'keyed' if seal['keyed'] else 'unkeyed'} seal {seal['chain_head'][:16]}…)")
        else:
            print(f"Valid: {count} records")
        return 0
    if args.command == "extract":
        from crotdalam.analyzers import SelectorExtractor
        payload = SelectorExtractor().analyze(load_records(args.input))
    elif args.command == "correlate":
        from crotdalam.analyzers import CoordinationAnalyzer
        payload = CoordinationAnalyzer(min_accounts=args.min_accounts).analyze(load_records(args.input))
    elif args.command == "analyze" and args.input:
        payload = summarize(load_records(args.input))
    elif args.command == "config":
        payload = asdict(settings_for(args))
    elif args.command in ("session", "proxy"):
        if not args.file:
            print(f"No {args.command} file configured. Supply --file with a JSON list.")
            return 0
        payload = json.loads(Path(args.file).read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            raise ValueError("List file must contain a JSON array")
    elif args.command == "shell":
        from .shell import InvestigationShell
        InvestigationShell(corpus=args.corpus, database=args.database).cmdloop()
        return 0
    elif args.command == "gui":
        from .gui import launch
        launch(settings_for(args))
        return 0
    else:
        payload = asyncio.run(run_engine(args))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return execute(args)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f"crotdalam: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Cancelled", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
