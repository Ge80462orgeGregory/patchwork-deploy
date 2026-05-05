"""Tests for patchwork.depgraph."""
import pytest

from patchwork.depgraph import CyclicDependencyError, DependencyGraph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _graph(*edges: tuple) -> DependencyGraph:
    """Build a DependencyGraph from (service, depends_on) tuples."""
    g = DependencyGraph()
    for service, dep in edges:
        g.add_dependency(service, dep)
    return g


# ---------------------------------------------------------------------------
# DependencyGraph – basic API
# ---------------------------------------------------------------------------

class TestDependencyGraph:
    def test_add_service_registers_node(self):
        g = DependencyGraph()
        g.add_service("api")
        assert "api" in g.services()

    def test_len_reflects_service_count(self):
        g = DependencyGraph()
        g.add_service("a")
        g.add_service("b")
        assert len(g) == 2

    def test_add_dependency_registers_both_services(self):
        g = _graph(("app", "db"))
        assert "app" in g.services()
        assert "db" in g.services()

    def test_dependencies_of_returns_direct_deps(self):
        g = _graph(("app", "db"), ("app", "cache"))
        assert g.dependencies_of("app") == {"db", "cache"}

    def test_dependencies_of_unknown_service_returns_empty(self):
        g = DependencyGraph()
        assert g.dependencies_of("ghost") == set()


# ---------------------------------------------------------------------------
# Topological ordering
# ---------------------------------------------------------------------------

class TestTopologicalOrder:
    def test_single_service_no_deps(self):
        g = DependencyGraph()
        g.add_service("api")
        assert g.topological_order() == ["api"]

    def test_simple_chain_db_before_app(self):
        g = _graph(("app", "db"))
        order = g.topological_order()
        assert order.index("db") < order.index("app")

    def test_diamond_dependency_order(self):
        # frontend -> api -> db
        # frontend -> cache -> db
        g = _graph(
            ("api", "db"),
            ("cache", "db"),
            ("frontend", "api"),
            ("frontend", "cache"),
        )
        order = g.topological_order()
        assert order.index("db") < order.index("api")
        assert order.index("db") < order.index("cache")
        assert order.index("api") < order.index("frontend")
        assert order.index("cache") < order.index("frontend")

    def test_independent_services_all_present(self):
        g = DependencyGraph()
        for svc in ["a", "b", "c"]:
            g.add_service(svc)
        order = g.topological_order()
        assert sorted(order) == ["a", "b", "c"]

    def test_cycle_raises_cyclic_dependency_error(self):
        g = _graph(("a", "b"), ("b", "c"), ("c", "a"))
        with pytest.raises(CyclicDependencyError):
            g.topological_order()

    def test_self_loop_raises_cyclic_dependency_error(self):
        g = _graph(("a", "a"))
        with pytest.raises(CyclicDependencyError):
            g.topological_order()

    def test_output_is_deterministic(self):
        g = DependencyGraph()
        for svc in ["z", "y", "x"]:
            g.add_service(svc)
        assert g.topological_order() == g.topological_order()


# ---------------------------------------------------------------------------
# CyclicDependencyError repr
# ---------------------------------------------------------------------------

class TestCyclicDependencyError:
    def test_repr_contains_message(self):
        err = CyclicDependencyError("cycle!")
        assert "cycle!" in repr(err)
