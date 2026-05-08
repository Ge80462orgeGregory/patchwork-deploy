"""CLI commands for canary deployment management."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from patchwork.canarymanager import CanaryError, CanaryManager


def build_canary_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchwork-canary",
        description="Manage canary deployments",
    )
    parser.add_argument("--store", default="canary.json", help="Path to canary store file")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # create
    p_create = sub.add_parser("create", help="Start a canary rollout")
    p_create.add_argument("service", help="Service name")
    p_create.add_argument("--weight", type=int, default=10, help="Canary traffic weight (0-100)")

    # promote
    p_promote = sub.add_parser("promote", help="Promote canary to full rollout")
    p_promote.add_argument("service", help="Service name")

    # abort
    p_abort = sub.add_parser("abort", help="Abort canary rollout")
    p_abort.add_argument("service", help="Service name")

    # list
    p_list = sub.add_parser("list", help="List active canaries")
    p_list.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON")

    return parser


def _print_entry(entry) -> None:
    status = "active" if entry.is_active() else ("promoted" if entry.promoted else "aborted")
    print(f"  {entry.service:<20} canary={entry.canary_weight}%  baseline={entry.baseline_weight}%  [{status}]")


def cmd_canary(args: argparse.Namespace) -> int:
    manager = CanaryManager(store_path=Path(args.store))
    try:
        if args.subcommand == "create":
            entry = manager.create(args.service, args.weight)
            print(f"[canary] Created canary for {entry.service!r} at {entry.canary_weight}% traffic.")

        elif args.subcommand == "promote":
            entry = manager.promote(args.service)
            print(f"[canary] Promoted {entry.service!r} — full rollout active.")

        elif args.subcommand == "abort":
            entry = manager.abort(args.service)
            print(f"[canary] Aborted canary for {entry.service!r} — rolled back to baseline.")

        elif args.subcommand == "list":
            active = manager.list_active()
            if args.as_json:
                print(json.dumps([e.to_dict() for e in active], indent=2))
            else:
                if not active:
                    print("No active canaries.")
                else:
                    print(f"Active canaries ({len(active)}):")
                    for e in active:
                        _print_entry(e)
    except CanaryError as exc:
        print(f"[error] {exc}")
        return 1
    return 0


def main() -> None:
    parser = build_canary_parser()
    args = parser.parse_args()
    raise SystemExit(cmd_canary(args))


if __name__ == "__main__":
    main()
