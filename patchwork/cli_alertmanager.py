"""CLI interface for the alert manager."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from patchwork.alertmanager import AlertManager, Severity


def build_alertmanager_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="patchwork-alerts",
        description="Manage deployment alerts.",
    )
    parser.add_argument("--store", default="alerts.json", help="Path to alert store (default: alerts.json)")
    parser.add_argument("--format", choices=["text", "json"], default="text", dest="fmt")

    sub = parser.add_subparsers(dest="subcmd", required=True)

    fire_p = sub.add_parser("fire", help="Fire a new alert")
    fire_p.add_argument("service")
    fire_p.add_argument("message")
    fire_p.add_argument("--severity", choices=[s.value for s in Severity], default=Severity.WARNING.value)

    resolve_p = sub.add_parser("resolve", help="Resolve matching alerts")
    resolve_p.add_argument("service")
    resolve_p.add_argument("message")

    list_p = sub.add_parser("list", help="List active alerts")
    list_p.add_argument("--service", default=None, help="Filter by service")

    sub.add_parser("summary", help="Show active alert counts by severity")

    return parser


def _print_alerts(alerts, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps([a.to_dict() for a in alerts], indent=2))
        return
    if not alerts:
        print("No active alerts.")
        return
    for a in alerts:
        status = "RESOLVED" if a.is_resolved else "FIRING"
        print(f"[{a.severity.value.upper()}] {a.service}: {a.message}  ({status})")


def cmd_alerts(args: argparse.Namespace) -> int:
    manager = AlertManager(Path(args.store))

    if args.subcmd == "fire":
        alert = manager.fire(args.service, args.message, Severity(args.severity))
        if args.fmt == "json":
            print(json.dumps(alert.to_dict(), indent=2))
        else:
            print(f"Alert fired: [{alert.severity.value.upper()}] {alert.service}: {alert.message}")
        return 0

    if args.subcmd == "resolve":
        count = manager.resolve(args.service, args.message)
        if args.fmt == "json":
            print(json.dumps({"resolved": count}))
        else:
            print(f"Resolved {count} alert(s) for service '{args.service}'.")
        return 0

    if args.subcmd == "list":
        alerts = manager.active_for(args.service) if args.service else manager.all_active()
        _print_alerts(alerts, args.fmt)
        return 0

    if args.subcmd == "summary":
        s = manager.summary()
        if args.fmt == "json":
            print(json.dumps(s, indent=2))
        else:
            for sev, count in s.items():
                print(f"  {sev:<10} {count}")
        return 0

    return 1


def main() -> None:  # pragma: no cover
    parser = build_alertmanager_parser()
    args = parser.parse_args()
    raise SystemExit(cmd_alerts(args))


if __name__ == "__main__":  # pragma: no cover
    main()
