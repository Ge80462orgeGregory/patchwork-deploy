"""CLI sub-command: rollback a service to its last known-good snapshot."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from patchwork.rollback import RollbackStore
from patchwork.ssh import SSHClient
from patchwork.executor import Executor
from patchwork.planner import DeployPlan, DeployStep


DEFAULT_STORE = Path(".patchwork") / "snapshots.json"


def build_rollback_parser(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("service", help="Service name to roll back")
    sub.add_argument(
        "--store",
        default=str(DEFAULT_STORE),
        help="Path to snapshot store (default: .patchwork/snapshots.json)",
    )
    sub.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    sub.add_argument("--host", help="Override SSH host from snapshot")
    sub.add_argument("--user", default="deploy", help="SSH user (default: deploy)")


def cmd_rollback(args: argparse.Namespace) -> int:
    store = RollbackStore(Path(args.store))
    snap = store.latest(args.service)
    if snap is None:
        print(f"[rollback] No snapshot found for service '{args.service}'.", file=sys.stderr)
        return 1

    cfg = snap.config
    host = args.host or cfg.host

    print(f"[rollback] Restoring '{cfg.name}' to image={cfg.image} replicas={cfg.replicas}")
    print(f"[rollback] Snapshot timestamp: {snap.timestamp:.0f}")

    plan = DeployPlan()
    plan.add_step(DeployStep(
        service=cfg.name,
        command=f"docker service update --image {cfg.image} --replicas {cfg.replicas} {cfg.name}",
        description=f"rollback {cfg.name} to {cfg.image}",
    ))

    if args.dry_run:
        print("[rollback] Dry-run mode — no changes applied.")
        for step in plan:
            print(f"  would run: {step.command}")
        return 0

    client = SSHClient(host=host, user=args.user)
    executor = Executor(client)
    report = executor.run(plan)

    if report.success:
        print(f"[rollback] '{cfg.name}' rolled back successfully.")
        return 0
    else:
        for fs in report.failed_steps:
            print(f"[rollback] FAILED: {fs.step.command}\n  stderr: {fs.result.stderr}", file=sys.stderr)
        return 1
