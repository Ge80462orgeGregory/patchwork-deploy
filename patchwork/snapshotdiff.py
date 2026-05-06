"""snapshotdiff.py – compare two rollback snapshots and summarise config drift."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from patchwork.rollback import Snapshot


@dataclass
class FieldDelta:
    """A single field that changed between two snapshots."""
    field: str
    before: object
    after: object

    def __repr__(self) -> str:  # pragma: no cover
        return f"FieldDelta({self.field!r}: {self.before!r} -> {self.after!r})"

    def to_dict(self) -> dict:
        return {"field": self.field, "before": self.before, "after": self.after}


@dataclass
class SnapshotDiffResult:
    """Result of diffing two snapshots for a single service."""
    service: str
    deltas: List[FieldDelta] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.deltas)

    def summary(self) -> str:
        if not self.has_changes:
            return f"{self.service}: no changes"
        lines = [f"{self.service}: {len(self.deltas)} change(s)"]
        for d in self.deltas:
            lines.append(f"  {d.field}: {d.before!r} -> {d.after!r}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "has_changes": self.has_changes,
            "deltas": [d.to_dict() for d in self.deltas],
        }


_TRACKED_FIELDS = ("image", "replicas", "env", "ports", "command")


def diff_snapshots(
    before: Snapshot,
    after: Snapshot,
    fields: Optional[tuple] = None,
) -> SnapshotDiffResult:
    """Return a :class:`SnapshotDiffResult` comparing *before* and *after*.

    Only fields listed in *fields* (defaults to ``_TRACKED_FIELDS``) are
    compared.  Both snapshots must reference the same service.
    """
    if before.service != after.service:
        raise ValueError(
            f"Cannot diff snapshots for different services: "
            f"{before.service!r} vs {after.service!r}"
        )

    tracked = fields or _TRACKED_FIELDS
    deltas: List[FieldDelta] = []

    before_cfg = before.config.to_dict() if hasattr(before.config, "to_dict") else vars(before.config)
    after_cfg = after.config.to_dict() if hasattr(after.config, "to_dict") else vars(after.config)

    for f_name in tracked:
        bv = before_cfg.get(f_name)
        av = after_cfg.get(f_name)
        if bv != av:
            deltas.append(FieldDelta(field=f_name, before=bv, after=av))

    return SnapshotDiffResult(service=before.service, deltas=deltas)
