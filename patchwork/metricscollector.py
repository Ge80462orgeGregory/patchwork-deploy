"""Lightweight metrics collector for tracking deployment counters and timings."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class MetricsError(Exception):
    def __repr__(self) -> str:
        return f"MetricsError({self.args[0]!r})"


@dataclass
class MetricSample:
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "labels": self.labels,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        label_str = ",".join(f"{k}={v}" for k, v in self.labels.items())
        return f"MetricSample({self.name!r}, value={self.value}, labels={{{label_str}}})"


@dataclass
class MetricsCollector:
    """Accumulates counters and timing samples for a deployment run."""
    _samples: List[MetricSample] = field(default_factory=list, init=False)

    def record(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> MetricSample:
        if not name:
            raise MetricsError("Metric name must not be empty")
        sample = MetricSample(name=name, value=value, labels=labels or {})
        self._samples.append(sample)
        return sample

    def increment(self, name: str, labels: Optional[Dict[str, str]] = None, by: float = 1.0) -> MetricSample:
        return self.record(name, by, labels)

    def all_samples(self) -> List[MetricSample]:
        return list(self._samples)

    def by_name(self, name: str) -> List[MetricSample]:
        return [s for s in self._samples if s.name == name]

    def total(self, name: str) -> float:
        return sum(s.value for s in self.by_name(name))

    def clear(self) -> None:
        self._samples.clear()

    def summary(self) -> Dict[str, float]:
        names = {s.name for s in self._samples}
        return {n: self.total(n) for n in sorted(names)}

    def __len__(self) -> int:
        return len(self._samples)
