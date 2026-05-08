"""CLI sub-commands for the blame log."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from patchwork.blamelog import BlameLog


def build_blamelog_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    p = sub.add_parser("blame", help="Manage deployment blame log")
    p.add_argument("--log-file", default="blame.json", help="Path to blame log JSON")
    sp = p.add_subparsers(dest="blame_cmd")

    rec = sp.add_parser("record", help="Record a deployment attribution")
    rec.add_argument("service")
    rec.add_argument("actor")
    rec.add_argument("reason")
    rec.add_argument("--commit", default=None, dest="commit_sha")
    rec.add_argument("--ticket", default=None)

    ls = sp.add_parser("list", help="List blame entries")
    ls.add_argument("--service", default=None, help="Filter by service")
    ls.add_argument("--json", action="store_true", dest="as_json")

    return p


def cmd_blame(args: argparse.Namespace) -> None:
    log = BlameLog(Path(args.log_file))

    if args.blame_cmd == "record":
        entry = log.record(
            service=args.service,
            actor=args.actor,
            reason=args.reason,
            commit_sha=args.commit_sha,
            ticket=args.ticket,
        )
        print(f"Recorded: {entry}")

    elif args.blame_cmd == "list":
        entries = log.for_service(args.service) if args.service else log.all_entries()
        if args.as_json:
            print(json.dumps([e.to_dict() for e in entries], indent=2))
        else:
            if not entries:
                print("No blame entries found.")
            for e in entries:
                sha = f" [{e.commit_sha[:7]}]" if e.commit_sha else ""
                tkt = f" ({e.ticket})" if e.ticket else ""
                print(f"[{e.triggered_at}] {e.service} by {e.actor}: {e.reason}{sha}{tkt}")
    else:
        print("Use 'record' or 'list'. See --help.")
