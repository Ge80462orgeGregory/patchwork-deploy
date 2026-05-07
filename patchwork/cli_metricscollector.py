"""CLI interface for displaying collected metrics from a JSON log file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from patchwork.metricscollector import MetricSample


def build_metrics_parser(sub=None) -> argparse.ArgumentParser:
    if sub is not None:
        p = sub.add_parser("metrics", help="Display collected deployment metrics")
    else:
        p = argparse.ArgumentParser(prog="patchwork-metrics", description="Show deployment metrics")
    p.add_argument("log_file", help="Path to JSON metrics log")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--filter", dest="name_filter", default=None, help="Show only metrics matching this name")
    return p


def _load_samples(path: Path) -> list[MetricSample]:
    raw = json.loads(path.read_text())
    return [
        MetricSample(
            name=r["name"],
            value=r["value"],
            labels=r.get("labels", {}),
            timestamp=r.get("timestamp", 0.0),
        )
        for r in raw
    ]


def cmd_metrics(args: argparse.Namespace) -> int:
    path = Path(args.log_file)
    if not path.exists():
        print(f"[error] file not found: {path}", file=sys.stderr)
        return 1

    samples = _load_samples(path)
    if args.name_filter:
        samples = [s for s in samples if s.name == args.name_filter]

    if args.format == "json":
        print(json.dumps([s.to_dict() for s in samples], indent=2))
        return 0

    if not samples:
        print("No metrics found.")
        return 0

    totals: dict[str, float] = {}
    for s in samples:
        totals[s.name] = totals.get(s.name, 0.0) + s.value

    print(f"{'Metric':<35} {'Total':>12}")
    print("-" * 50)
    for name in sorted(totals):
        print(f"{name:<35} {totals[name]:>12.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(cmd_metrics(build_metrics_parser().parse_args()))
