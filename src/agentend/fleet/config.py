"""
Fleet configuration management.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import os
import logging

logger = logging.getLogger(__name__)


@dataclass
class FleetConfig:
    """
    Configuration for the worker fleet.

    Loads from YAML, resolves worker configs with override chains,
    and supports environment variable substitution.
    """

    workers: Dict[str, Any] = field(default_factory=dict)
    """Worker configurations by slot name."""

    global_model: Optional[str] = None
    """Global default model for all workers."""

    global_temperature: float = 0.7
    """Global default temperature."""

    global_max_tokens: Optional[int] = None
    """Global default max tokens."""

    global_backend: str = "litellm"
    """Global default backend."""

    extra_params: Dict[str, Any] = field(default_factory=dict)
    """Extra parameters to apply to all workers."""

    @classmethod
    def from_yaml(cls, path: str) -> "FleetConfig":
        """
        Load fleet configuration from YAML file.

        Supports environment variable substitution in format ${VAR_NAME}.

        Args:
            path: Path to YAML file.

        Returns:
            FleetConfig instance.

        Raises:
            FileNotFoundError: If config file doesn't exist.
            ValueError: If YAML is invalid.
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required for YAML config loading")

        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "r") as f:
            content = f.read()

        # Substitute environment variables
        content = cls._substitute_env_vars(content)

        try:
            config_dict = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {path}: {e}")

        if not isinstance(config_dict, dict):
            raise ValueError(f"Config must be a YAML object, got {type(config_dict)}")

        return cls(**config_dict)

    @staticmethod
    def _substitute_env_vars(content: str) -> str:
        """
        Substitute environment variables in ${VAR_NAME} format.

        Args:
            content: Content with variable placeholders.

        Returns:
            Content with variables substituted.
        """
        import re

        def replace_var(match: Any) -> str:
            var_name = match.group(1)
            value = os.getenv(var_name)
            if value is None:
                logger.warning(f"Environment variable not found: {var_name}")
                return match.group(0)
            return value

        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace_var, content)

    def get_worker_config(
        self, slot_name: str, overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get resolved configuration for a worker slot.

        Applies 3-level override resolution:
        1. Global defaults
        2. Per-slot config (from YAML)
        3. Per-request overrides

        Args:
            slot_name: Name of the worker slot.
            overrides: Optional per-request overrides.

        Returns:
            Resolved worker configuration dict.
        """
        # Start with global defaults
        resolved = {
            "model": self.global_model or "gpt-4",
            "temperature": self.global_temperature,
            "max_tokens": self.global_max_tokens,
            "backend": self.global_backend,
        }
        resolved.update(self.extra_params)

        # Apply per-slot config
        if slot_name in self.workers:
            slot_config = self.workers[slot_name]
            if isinstance(slot_config, dict):
                resolved.update(slot_config)

        # Apply per-request overrides
        if overrides:
            resolved.update({k: v for k, v in overrides.items() if v is not None})

        return resolved

    def list_workers(self) -> list[str]:
        """
        List all configured worker slots.

        Returns:
            List of slot names.
        """
        return list(self.workers.keys())
