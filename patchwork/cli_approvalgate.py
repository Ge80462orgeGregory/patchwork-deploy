"""CLI commands for the approval gate."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from patchwork.approvalgate import ApprovalGate, ApprovalError


def build_approvalgate_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:  # type: ignore[type-arg]
    p = sub.add_parser("approvals", help="Manage deployment approval gates")
    p.add_argument("--store", default="approvals.json", help="Path to approval store (default: approvals.json)")
    cmds = p.add_subparsers(dest="approval_cmd", required=True)

    req = cmds.add_parser("request", help="Request approval for a service")
    req.add_argument("service")
    req.add_argument("--by", required=True, dest="requested_by", help="Who is requesting")

    apr = cmds.add_parser("approve", help="Approve a pending request")
    apr.add_argument("service")
    apr.add_argument("--by", required=True, dest="approved_by", help="Who is approving")

    deny = cmds.add_parser("deny", help="Deny a pending request")
    deny.add_argument("service")

    cmds.add_parser("list", help="List all approval entries")

    return p


def _status_label(entry) -> str:
    if entry.is_approved():
        return f"APPROVED by {entry.approved_by}"
    if entry.denied:
        return "DENIED"
    return "PENDING"


def cmd_approvals(args: argparse.Namespace) -> int:
    gate = ApprovalGate(Path(args.store))

    try:
        if args.approval_cmd == "request":
            entry = gate.request(args.service, args.requested_by)
            print(f"[requested] {entry.service} — awaiting approval")

        elif args.approval_cmd == "approve":
            entry = gate.approve(args.service, args.approved_by)
            print(f"[approved]  {entry.service} by {entry.approved_by}")

        elif args.approval_cmd == "deny":
            entry = gate.deny(args.service)
            print(f"[denied]    {entry.service}")

        elif args.approval_cmd == "list":
            entries = gate.all_entries()
            if not entries:
                print("No approval entries found.")
            else:
                for e in entries:
                    print(f"  {e.service:<20} {_status_label(e)}")

    except ApprovalError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0
