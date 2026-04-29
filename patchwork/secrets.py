"""Secrets masking utilities for patchwork-deploy.

Provides helpers to detect and redact sensitive values (passwords, tokens,
keys) from config dicts and command strings before they appear in logs or
reports.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Patterns whose *keys* indicate a secret value.
_SECRET_KEY_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|private[_-]?key|auth)",
    re.IGNORECASE,
)

_MASK = "***"


@dataclass
class MaskingResult:
    """Holds the masked output and a count of values that were redacted."""

    value: Any
    redacted_count: int = 0

    def __repr__(self) -> str:  # pragma: no cover
        return f"MaskingResult(redacted={self.redacted_count})"


class SecretMasker:
    """Masks secret values found in dicts, lists, and strings."""

    def __init__(self, extra_patterns: list[str] | None = None) -> None:
        patterns = [_SECRET_KEY_RE.pattern]
        if extra_patterns:
            patterns.extend(extra_patterns)
        combined = "|".join(f"({p})" for p in patterns)
        self._key_re = re.compile(combined, re.IGNORECASE)
        self._redacted: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mask_dict(self, data: dict[str, Any]) -> MaskingResult:
        """Return a new dict with secret values replaced by the mask."""
        self._redacted = 0
        masked = self._mask_value(data)
        return MaskingResult(value=masked, redacted_count=self._redacted)

    def mask_string(self, text: str) -> MaskingResult:
        """Redact inline KEY=VALUE patterns where the key looks secret."""
        self._redacted = 0
        result = re.sub(
            r"(?i)((?:" + _SECRET_KEY_RE.pattern + r")[\w]*\s*=\s*)([^\s&;|]+)",
            self._replace_inline,
            text,
        )
        return MaskingResult(value=result, redacted_count=self._redacted)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _replace_inline(self, m: re.Match) -> str:  # type: ignore[type-arg]
        self._redacted += 1
        return m.group(1) + _MASK

    def _mask_value(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: (self._redact(v) if self._key_re.search(str(k)) else self._mask_value(v))
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [self._mask_value(item) for item in obj]
        return obj

    def _redact(self, value: Any) -> str:
        self._redacted += 1
        return _MASK
