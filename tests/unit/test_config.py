"""Tests for configuration loading."""
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from agentend.config import Config, FleetConfig, WorkerSlotConfig, MemoryConfig


class TestConfig:
    """Test Config loading and defaults."""

    def test_default_config(self):
        """Config with no YAML file returns defaults."""
        config = Config.from_yaml("nonexistent.yaml")
        assert config.fleet.classify.model == ""
        assert config.fleet.classify.backend == "litellm"
        assert config.memory.session_backend == "dict"
        assert config.server.port == 8000

    def test_load_from_yaml(self, tmp_path):
        """Config loads values from YAML file."""
        yaml_content = {
            "fleet": {
                "classify": {
                    "model": "HuggingFaceTB/SmolLM2-360M",
                    "backend": "local",
                },
                "generate": {
                    "model": "openai/gpt-4o-mini",
                    "fallback": "ollama/qwen2.5:7b",
                    "routing": "cost_optimized",
                    "routing_threshold": 0.8,
                },
            },
            "memory": {
                "session_backend": "redis",
                "session_ttl": 7200,
                "redis_url": "redis://myredis:6379",
            },
        }
        config_file = tmp_path / "fleet.yaml"
        config_file.write_text(yaml.dump(yaml_content))

        config = Config.from_yaml(config_file)

        assert config.fleet.classify.model == "HuggingFaceTB/SmolLM2-360M"
        assert config.fleet.classify.backend == "local"
        assert config.fleet.generate.model == "openai/gpt-4o-mini"
        assert config.fleet.generate.fallback == "ollama/qwen2.5:7b"
        assert config.fleet.generate.routing == "cost_optimized"
        assert config.fleet.generate.routing_threshold == 0.8
        assert config.memory.session_backend == "redis"
        assert config.memory.session_ttl == 7200
        assert config.memory.redis_url == "redis://myredis:6379"

    def test_override_hierarchy(self, tmp_path):
        """Unspecified slots keep defaults while specified ones override."""
        yaml_content = {
            "fleet": {
                "extract": {"model": "my-extract-model"},
            }
        }
        config_file = tmp_path / "fleet.yaml"
        config_file.write_text(yaml.dump(yaml_content))

        config = Config.from_yaml(config_file)

        # extract is overridden
        assert config.fleet.extract.model == "my-extract-model"
        # classify keeps default
        assert config.fleet.classify.model == ""

    def test_load_from_env(self, tmp_path):
        """Config.load() respects AGENTEND_CONFIG env var."""
        yaml_content = {"fleet": {"classify": {"model": "env-model"}}}
        config_file = tmp_path / "custom.yaml"
        config_file.write_text(yaml.dump(yaml_content))

        os.environ["AGENTEND_CONFIG"] = str(config_file)
        try:
            config = Config.load()
            assert config.fleet.classify.model == "env-model"
        finally:
            del os.environ["AGENTEND_CONFIG"]
