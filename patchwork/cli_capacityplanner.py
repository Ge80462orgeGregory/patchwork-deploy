"""CLI entry-point for the capacity planner."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from patchwork.capacityplanner import evaluate_capacity


def build_capacity_parser(parent: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    kwargs = dict(
        prog="patchwork capacity",
        description="Check service replica capacity against defined limits.",
    )
    if parent is not None:
        parser = parent.add_parser("capacity", **kwargs)
    else:
        parser = argparse.ArgumentParser(**kwargs)

    parser.add_argument("config_file", help="JSON file with list of service configs")
    parser.add_argument(
        "--limits",
        metavar="FILE",
        default=None,
        help="JSON file mapping service -> {min_replicas, max_replicas}",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="output_format",
        help="Output format (default: text)",
    )
    return parser


def _print_text(report) -> None:
    print(report.summary())
    for entry in report.entries:
        status = "OK"
        if entry.is_over:
            status = "OVER"
        elif entry.is_under:
            status = "UNDER"
        print(f"  {entry.service}: desired={entry.desired} headroom={entry.headroom} [{status}]")


def cmd_capacity(args: argparse.Namespace) -> int:
    try:
        configs = json.loads(Path(args.config_file).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load config file: {exc}", file=sys.stderr)
        return 1

    limits = None
    if args.limits:
        try:
            limits = json.loads(Path(args.limits).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: cannot load limits file: {exc}", file=sys.stderr)
            return 1

    report = evaluate_capacity(configs, limits)

    if args.output_format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_text(report)

    return 1 if report.has_violations else 0


def main(argv=None) -> None:  # pragma: no cover
    parser = build_capacity_parser()
    args = parser.parse_args(argv)
    sys.exit(cmd_capacity(args))


if __name__ == "__main__":  # pragma: no cover
    main()
