"""CLI sub-command: healthcheck — verify service health over SSH after deploy."""
from __future__ import annotations

import argparse
import json
import sys

from patchwork.healthcheck import HealthCheckOptions, HealthChecker
from patchwork.ssh import SSHClient, SSHConfig


def build_healthcheck_parser(subparsers=None) -> argparse.ArgumentParser:
    description = "Check health of one or more services via SSH."
    if subparsers is not None:
        parser = subparsers.add_parser("healthcheck", help=description)
    else:
        parser = argparse.ArgumentParser(prog="patchwork-healthcheck", description=description)

    parser.add_argument("services", nargs="+", metavar="SERVICE", help="Service name(s) to check")
    parser.add_argument("--host", required=True, help="SSH host")
    parser.add_argument("--user", default="root", help="SSH user (default: root)")
    parser.add_argument("--port", type=int, default=22, help="SSH port (default: 22)")
    parser.add_argument("--key", dest="key_path", default=None, help="Path to SSH private key")
    parser.add_argument("--retries", type=int, default=3, help="Number of check attempts (default: 3)")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between retries in seconds")
    parser.add_argument("--command", default="systemctl is-active {service}", help="Health check command template")
    parser.add_argument("--expected", default="active", dest="expected_output", help="Expected output substring")
    parser.add_argument("--format", choices=["text", "json"], default="text", dest="output_format")
    parser.set_defaults(func=cmd_healthcheck)
    return parser


def cmd_healthcheck(args: argparse.Namespace) -> int:
    ssh_cfg = SSHConfig(
        host=args.host,
        user=args.user,
        port=args.port,
        key_path=args.key_path,
    )
    opts = HealthCheckOptions(
        command=args.command,
        retries=args.retries,
        retry_delay=args.delay,
        expected_output=args.expected_output,
    )

    with SSHClient(ssh_cfg) as client:
        checker = HealthChecker(client, opts)
        results = checker.check_many(args.services)

    if args.output_format == "json":
        data = [
            {
                "service": r.service,
                "passed": r.passed,
                "attempts": r.attempts,
                "message": r.message,
                "output": r.output,
            }
            for r in results
        ]
        print(json.dumps(data, indent=2))
    else:
        for r in results:
            status = "OK" if r.passed else "FAIL"
            print(f"[{status}] {r.service}: {r.message}")

    all_passed = all(r.passed for r in results)
    return 0 if all_passed else 1
