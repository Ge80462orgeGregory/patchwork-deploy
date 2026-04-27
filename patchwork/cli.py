"""Simple CLI entry-point for patchwork-deploy."""

from __future__ import annotations

import argparse
import sys

from patchwork.reporter import ReportFormatter, ReportWriter
from patchwork.executor import ExecutionReport, StepResult
from patchwork.planner import DeployStep, DeployPlan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchwork",
        description="Lightweight deployment orchestrator",
    )
    sub = parser.add_subparsers(dest="command")

    report_cmd = sub.add_parser("report", help="Display a saved report file")
    report_cmd.add_argument("file", help="Path to a JSON report file")
    report_cmd.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (default: text)",
    )

    return parser


def cmd_report(args: argparse.Namespace) -> int:
    import json

    try:
        with open(args.file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read report: {exc}", file=sys.stderr)
        return 1

    # Reconstruct a lightweight ExecutionReport for formatting purposes
    steps_raw = data.get("steps", [])
    results: list[StepResult] = []
    for s in steps_raw:
        step = DeployStep(action=s["action"], description=s["description"])
        results.append(
            StepResult(
                step=step,
                success=s["success"],
                output=s.get("output", ""),
                error=s.get("error", ""),
            )
        )

    report = ExecutionReport(
        service=data["service"],
        host=data["host"],
        results=results,
    )

    formatter = ReportFormatter(report)
    if args.format == "json":
        print(formatter.to_json())
    else:
        print(formatter.to_text())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "report":
        return cmd_report(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
