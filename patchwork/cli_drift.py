"""CLI subcommand: drift — detect config drift on remote services."""
from __future__ import annotations

import argparse
import json
import sys

from patchwork.loader import ConfigLoader
from patchwork.driftdetector import DriftDetector
from patchwork.ssh import SSHClient


def build_drift_parser(subparsers=None) -> argparse.ArgumentParser:
    if subparsers is not None:
        parser = subparsers.add_parser("drift", help="Detect config drift on remote services")
    else:
        parser = argparse.ArgumentParser(
            prog="patchwork-drift",
            description="Detect config drift on remote services",
        )
    parser.add_argument("config", help="Path to service config file (JSON)")
    parser.add_argument("--host", required=True, help="SSH host")
    parser.add_argument("--user", default="deploy", help="SSH user (default: deploy)")
    parser.add_argument("--port", type=int, default=22, help="SSH port (default: 22)")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--exit-code",
        action="store_true",
        help="Exit with code 1 if drift is detected",
    )
    return parser


def cmd_drift(args: argparse.Namespace) -> int:
    loader = ConfigLoader()
    try:
        config = loader.load(args.config)
    except Exception as exc:  # pragma: no cover
        print(f"[drift] Failed to load config: {exc}", file=sys.stderr)
        return 2

    try:
        client = SSHClient(
            host=args.host,
            user=args.user,
            port=args.port,
        )
        client.connect()
    except Exception as exc:  # pragma: no cover
        print(f"[drift] SSH connection failed: {exc}", file=sys.stderr)
        return 2

    try:
        detector = DriftDetector(client)
        report = detector.check(config)
    finally:
        client.close()

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.summary)

    if args.exit_code and report.has_drift:
        return 1
    return 0


def main() -> None:  # pragma: no cover
    parser = build_drift_parser()
    args = parser.parse_args()
    sys.exit(cmd_drift(args))


if __name__ == "__main__":  # pragma: no cover
    main()
