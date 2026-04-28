"""CLI sub-command: notify — re-emit notifications from a saved report file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from patchwork.executor import ExecutionReport, StepResult
from patchwork.notifier import Notifier
from patchwork.planner import DeployStep


def build_notify_parser(sub: "argparse._SubParsersAction") -> argparse.ArgumentParser:  # type: ignore[type-arg]
    p = sub.add_parser(
        "notify",
        help="Re-emit notifications from a saved JSON execution report.",
    )
    p.add_argument("report", help="Path to the JSON execution report file.")
    p.add_argument(
        "--webhook",
        metavar="URL",
        default=None,
        help="Webhook URL to POST the deployment outcome to.",
    )
    return p


def cmd_notify(args: argparse.Namespace) -> int:
    report_path = Path(args.report)
    if not report_path.exists():
        print(f"Error: report file not found: {report_path}", file=sys.stderr)
        return 1

    try:
        raw = json.loads(report_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in report: {exc}", file=sys.stderr)
        return 1

    steps = [
        StepResult(
            step=DeployStep(
                service=s["service"],
                action=s["action"],
                command=s["command"],
            ),
            success=s["success"],
            output=s.get("output", ""),
            error=s.get("error", ""),
        )
        for s in raw.get("steps", [])
    ]
    report = ExecutionReport(
        steps=steps,
        duration_seconds=raw.get("duration_seconds", 0.0),
    )

    notifier = Notifier(webhook_url=args.webhook)
    results = notifier.notify(report)

    failed = [r for r in results if not r.success]
    if failed:
        for r in failed:
            print(f"Notification failed [{r.channel}]: {r.message}", file=sys.stderr)
        return 1
    return 0
