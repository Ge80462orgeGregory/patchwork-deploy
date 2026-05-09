"""CLI helper that wires a SignalHandler into a long-running pipeline run."""
from __future__ import annotations

import argparse
import sys
import time

from patchwork.signalhandler import SignalHandler


def build_signal_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchwork-signal",
        description="Run a blocking loop with graceful shutdown support (demo).",
    )
    parser.add_argument(
        "--tick",
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="Seconds between heartbeat ticks (default: 1.0).",
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=0,
        metavar="N",
        help="Stop after N ticks (0 = run until signal, default: 0).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    return parser


def cmd_signal(args: argparse.Namespace) -> None:  # pragma: no cover
    handler = SignalHandler()
    handler.register()

    ticks = 0
    try:
        while not handler.shutdown.is_set():
            ticks += 1
            if args.format == "json":
                print(f'{{"tick": {ticks}}}', flush=True)
            else:
                print(f"[tick {ticks}] running…", flush=True)

            if args.max_ticks and ticks >= args.max_ticks:
                break

            time.sleep(args.tick)
    finally:
        handler.unregister()
        sig = handler.shutdown.signal_received
        if args.format == "json":
            import json
            print(json.dumps({"ticks": ticks, "signal": sig}))
        else:
            reason = f"signal {sig}" if sig else "max ticks reached"
            print(f"Shutdown after {ticks} tick(s) — {reason}")


def main(argv: list[str] | None = None) -> None:  # pragma: no cover
    parser = build_signal_parser()
    args = parser.parse_args(argv)
    cmd_signal(args)


if __name__ == "__main__":  # pragma: no cover
    main()
