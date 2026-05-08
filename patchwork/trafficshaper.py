"""Traffic shaping: weight-based routing rules between service versions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


class TrafficShaperError(Exception):
    """Raised when traffic shaping configuration is invalid."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"TrafficShaperError({self.args[0]!r})"


@dataclass
class TrafficWeight:
    """A single version -> weight mapping for a service."""

    version: str
    weight: int  # 0-100

    def to_dict(self) -> dict:
        return {"version": self.version, "weight": self.weight}

    @classmethod
    def from_dict(cls, data: dict) -> "TrafficWeight":
        return cls(version=data["version"], weight=int(data["weight"]))

    def __repr__(self) -> str:
        return f"TrafficWeight(version={self.version!r}, weight={self.weight})"


@dataclass
class TrafficRule:
    """Routing rule for a named service with one or more weighted versions."""

    service: str
    weights: List[TrafficWeight] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.service:
            raise TrafficShaperError("service name must not be empty")
        self._validate_weights()

    def _validate_weights(self) -> None:
        if not self.weights:
            return
        total = sum(w.weight for w in self.weights)
        if total != 100:
            raise TrafficShaperError(
                f"weights for '{self.service}' must sum to 100, got {total}"
            )
        for w in self.weights:
            if w.weight < 0:
                raise TrafficShaperError(
                    f"weight for version '{w.version}' must be >= 0"
                )

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "weights": [w.to_dict() for w in self.weights],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrafficRule":
        weights = [TrafficWeight.from_dict(w) for w in data.get("weights", [])]
        return cls(service=data["service"], weights=weights)

    def __repr__(self) -> str:
        return f"TrafficRule(service={self.service!r}, versions={len(self.weights)})"


@dataclass
class TrafficShaper:
    """Collection of traffic rules keyed by service name."""

    _rules: Dict[str, TrafficRule] = field(default_factory=dict, init=False)

    def add_rule(self, rule: TrafficRule) -> None:
        self._rules[rule.service] = rule

    def get(self, service: str) -> Optional[TrafficRule]:
        return self._rules.get(service)

    def all_rules(self) -> List[TrafficRule]:
        return list(self._rules.values())

    def remove(self, service: str) -> bool:
        if service in self._rules:
            del self._rules[service]
            return True
        return False

    def __len__(self) -> int:
        return len(self._rules)

    def to_dict(self) -> dict:
        return {s: r.to_dict() for s, r in self._rules.items()}
