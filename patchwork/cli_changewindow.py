"""CLI sub-commands for managing change windows."""
from __future__ import annotations

import argparse
import json
from datetime import time
from pathlib import Path

from patchwork.changewindow import ChangeWindow, ChangeWindowStore


def build_changewindow_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:  # noqa: SLF001
    p = sub.add_parser("windows", help="Manage deployment change windows")
    sp = p.add_subparsers(dest="windows_cmd", required=True)

    # list
    sp.add_parser("list", help="List all change windows")

    # add
    add_p = sp.add_parser("add", help="Add a change window")
    add_p.add_argument("name")
    add_p.add_argument("--days", nargs="+", type=int, default=[0, 1, 2, 3, 4],
                       metavar="DOW", help="Days of week (0=Mon … 6=Sun)")
    add_p.add_argument("--start", default="09:00", help="Start time HH:MM")
    add_p.add_argument("--end", default="17:00", help="End time HH:MM")
    add_p.add_argument("--disabled", action="store_true")

    # remove
    rm_p = sp.add_parser("remove", help="Remove a change window")
    rm_p.add_argument("name")

    # check
    sp.add_parser("check", help="Check if deployment is currently allowed")

    p.add_argument("--store", default="change_windows.json",
                   help="Path to windows JSON store")
    return p


def _print_windows(windows: list) -> None:
    if not windows:
        print("No change windows defined.")
        return
    for w in windows:
        status = "enabled" if w.enabled else "disabled"
        days = ",".join(str(d) for d in w.days)
        print(f"  {w.name:20s}  days=[{days}]  {w.start}-{w.end}  [{status}]")


def cmd_windows(args: argparse.Namespace) -> int:
    store = ChangeWindowStore(Path(args.store))

    if args.windows_cmd == "list":
        _print_windows(store.all())
        return 0

    if args.windows_cmd == "add":
        window = ChangeWindow(
            name=args.name,
            days=args.days,
            start=time.fromisoformat(args.start),
            end=time.fromisoformat(args.end),
            enabled=not args.disabled,
        )
        store.add(window)
        print(f"Added change window {args.name!r}.")
        return 0

    if args.windows_cmd == "remove":
        store.remove(args.name)
        print(f"Removed change window {args.name!r}.")
        return 0

    if args.windows_cmd == "check":
        allowed = store.is_deployment_allowed()
        if allowed:
            print("Deployment is ALLOWED in the current change window.")
            return 0
        print("Deployment is BLOCKED — outside all active change windows.")
        return 1

    return 0
