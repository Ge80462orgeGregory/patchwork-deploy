"""Load and validate service configs from YAML or dict sources."""

import json
from pathlib import Path
from typing import List, Tuple

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

from patchwork.core import ServiceConfig
from patchwork.validator import validate_config, ValidationResult


class LoadError(Exception):
    """Raised when a config file cannot be loaded or parsed."""


class ConfigLoader:
    """Loads service configs from files and validates them."""

    def load_file(self, path: str) -> dict:
        """Read and parse a YAML or JSON config file."""
        p = Path(path)
        if not p.exists():
            raise LoadError(f"Config file not found: {path}")

        text = p.read_text(encoding="utf-8")
        suffix = p.suffix.lower()

        if suffix in (".yaml", ".yml"):
            if not _YAML_AVAILABLE:
                raise LoadError("PyYAML is required to load .yaml files. Install it with: pip install pyyaml")
            try:
                data = yaml.safe_load(text)
            except yaml.YAMLError as exc:
                raise LoadError(f"Failed to parse YAML: {exc}") from exc
        elif suffix == ".json":
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise LoadError(f"Failed to parse JSON: {exc}") from exc
        else:
            raise LoadError(f"Unsupported file format: {suffix!r}. Use .yaml, .yml, or .json")

        if not isinstance(data, dict):
            raise LoadError("Config file must contain a mapping at the top level.")

        return data

    def validate_and_build(self, raw: dict) -> Tuple[ServiceConfig, ValidationResult]:
        """Validate raw config dict and build a ServiceConfig if valid."""
        result = validate_config(raw)
        if not result.valid:
            return None, result
        config = ServiceConfig.from_dict(raw)
        return config, result

    def load(self, path: str) -> ServiceConfig:
        """Load, validate, and return a ServiceConfig from a file."""
        raw = self.load_file(path)
        config, validation = self.validate_and_build(raw)
        if not validation.valid:
            raise LoadError(f"Invalid config at {path}:\n{validation.summary()}")
        return config
