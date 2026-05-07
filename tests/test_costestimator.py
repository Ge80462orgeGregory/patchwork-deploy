"""Tests for patchwork.costestimator."""
from __future__ import annotations

import pytest

from patchwork.planner import DeployPlan, DeployStep
from patchwork.costestimator import (
    CostEntry,
    CostEstimator,
    CostReport,
    DEFAULT_WEIGHTS,
)


def _make_plan(*steps: tuple[str, str]) -> DeployPlan:
    """Build a DeployPlan from (service, kind) tuples."""
    plan = DeployPlan()
    for service, kind in steps:
        plan.add_step(DeployStep(service=service, kind=kind, command=f"run {kind}"))
    return plan


# ---------------------------------------------------------------------------
# CostEntry
# ---------------------------------------------------------------------------

class TestCostEntry:
    def test_to_dict_contains_all_keys(self):
        entry = CostEntry(service="api", kind="pull", weight=1.0)
        d = entry.to_dict()
        assert set(d) == {"service", "kind", "weight"}

    def test_repr_contains_service_and_kind(self):
        entry = CostEntry(service="api", kind="restart", weight=2.0)
        r = repr(entry)
        assert "api" in r
        assert "restart" in r


# ---------------------------------------------------------------------------
# CostReport
# ---------------------------------------------------------------------------

class TestCostReport:
    def test_within_budget_when_budget_is_zero(self):
        report = CostReport(total=999.0, budget=0.0)
        assert report.within_budget is True

    def test_within_budget_when_under(self):
        report = CostReport(total=3.0, budget=5.0)
        assert report.within_budget is True

    def test_over_budget_when_above(self):
        report = CostReport(total=6.0, budget=5.0)
        assert report.within_budget is False

    def test_to_dict_contains_required_keys(self):
        report = CostReport(total=1.0, budget=10.0)
        d = report.to_dict()
        assert "entries" in d
        assert "total" in d
        assert "budget" in d
        assert "within_budget" in d

    def test_summary_contains_status_ok(self):
        report = CostReport(total=2.0, budget=5.0)
        assert "OK" in report.summary()

    def test_summary_contains_over_budget(self):
        report = CostReport(total=9.0, budget=5.0)
        assert "OVER BUDGET" in report.summary()


# ---------------------------------------------------------------------------
# CostEstimator
# ---------------------------------------------------------------------------

class TestCostEstimator:
    def test_empty_plan_has_zero_cost(self):
        estimator = CostEstimator()
        report = estimator.estimate(_make_plan())
        assert report.total == 0.0
        assert report.entries == []

    def test_known_kind_uses_default_weight(self):
        estimator = CostEstimator()
        report = estimator.estimate(_make_plan(("svc", "pull")))
        assert report.total == DEFAULT_WEIGHTS["pull"]

    def test_unknown_kind_defaults_to_one(self):
        estimator = CostEstimator()
        report = estimator.estimate(_make_plan(("svc", "unknown_op")))
        assert report.total == 1.0

    def test_multiple_steps_sum_correctly(self):
        estimator = CostEstimator()
        plan = _make_plan(("a", "pull"), ("b", "restart"), ("c", "stop"))
        report = estimator.estimate(plan)
        expected = DEFAULT_WEIGHTS["pull"] + DEFAULT_WEIGHTS["restart"] + DEFAULT_WEIGHTS["stop"]
        assert report.total == pytest.approx(expected)

    def test_custom_weights_are_applied(self):
        estimator = CostEstimator(weights={"pull": 10.0})
        report = estimator.estimate(_make_plan(("svc", "pull")))
        assert report.total == 10.0

    def test_budget_propagated_to_report(self):
        estimator = CostEstimator(budget=5.0)
        report = estimator.estimate(_make_plan())
        assert report.budget == 5.0

    def test_entry_count_matches_steps(self):
        plan = _make_plan(("a", "pull"), ("b", "start"))
        report = CostEstimator().estimate(plan)
        assert len(report.entries) == 2

    def test_entry_service_names_preserved(self):
        plan = _make_plan(("frontend", "restart"))
        report = CostEstimator().estimate(plan)
        assert report.entries[0].service == "frontend"
