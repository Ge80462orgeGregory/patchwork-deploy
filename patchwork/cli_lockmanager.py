"""CLI sub-commands for the deployment lock manager."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from patchwork.lockmanager import LockError, LockManager

_DEFAULT_STORE = ".patchwork/locks.json"


def build_lockmanager_parser(parent: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = parent.add_parser("lock", help="Manage deployment locks")
    sub = p.add_subparsers(dest="lock_cmd", required=True)

    # acquire
    acq = sub.add_parser("acquire", help="Acquire a lock for a service")
    acq.add_argument("service", help="Service name")
    acq.add_argument("owner", help="Lock owner identifier (e.g. CI job ID)")
    acq.add_argument("--ttl", type=float, default=300.0, metavar="SECONDS",
                     help="Lock TTL in seconds (default: 300)")
    acq.add_argument("--store", default=_DEFAULT_STORE, metavar="FILE")

    # release
    rel = sub.add_parser("release", help="Release a lock")
    rel.add_argument("service")
    rel.add_argument("owner")
    rel.add_argument("--store", default=_DEFAULT_STORE, metavar="FILE")

    # status
    st = sub.add_parser("status", help="Show active locks")
    st.add_argument("--store", default=_DEFAULT_STORE, metavar="FILE")

    # purge
    pu = sub.add_parser("purge", help="Remove expired locks")
    pu.add_argument("--store", default=_DEFAULT_STORE, metavar="FILE")


def cmd_lock(args: argparse.Namespace) -> int:
    store = Path(args.store)
    manager = LockManager(store)

    if args.lock_cmd == "acquire":
        try:
            entry = manager.acquire(args.service, args.owner, ttl_seconds=args.ttl)
            print(f"Acquired lock: {entry}")
            return 0
        except LockError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.lock_cmd == "release":
        try:
            released = manager.release(args.service, args.owner)
            if released:
                print(f"Released lock for service {args.service!r}")
            else:
                print(f"No lock found for service {args.service!r}")
            return 0
        except LockError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.lock_cmd == "status":
        active = manager.status()
        if not active:
            print("No active locks.")
        for name, entry in active.items():
            print(f"  {name}: owner={entry.owner!r}  ttl={entry.ttl_seconds}s")
        return 0

    if args.lock_cmd == "purge":
        count = manager.purge_expired()
        print(f"Purged {count} expired lock(s).")
        return 0

    print(f"Unknown lock sub-command: {args.lock_cmd}", file=sys.stderr)
    return 2
