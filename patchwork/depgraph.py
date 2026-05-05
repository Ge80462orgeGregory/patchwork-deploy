"""Dependency graph for ordering deployment steps by service dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


class CyclicDependencyError(Exception):
    """Raised when a cycle is detected in the dependency graph."""

    def __repr__(self) -> str:
        return f"CyclicDependencyError({self.args[0]!r})"


@dataclass
class DependencyGraph:
    """Directed acyclic graph of service deployment dependencies."""

    _edges: Dict[str, Set[str]] = field(default_factory=dict)  # service -> deps

    def add_service(self, name: str) -> None:
        """Register a service with no dependencies."""
        if name not in self._edges:
            self._edges[name] = set()

    def add_dependency(self, service: str, depends_on: str) -> None:
        """Declare that *service* must be deployed after *depends_on*."""
        self.add_service(service)
        self.add_service(depends_on)
        self._edges[service].add(depends_on)

    def services(self) -> List[str]:
        """Return all registered service names."""
        return list(self._edges.keys())

    def dependencies_of(self, service: str) -> Set[str]:
        """Return the direct dependencies of *service*."""
        return set(self._edges.get(service, set()))

    def topological_order(self) -> List[str]:
        """Return services sorted so every dependency precedes its dependent.

        Raises CyclicDependencyError if the graph contains a cycle.
        """
        in_degree: Dict[str, int] = {s: 0 for s in self._edges}
        for deps in self._edges.values():
            for dep in deps:
                in_degree[dep] = in_degree.get(dep, 0)  # already counted above

        # Kahn's algorithm
        queue: List[str] = [s for s, d in in_degree.items() if d == 0]
        queue.sort()  # deterministic output
        result: List[str] = []

        # Rebuild in-degree from scratch to count correctly
        in_deg: Dict[str, int] = {s: 0 for s in self._edges}
        for service, deps in self._edges.items():
            for dep in deps:
                in_deg[service] = in_deg.get(service, 0)
            # deps are *prerequisites*, so they don't add to this service's in-degree
            # Instead: for each dep, the current service depends on it
            # => dep must come first => service has in-degree += 1 per dep
        in_deg = {s: len(deps) for s, deps in self._edges.items()}
        queue = sorted(s for s, d in in_deg.items() if d == 0)

        # reverse adjacency: dep -> list of services that depend on it
        rev: Dict[str, List[str]] = {s: [] for s in self._edges}
        for service, deps in self._edges.items():
            for dep in deps:
                rev[dep].append(service)

        while queue:
            node = queue.pop(0)
            result.append(node)
            for dependent in sorted(rev.get(node, [])):
                in_deg[dependent] -= 1
                if in_deg[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._edges):
            visited = set(result)
            cycle_nodes = [s for s in self._edges if s not in visited]
            raise CyclicDependencyError(
                f"Cycle detected among services: {sorted(cycle_nodes)}"
            )
        return result

    def __len__(self) -> int:
        return len(self._edges)
