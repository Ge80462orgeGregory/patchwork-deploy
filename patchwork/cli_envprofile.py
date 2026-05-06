"""CLI subcommand: patchwork profiles — manage environment profiles."""
from __future__ import annotations

import argparse
import json
import sys

from patchwork.envprofile import EnvProfile, ProfileStore


def build_profile_parser(sub=None) -> argparse.ArgumentParser:
    if sub is None:
        parser = argparse.ArgumentParser(description="Manage environment profiles")
        sub = parser.add_subparsers(dest="profiles_cmd")
    else:
        parser = sub.add_parser("profiles", help="Manage environment profiles")
        sub = parser.add_subparsers(dest="profiles_cmd")

    # list
    sub.add_parser("list", help="List all profiles")

    # show
    p_show = sub.add_parser("show", help="Show a profile")
    p_show.add_argument("name")

    # set
    p_set = sub.add_parser("set", help="Create or update a profile")
    p_set.add_argument("name")
    p_set.add_argument("--ssh-user", default="deploy")
    p_set.add_argument("--ssh-port", type=int, default=22)
    p_set.add_argument("--dry-run", action="store_true")
    p_set.add_argument(
        "--env", nargs="*", default=[], metavar="KEY=VALUE",
        help="Environment variables (KEY=VALUE)",
    )
    p_set.add_argument(
        "--allow", nargs="*", default=[], metavar="SERVICE",
        help="Restrict to these services (empty = all)",
    )

    # delete
    p_del = sub.add_parser("delete", help="Delete a profile")
    p_del.add_argument("name")

    return parser


def cmd_profiles(args: argparse.Namespace, store_path: str = "profiles.json") -> int:
    store = ProfileStore(store_path)
    cmd = getattr(args, "profiles_cmd", None)

    if cmd == "list":
        profiles = store.list()
        if not profiles:
            print("No profiles defined.")
            return 0
        for p in profiles:
            flag = " [dry-run]" if p.dry_run else ""
            print(f"  {p.name}{flag}  user={p.ssh_user}  port={p.ssh_port}")
        return 0

    if cmd == "show":
        p = store.get(args.name)
        if p is None:
            print(f"Profile not found: {args.name}", file=sys.stderr)
            return 1
        print(json.dumps(p.to_dict(), indent=2))
        return 0

    if cmd == "set":
        env_vars = {}
        for pair in (args.env or []):
            if "=" not in pair:
                print(f"Invalid env pair: {pair!r}", file=sys.stderr)
                return 1
            k, v = pair.split("=", 1)
            env_vars[k] = v
        profile = EnvProfile(
            name=args.name,
            ssh_user=args.ssh_user,
            ssh_port=args.ssh_port,
            env_vars=env_vars,
            allowed_services=list(args.allow or []),
            dry_run=args.dry_run,
        )
        store.save(profile)
        print(f"Profile '{args.name}' saved.")
        return 0

    if cmd == "delete":
        if store.delete(args.name):
            print(f"Profile '{args.name}' deleted.")
            return 0
        print(f"Profile not found: {args.name}", file=sys.stderr)
        return 1

    print("No subcommand given. Use --help.", file=sys.stderr)
    return 1
