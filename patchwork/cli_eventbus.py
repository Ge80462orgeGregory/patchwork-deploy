"""CLI sub-command: inspect event bus history stored in a JSON log file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_eventbus_parser(sub: argparse.ArgumentParser | None = None) -> argparse.ArgumentParser:
    if sub is None:
        sub = argparse.ArgumentParser(prog="patchwork eventbus")
    sub.add_argument("log_file", help="Path to JSON event log file")
    sub.add_argument("--topic", default=None, help="Filter events by topic")
    sub.add_argument("--format", choices=["text", "json"], default="text", dest="fmt")
    sub.add_argument("--limit", type=int, default=0, help="Max events to show (0 = all)")
    return sub


def cmd_eventbus(args: argparse.Namespace) -> int:
    path = Path(args.log_file)
    if not path.exists():
        print(f"[error] log file not found: {path}", file=sys.stderr)
        return 1

    try:
        events = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        print(f"[error] invalid JSON: {exc}", file=sys.stderr)
        return 1

    if not isinstance(events, list):
        print("[error] expected a JSON array of events", file=sys.stderr)
        return 1

    if args.topic:
        events = [e for e in events if e.get("topic") == args.topic]

    if args.limit and args.limit > 0:
        events = events[-args.limit:]

    if args.fmt == "json":
        print(json.dumps(events, indent=2))
    else:
        if not events:
            print("No events found.")
        for e in events:
            print(f"[{e.get('timestamp', '?')}] {e.get('topic', '?')} — {e.get('payload', {})}")

    return 0
