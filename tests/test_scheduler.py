"""Tests for patchwork.scheduler."""
from __future__ import annotations

import pytest

from patchwork.planner import DeployPlan, DeployStep
from patchwork.scheduler import Scheduler, SchedulerOptions, ScheduledBatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(*cmds: str) -> DeployPlan:
    plan = DeployPlan()
    for cmd in cmds:
        plan.add_step(DeployStep(command=cmd, description=cmd))
    return plan


# ---------------------------------------------------------------------------
# SchedulerOptions validation
# ---------------------------------------------------------------------------

class TestSchedulerOptions:
    def test_defaults_are_valid(self):
        opts = SchedulerOptions()
        assert opts.max_parallel == 1
        assert opts.step_delay_seconds == 0.0
        assert opts.service_delay_seconds == 0.0

    def test_invalid_max_parallel_raises(self):
        with pytest.raises(ValueError, match="max_parallel"):
            SchedulerOptions(max_parallel=0)

    def test_negative_step_delay_raises(self):
        with pytest.raises(ValueError, match="step_delay_seconds"):
            SchedulerOptions(step_delay_seconds=-1)

    def test_negative_service_delay_raises(self):
        with pytest.raises(ValueError, match="service_delay_seconds"):
            SchedulerOptions(service_delay_seconds=-0.5)


# ---------------------------------------------------------------------------
# ScheduledBatch
# ---------------------------------------------------------------------------

class TestScheduledBatch:
    def test_add_and_len(self):
        batch = ScheduledBatch()
        batch.add("svc-a", _make_plan("cmd1"))
        batch.add("svc-b", _make_plan("cmd2"))
        assert len(batch) == 2

    def test_iter_order(self):
        batch = ScheduledBatch()
        batch.add("alpha", _make_plan())
        batch.add("beta", _make_plan())
        names = [name for name, _ in batch]
        assert names == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# Scheduler.build_batch
# ---------------------------------------------------------------------------

class TestBuildBatch:
    def setup_method(self):
        self.scheduler = Scheduler()
        self.plans = {
            "api": _make_plan("deploy api"),
            "worker": _make_plan("deploy worker"),
            "db": _make_plan("migrate db"),
        }

    def test_no_priority_preserves_insertion_order(self):
        batch = self.scheduler.build_batch(self.plans)
        names = [n for n, _ in batch]
        assert names == ["api", "worker", "db"]

    def test_priority_order_respected(self):
        batch = self.scheduler.build_batch(
            self.plans, priority_order=["db", "api"]
        )
        names = [n for n, _ in batch]
        assert names[0] == "db"
        assert names[1] == "api"
        assert "worker" in names

    def test_unknown_priority_keys_ignored(self):
        batch = self.scheduler.build_batch(
            self.plans, priority_order=["nonexistent", "db"]
        )
        names = [n for n, _ in batch]
        assert "nonexistent" not in names
        assert names[0] == "db"


# ---------------------------------------------------------------------------
# Scheduler.iter_steps
# ---------------------------------------------------------------------------

class TestIterSteps:
    def test_yields_all_steps(self):
        scheduler = Scheduler()
        plans = {
            "svc-a": _make_plan("cmd-a1", "cmd-a2"),
            "svc-b": _make_plan("cmd-b1"),
        }
        batch = scheduler.build_batch(plans)
        results = list(scheduler.iter_steps(batch))
        assert len(results) == 3
        service_names = [svc for svc, _ in results]
        assert service_names.count("svc-a") == 2
        assert service_names.count("svc-b") == 1

    def test_step_commands_match(self):
        scheduler = Scheduler()
        plans = {"svc": _make_plan("echo hello", "echo world")}
        batch = scheduler.build_batch(plans)
        cmds = [step.command for _, step in scheduler.iter_steps(batch)]
        assert cmds == ["echo hello", "echo world"]
