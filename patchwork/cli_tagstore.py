"""CLI commands for managing deployment tags."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from patchwork.tagstore import DeploymentTag, TagStore

_DEFAULT_PATH = ".patchwork/tags.json"


def build_tagstore_parser(parent: argparse._SubParsersAction) -> None:
    p = parent.add_parser("tags", help="Manage deployment tags")
    sub = p.add_subparsers(dest="tag_cmd", required=True)

    # put
    put_p = sub.add_parser("put", help="Attach tags to a deployment")
    put_p.add_argument("service")
    put_p.add_argument("deploy_id")
    put_p.add_argument("tags", nargs="+", metavar="KEY=VALUE")
    put_p.add_argument("--store", default=_DEFAULT_PATH)

    # get
    get_p = sub.add_parser("get", help="Show tags for a deployment")
    get_p.add_argument("service")
    get_p.add_argument("deploy_id")
    get_p.add_argument("--store", default=_DEFAULT_PATH)
    get_p.add_argument("--json", dest="as_json", action="store_true")

    # list
    list_p = sub.add_parser("list", help="List all deployments for a service")
    list_p.add_argument("service")
    list_p.add_argument("--store", default=_DEFAULT_PATH)
    list_p.add_argument("--json", dest="as_json", action="store_true")

    # delete
    del_p = sub.add_parser("delete", help="Remove tags for a deployment")
    del_p.add_argument("service")
    del_p.add_argument("deploy_id")
    del_p.add_argument("--store", default=_DEFAULT_PATH)


def _parse_tags(raw: list[str]) -> dict:
    result = {}
    for item in raw:
        if "=" not in item:
            print(f"[tags] invalid tag format (expected KEY=VALUE): {item!r}", file=sys.stderr)
            sys.exit(1)
        k, v = item.split("=", 1)
        result[k.strip()] = v.strip()
    return result


def cmd_tags(args: argparse.Namespace) -> None:
    store = TagStore(path=Path(args.store))

    if args.tag_cmd == "put":
        tag = DeploymentTag(
            service=args.service,
            deploy_id=args.deploy_id,
            tags=_parse_tags(args.tags),
        )
        store.put(tag)
        print(f"[tags] tagged {args.service}/{args.deploy_id} with {tag.tags}")

    elif args.tag_cmd == "get":
        tag = store.get(args.service, args.deploy_id)
        if tag is None:
            print(f"[tags] no tags found for {args.service}/{args.deploy_id}", file=sys.stderr)
            sys.exit(1)
        if args.as_json:
            print(json.dumps(tag.to_dict(), indent=2))
        else:
            for k, v in tag.tags.items():
                print(f"  {k}: {v}")

    elif args.tag_cmd == "list":
        tags = store.list_for_service(args.service)
        if args.as_json:
            print(json.dumps([t.to_dict() for t in tags], indent=2))
        else:
            for t in tags:
                print(f"  {t.deploy_id}: {t.tags}")

    elif args.tag_cmd == "delete":
        removed = store.delete(args.service, args.deploy_id)
        if removed:
            print(f"[tags] removed tags for {args.service}/{args.deploy_id}")
        else:
            print(f"[tags] nothing to remove for {args.service}/{args.deploy_id}", file=sys.stderr)
            sys.exit(1)
