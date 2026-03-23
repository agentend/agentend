"""Agentend configuration loader.

Loads fleet.yaml and provides typed access to all configuration sections.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class WorkerSlotConfig:
    """Configuration for a single worker slot."""
    model: str = ""
    backend: str = "litellm"
    fallback: Optional[str] = None
    routing: Optional[str] = None
    routing_threshold: float = 0.7
    temperature: float = 0.0
    max_tokens: int = 4096


@dataclass
class FleetConfig:
    """Fleet-level configuration."""
    classify: WorkerSlotConfig = field(default_factory=WorkerSlotConfig)
    extract: WorkerSlotConfig = field(default_factory=WorkerSlotConfig)
    verify: WorkerSlotConfig = field(default_factory=WorkerSlotConfig)
    summarize: WorkerSlotConfig = field(default_factory=WorkerSlotConfig)
    generate: WorkerSlotConfig = field(default_factory=WorkerSlotConfig)
    tool_call: WorkerSlotConfig = field(default_factory=WorkerSlotConfig)


@dataclass
class MemoryConfig:
    """Memory configuration."""
    session_backend: str = "dict"
    session_ttl: int = 3600
    semantic_backend: str = "none"
    redis_url: str = "redis://localhost:6379"
    database_url: str = "sqlite:///agentend.db"


@dataclass
class ServerConfig:
    """Server configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False


@dataclass
class Config:
    """Root configuration for agentend."""
    fleet: FleetConfig = field(default_factory=FleetConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str | Path = "fleet.yaml") -> "Config":
        """Load configuration from a YAML file."""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        config = cls(raw=raw)

        # Parse fleet section
        fleet_raw = raw.get("fleet", {})
        for slot_name in ["classify", "extract", "verify", "summarize", "generate", "tool_call"]:
            if slot_name in fleet_raw:
                slot_data = fleet_raw[slot_name]
                slot_config = WorkerSlotConfig(
                    model=slot_data.get("model", ""),
                    backend=slot_data.get("backend", "litellm"),
                    fallback=slot_data.get("fallback"),
                    routing=slot_data.get("routing"),
                    routing_threshold=slot_data.get("routing_threshold", 0.7),
                    temperature=slot_data.get("temperature", 0.0),
                    max_tokens=slot_data.get("max_tokens", 4096),
                )
                setattr(config.fleet, slot_name, slot_config)

        # Parse memory section
        mem_raw = raw.get("memory", {})
        config.memory = MemoryConfig(
            session_backend=mem_raw.get("session_backend", "dict"),
            session_ttl=mem_raw.get("session_ttl", 3600),
            semantic_backend=mem_raw.get("semantic_backend", "none"),
            redis_url=mem_raw.get("redis_url", "redis://localhost:6379"),
            database_url=mem_raw.get("database_url", "sqlite:///agentend.db"),
        )

        return config

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        """Load config from path or environment variable or default."""
        if path:
            config = cls.from_yaml(path)
        else:
            env_path = os.environ.get("AGENTEND_CONFIG", "fleet.yaml")
            config = cls.from_yaml(env_path)

        # Environment variables override YAML values
        if db_url := os.environ.get("DATABASE_URL"):
            config.memory.database_url = db_url
        if redis_url := os.environ.get("REDIS_URL"):
            config.memory.redis_url = redis_url

        return config
