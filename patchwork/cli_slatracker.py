"""CLI interface for reviewing SLA compliance from a recorded log."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from patchwork.slatracker import SLAEntry, SLAReport


def build_sla_parser(parent: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    kwargs = dict(description="Review SLA compliance records.")
    if parent is not None:
        parser = parent.add_parser("sla", **kwargs)
    else:
        parser = argparse.ArgumentParser(prog="patchwork-sla", **kwargs)

    sub = parser.add_subparsers(dest="sla_cmd")

    show = sub.add_parser("show", help="Display SLA entries from a log file.")
    show.add_argument("log_file", help="Path to JSON-lines SLA log.")
    show.add_argument(
        "--breached-only",
        action="store_true",
        default=False,
        help="Only show breached entries.",
    )
    show.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="fmt",
    )
    return parser


def _load_entries(log_file: str) -> list[SLAEntry]:
    path = Path(log_file)
    if not path.exists():
        print(f"Error: file not found: {log_file}", file=sys.stderr)
        sys.exit(1)
    entries = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(SLAEntry.from_dict(json.loads(line)))
    return entries


def cmd_sla(args: argparse.Namespace) -> None:
    if args.sla_cmd == "show":
        entries = _load_entries(args.log_file)
        if args.breached_only:
            entries = [e for e in entries if e.breached]

        report = SLAReport(entries=entries)

        if args.fmt == "json":
            print(json.dumps([e.to_dict() for e in entries], indent=2))
        else:
            if not entries:
                print("No SLA entries to display.")
            else:
                for e in entries:
                    print(repr(e))
                print()
                print(report.summary())
    else:
        print("No subcommand given. Use 'sla show <log_file>'.", file=sys.stderr)
        sys.exit(1)


def main() -> None:  # pragma: no cover
    parser = build_sla_parser()
    args = parser.parse_args()
    cmd_sla(args)


if __name__ == "__main__":  # pragma: no cover
    main()
