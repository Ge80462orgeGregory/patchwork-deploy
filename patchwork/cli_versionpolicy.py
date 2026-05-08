"""CLI entry point for version policy checks."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from patchwork.versionpolicy import VersionPolicyChecker


def build_versionpolicy_parser(sub=None) -> argparse.ArgumentParser:
    desc = "Check service versions against configured policies."
    if sub is not None:
        p = sub.add_parser("versioncheck", help=desc)
    else:
        p = argparse.ArgumentParser(prog="patchwork-versioncheck", description=desc)

    p.add_argument(
        "versions_file",
        help="JSON file mapping service -> {current, candidate}",
    )
    p.add_argument(
        "--pinned",
        metavar="FILE",
        default=None,
        help="JSON file mapping service -> pinned version",
    )
    p.add_argument(
        "--allow-downgrades",
        action="store_true",
        default=False,
        help="Allow candidate versions lower than current",
    )
    p.add_argument(
        "--no-semver",
        action="store_true",
        default=False,
        help="Disable semver validation",
    )
    p.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    return p


def cmd_versioncheck(args: argparse.Namespace) -> int:
    versions_path = Path(args.versions_file)
    if not versions_path.exists():
        print(f"ERROR: versions file not found: {versions_path}", file=sys.stderr)
        return 2

    try:
        versions = json.loads(versions_path.read_text())
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {versions_path}: {exc}", file=sys.stderr)
        return 2

    pinned: dict = {}
    if args.pinned:
        pinned_path = Path(args.pinned)
        if not pinned_path.exists():
            print(f"ERROR: pinned file not found: {pinned_path}", file=sys.stderr)
            return 2
        pinned = json.loads(pinned_path.read_text())

    checker = VersionPolicyChecker(
        allow_downgrades=args.allow_downgrades,
        require_semver=not args.no_semver,
        pinned_versions=pinned,
    )
    report = checker.check_all(versions)

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.summary())

    return 0 if report.is_compliant else 1


def main() -> None:  # pragma: no cover
    parser = build_versionpolicy_parser()
    args = parser.parse_args()
    sys.exit(cmd_versioncheck(args))


if __name__ == "__main__":  # pragma: no cover
    main()
