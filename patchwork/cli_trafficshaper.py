"""CLI for inspecting and managing traffic shaping rules."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from patchwork.trafficshaper import TrafficRule, TrafficShaper, TrafficWeight


def build_trafficshaper_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchwork-traffic",
        description="Manage traffic shaping rules between service versions.",
    )
    sub = parser.add_subparsers(dest="subcmd", required=True)

    # list
    ls = sub.add_parser("list", help="List all traffic rules")
    ls.add_argument("--rules-file", default="traffic_rules.json", metavar="FILE")
    ls.add_argument("--json", dest="as_json", action="store_true")

    # set
    sv = sub.add_parser("set", help="Set traffic weights for a service")
    sv.add_argument("service", help="Service name")
    sv.add_argument(
        "--weight",
        action="append",
        dest="weights",
        metavar="VERSION:WEIGHT",
        required=True,
        help="version:weight pair, e.g. v1:70 (may repeat)",
    )
    sv.add_argument("--rules-file", default="traffic_rules.json", metavar="FILE")

    # remove
    rm = sub.add_parser("remove", help="Remove traffic rule for a service")
    rm.add_argument("service")
    rm.add_argument("--rules-file", default="traffic_rules.json", metavar="FILE")

    return parser


def _load_shaper(path: str) -> TrafficShaper:
    shaper = TrafficShaper()
    p = Path(path)
    if p.exists():
        data = json.loads(p.read_text())
        for entry in data.values():
            shaper.add_rule(TrafficRule.from_dict(entry))
    return shaper


def _save_shaper(shaper: TrafficShaper, path: str) -> None:
    Path(path).write_text(json.dumps(shaper.to_dict(), indent=2))


def _print_rules(shaper: TrafficShaper, as_json: bool) -> None:
    if as_json:
        print(json.dumps(shaper.to_dict(), indent=2))
        return
    rules = shaper.all_rules()
    if not rules:
        print("No traffic rules defined.")
        return
    for rule in rules:
        print(f"[{rule.service}]")
        for w in rule.weights:
            print(f"  {w.version}: {w.weight}%")


def cmd_traffic(args: argparse.Namespace) -> int:
    if args.subcmd == "list":
        shaper = _load_shaper(args.rules_file)
        _print_rules(shaper, getattr(args, "as_json", False))
        return 0

    if args.subcmd == "set":
        pairs = []
        for item in args.weights:
            try:
                version, raw_weight = item.rsplit(":", 1)
                pairs.append(TrafficWeight(version=version, weight=int(raw_weight)))
            except (ValueError, TypeError):
                print(f"Invalid weight spec: {item!r}", file=sys.stderr)
                return 1
        try:
            rule = TrafficRule(service=args.service, weights=pairs)
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        shaper = _load_shaper(args.rules_file)
        shaper.add_rule(rule)
        _save_shaper(shaper, args.rules_file)
        print(f"Updated traffic rule for '{args.service}'.")
        return 0

    if args.subcmd == "remove":
        shaper = _load_shaper(args.rules_file)
        removed = shaper.remove(args.service)
        if removed:
            _save_shaper(shaper, args.rules_file)
            print(f"Removed traffic rule for '{args.service}'.")
        else:
            print(f"No rule found for '{args.service}'.")
        return 0

    return 1  # pragma: no cover
