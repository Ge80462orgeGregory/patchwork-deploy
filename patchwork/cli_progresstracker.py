"""CLI sub-command: progress — show live deployment progress from a log file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from patchwork.progresstracker import ProgressTracker


def build_progress_parser(parent: argparse._SubParsersAction) -> argparse.ArgumentParser:  # type: ignore[type-arg]
    p = parent.add_parser("progress", help="Show deployment progress summary")
    p.add_argument(
        "log_file",
        help="JSON-lines progress log produced during a pipeline run",
    )
    p.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        default=False,
        help="Emit output as JSON",
    )
    return p


def cmd_progress(args: argparse.Namespace) -> int:
    path = Path(args.log_file)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 1

    tracker = ProgressTracker()

    try:
        for raw in path.read_text().splitlines():
            raw = raw.strip()
            if not raw:
                continue
            event = json.loads(raw)
            service = event["service"]
            kind = event.get("kind", "step")
            if kind == "register":
                tracker.register(service, event["total_steps"])
            elif kind == "step":
                tracker.advance(service, failed=event.get("failed", False))
    except (KeyError, json.JSONDecodeError) as exc:
        print(f"error: malformed log file — {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        output = [
            {
                "service": tracker.get(s).service,
                "completed": tracker.get(s).completed,
                "failed": tracker.get(s).failed,
                "total_steps": tracker.get(s).total_steps,
                "percent": tracker.get(s).percent,
                "done": tracker.get(s).is_done,
                "elapsed": tracker.get(s).elapsed,
            }
            for s in [e.service for e in [tracker.get(svc) for svc in vars(tracker._entries)]]
        ]
        # rebuild cleanly
        rows = []
        for svc_name, entry in tracker._entries.items():  # type: ignore[attr-defined]
            rows.append({
                "service": entry.service,
                "completed": entry.completed,
                "failed": entry.failed,
                "total_steps": entry.total_steps,
                "percent": entry.percent,
                "done": entry.is_done,
                "elapsed": entry.elapsed,
            })
        print(json.dumps(rows, indent=2))
    else:
        for line in tracker.summary():
            print(line)

    return 0
