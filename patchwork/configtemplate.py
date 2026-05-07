"""Config template renderer with variable substitution for service configs."""
from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from typing import Any


class TemplateError(Exception):
    """Raised when template rendering fails."""

    def __repr__(self) -> str:  # pragma: no cover
        return f"TemplateError({self.args[0]!r})"


_VAR_RE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


@dataclass
class RenderResult:
    """Result of rendering a config template."""

    rendered: dict[str, Any]
    substitutions: int = 0
    missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.missing) == 0

    def __repr__(self) -> str:
        return (
            f"RenderResult(substitutions={self.substitutions}, "
            f"missing={self.missing}, ok={self.ok})"
        )


class ConfigTemplate:
    """Renders service config dicts by substituting {{ var }} placeholders."""

    def __init__(self, variables: dict[str, str] | None = None) -> None:
        self._vars: dict[str, str] = dict(variables or {})

    def set(self, key: str, value: str) -> None:
        """Add or update a template variable."""
        self._vars[key] = value

    def update(self, mapping: dict[str, str]) -> None:
        """Bulk-update template variables."""
        self._vars.update(mapping)

    def render(self, config: dict[str, Any]) -> RenderResult:
        """Recursively substitute placeholders in *config* and return a RenderResult."""
        missing: list[str] = []
        count = [0]

        def _sub(value: Any) -> Any:
            if isinstance(value, str):
                def replacer(m: re.Match) -> str:
                    key = m.group(1)
                    if key in self._vars:
                        count[0] += 1
                        return self._vars[key]
                    missing.append(key)
                    return m.group(0)  # leave placeholder intact
                return _VAR_RE.sub(replacer, value)
            if isinstance(value, dict):
                return {k: _sub(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_sub(item) for item in value]
            return value

        rendered = _sub(config)
        return RenderResult(rendered=rendered, substitutions=count[0], missing=list(dict.fromkeys(missing)))

    def render_json(self, raw: str) -> RenderResult:
        """Parse *raw* JSON, render it, and return a RenderResult."""
        try:
            config = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TemplateError(f"Invalid JSON: {exc}") from exc
        if not isinstance(config, dict):
            raise TemplateError("Top-level JSON value must be an object")
        return self.render(config)
