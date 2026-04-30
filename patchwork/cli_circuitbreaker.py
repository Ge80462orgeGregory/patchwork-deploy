"""CLI sub-command for inspecting circuit-breaker state."""
from __future__ import annotations

import argparse
import json
from typing import List

from patchwork.circuitbreaker import CircuitBreaker, CircuitBreakerOptions


def build_circuitbreaker_parser(subparsers) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "circuit",
        help="Show or reset circuit-breaker state for named services.",
    )
    p.add_argument(
        "services",
        nargs="+",
        metavar="SERVICE",
        help="Service names to inspect.",
    )
    p.add_argument(
        "--failure-threshold",
        type=int,
        default=3,
        dest="failure_threshold",
        help="Failures before opening (default: 3).",
    )
    p.add_argument(
        "--recovery-timeout",
        type=float,
        default=30.0,
        dest="recovery_timeout",
        help="Seconds before attempting recovery (default: 30).",
    )
    p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    p.set_defaults(func=cmd_circuit)
    return p


def _build_status(services: List[str], opts: CircuitBreakerOptions) -> List[dict]:
    rows = []
    for name in services:
        cb = CircuitBreaker(name=name, options=opts)
        rows.append({
            "service": name,
            "state": cb.state.value,
            "allow_request": cb.allow_request(),
        })
    return rows


def _print_text(rows: List[dict]) -> None:
    for row in rows:
        allowed = "yes" if row["allow_request"] else "no"
        print(f"{row['service']:30s}  state={row['state']:10s}  allow={allowed}")


def cmd_circuit(args: argparse.Namespace) -> None:
    opts = CircuitBreakerOptions(
        failure_threshold=args.failure_threshold,
        recovery_timeout=args.recovery_timeout,
    )
    rows = _build_status(args.services, opts)
    if args.format == "json":
        print(json.dumps(rows, indent=2))
    else:
        _print_text(rows)
