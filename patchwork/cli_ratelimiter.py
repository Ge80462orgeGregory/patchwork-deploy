"""CLI sub-commands for inspecting rate-limiter status."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List

from patchwork.ratelimiter import RateLimiter


def build_ratelimiter_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "ratelimit",
        help="Check or reset rate-limit status for services",
    )
    p.add_argument(
        "services",
        nargs="+",
        metavar="SERVICE",
        help="Service names to inspect",
    )
    p.add_argument(
        "--interval",
        type=float,
        default=60.0,
        metavar="SECONDS",
        help="Minimum seconds between deploys (default: 60)",
    )
    p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="output_format",
        help="Output format (default: text)",
    )
    p.set_defaults(func=cmd_ratelimit)


def cmd_ratelimit(args: argparse.Namespace) -> int:
    """Print rate-limit status for requested services."""
    try:
        rl = RateLimiter(min_interval_seconds=args.interval)
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    results = _build_status(rl, args.services)

    if args.output_format == "json":
        print(json.dumps(results, indent=2))
    else:
        _print_text(results)

    return 0


def _build_status(rl: RateLimiter, services: List[str]) -> dict:  # type: ignore[type-arg]
    rows = {}
    for svc in services:
        allowed = rl.is_allowed(svc)
        rows[svc] = {
            "allowed": allowed,
            "remaining_wait_seconds": rl.status().get(svc, 0.0),
        }
    return rows


def _print_text(results: dict) -> None:  # type: ignore[type-arg]
    for svc, info in results.items():
        status = "OK" if info["allowed"] else f"WAIT {info['remaining_wait_seconds']:.1f}s"
        print(f"  {svc:<30} {status}")
