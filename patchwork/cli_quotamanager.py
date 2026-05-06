"""CLI sub-commands for the quota manager."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from patchwork.quotamanager import QuotaExceeded, QuotaManager

_DEFAULT_STORE = "quota_store.json"


def build_quota_parser(parser: argparse.ArgumentParser | None = None) -> argparse.ArgumentParser:
    if parser is None:
        parser = argparse.ArgumentParser(prog="patchwork-quota", description="Manage deployment quotas")
    parser.add_argument("--store", default=_DEFAULT_STORE, help="Path to quota store JSON file")
    parser.add_argument("--format", choices=["text", "json"], default="text")

    sub = parser.add_subparsers(dest="quota_cmd")

    # configure
    p_cfg = sub.add_parser("configure", help="Set quota for a service")
    p_cfg.add_argument("service")
    p_cfg.add_argument("--max-deploys", type=int, default=10)
    p_cfg.add_argument("--window", type=int, default=3600, help="Window in seconds")

    # check
    p_chk = sub.add_parser("check", help="Check and record a deployment")
    p_chk.add_argument("service")

    # status
    sub.add_parser("status", help="Show current quota status")

    return parser


def _print_status(status: dict, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(status, indent=2))
        return
    if not status:
        print("No quotas configured.")
        return
    for svc, data in status.items():
        remaining = max(0, data["max_deploys"] - len(data["deploy_times"]))
        print(
            f"{svc}: {remaining}/{data['max_deploys']} remaining "
            f"(window={data['window_seconds']}s)"
        )


def cmd_quota(args: argparse.Namespace) -> int:
    manager = QuotaManager(Path(args.store))
    fmt = getattr(args, "format", "text")

    if args.quota_cmd == "configure":
        entry = manager.configure(args.service, args.max_deploys, args.window)
        if fmt == "json":
            print(json.dumps(entry.to_dict(), indent=2))
        else:
            print(
                f"Configured quota for {entry.service!r}: "
                f"{entry.max_deploys} deploys / {entry.window_seconds}s"
            )
        return 0

    if args.quota_cmd == "check":
        try:
            entry = manager.check_and_record(args.service, time.time())
        except KeyError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        except QuotaExceeded as exc:
            print(f"QUOTA EXCEEDED: {exc}", file=sys.stderr)
            return 1
        remaining = entry.remaining()
        if fmt == "json":
            print(json.dumps({"service": entry.service, "remaining": remaining}))
        else:
            print(f"Deployment recorded for {entry.service!r}. Remaining: {remaining}")
        return 0

    if args.quota_cmd == "status":
        _print_status(manager.status(), fmt)
        return 0

    print("No sub-command specified. Use --help.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    _parser = build_quota_parser()
    sys.exit(cmd_quota(_parser.parse_args()))
