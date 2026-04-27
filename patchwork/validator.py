"""Config validation for service definitions before diffing or deploying."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ValidationError:
    field: str
    message: str

    def __repr__(self) -> str:
        return f"ValidationError(field={self.field!r}, message={self.message!r})"


@dataclass
class ValidationResult:
    errors: List[ValidationError] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, field: str, message: str) -> None:
        self.errors.append(ValidationError(field=field, message=message))

    def summary(self) -> str:
        if self.valid:
            return "Config is valid."
        lines = [f"  - [{e.field}] {e.message}" for e in self.errors]
        return "Validation failed:\n" + "\n".join(lines)


def validate_config(config: dict) -> ValidationResult:
    """Validate a raw service config dictionary."""
    result = ValidationResult()

    name = config.get("name")
    if not name or not isinstance(name, str):
        result.add_error("name", "Service name must be a non-empty string.")
    elif not name.replace("-", "").replace("_", "").isalnum():
        result.add_error("name", "Service name must be alphanumeric (hyphens/underscores allowed).")

    image = config.get("image")
    if not image or not isinstance(image, str):
        result.add_error("image", "Image must be a non-empty string.")
    elif ":" not in image:
        result.add_error("image", "Image should include a tag (e.g. 'nginx:latest').")

    replicas = config.get("replicas")
    if replicas is None:
        result.add_error("replicas", "Replicas field is required.")
    elif not isinstance(replicas, int) or replicas < 1:
        result.add_error("replicas", "Replicas must be a positive integer.")
    elif replicas > 100:
        result.add_error("replicas", "Replicas must not exceed 100.")

    env = config.get("env", {})
    if not isinstance(env, dict):
        result.add_error("env", "Env must be a key-value mapping.")
    else:
        for k, v in env.items():
            if not isinstance(k, str) or not k:
                result.add_error("env", f"Env key {k!r} must be a non-empty string.")
            if not isinstance(v, str):
                result.add_error("env", f"Env value for {k!r} must be a string.")

    return result
