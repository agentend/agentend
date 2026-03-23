"""Tests for built-in system capabilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from agentend.kernel.kernel import RequestContext
from agentend.config import Config, FleetConfig, WorkerSlotConfig
from agentend.capabilities import SYSTEM_CAPABILITIES
from agentend.capabilities.fleet_status import FleetStatusCapability
from agentend.capabilities.system_health import SystemHealthCapability
from agentend.capabilities.memory_inspect import MemoryInspectCapability
from agentend.capabilities.metrics_usage import MetricsUsageCapability
from agentend.capabilities.sessions_list import SessionsListCapability
from agentend.capabilities.workflow_status import WorkflowStatusCapability
from agentend.kernel.registry import CapabilityRegistry


def _make_context(**overrides):
    """Create a RequestContext with sensible defaults."""
    defaults = {
        "user_id": "user-1",
        "session_id": "session-1",
        "messages": [],
        "metadata": {},
        "memory_refs": [],
        "tenant_id": "tenant-1",
    }
    defaults.update(overrides)
    return RequestContext(**defaults)


class TestSystemCapabilitiesRegistry:
    """Test that SYSTEM_CAPABILITIES dict is well-formed."""

    def test_all_six_capabilities_present(self):
        expected = {
            "fleet.status",
            "system.health",
            "memory.inspect",
            "metrics.usage",
            "sessions.list",
            "workflow.status",
        }
        assert set(SYSTEM_CAPABILITIES.keys()) == expected

    def test_capabilities_have_name_and_description(self):
        for name, cap in SYSTEM_CAPABILITIES.items():
            assert cap.name == name
            assert isinstance(cap.description, str)
            assert len(cap.description) > 0

    def test_capabilities_register_in_registry(self):
        registry = CapabilityRegistry()
        for cap_name, cap_instance in SYSTEM_CAPABILITIES.items():
            registry.register(cap_name, cap_instance)

        for cap_name in SYSTEM_CAPABILITIES:
            assert registry.lookup(cap_name) is not None

    def test_duplicate_registration_raises(self):
        registry = CapabilityRegistry()
        cap = SYSTEM_CAPABILITIES["fleet.status"]
        registry.register("fleet.status", cap)
        with pytest.raises(ValueError, match="already registered"):
            registry.register("fleet.status", cap)

    def test_list_capabilities_includes_system(self):
        registry = CapabilityRegistry()
        for cap_name, cap_instance in SYSTEM_CAPABILITIES.items():
            registry.register(cap_name, cap_instance)

        listed = registry.list_capabilities()
        listed_names = {c["name"] for c in listed}
        assert "fleet.status" in listed_names
        assert "system.health" in listed_names


class TestFleetStatus:
    """Tests for fleet.status capability."""

    @pytest.mark.asyncio
    async def test_returns_slot_configs(self):
        config = Config()
        config.fleet.classify.model = "test-model"
        config.fleet.classify.backend = "litellm"
        config.fleet.generate.model = "openai/gpt-4o"
        config.fleet.generate.fallback = "ollama/qwen2.5:7b"

        ctx = _make_context(metadata={"app_config": config})
        cap = FleetStatusCapability()
        result = await cap.execute(ctx)

        assert result["capability"] == "fleet.status"
        assert "slots" in result
        assert result["slots"]["classify"]["model"] == "test-model"
        assert result["slots"]["generate"]["model"] == "openai/gpt-4o"
        assert result["slots"]["generate"]["fallback"] == "ollama/qwen2.5:7b"

    @pytest.mark.asyncio
    async def test_all_six_slots_present(self):
        config = Config()
        ctx = _make_context(metadata={"app_config": config})
        cap = FleetStatusCapability()
        result = await cap.execute(ctx)

        expected_slots = {"classify", "extract", "verify", "summarize", "generate", "tool_call"}
        assert set(result["slots"].keys()) == expected_slots

    @pytest.mark.asyncio
    async def test_missing_config_returns_error(self):
        ctx = _make_context(metadata={})
        cap = FleetStatusCapability()
        result = await cap.execute(ctx)

        assert "error" in result
        assert result["slots"] == {}


class TestSystemHealth:
    """Tests for system.health capability."""

    @pytest.mark.asyncio
    async def test_all_services_unavailable(self):
        ctx = _make_context(metadata={})
        cap = SystemHealthCapability()
        result = await cap.execute(ctx)

        assert result["capability"] == "system.health"
        assert "services" in result
        assert result["services"]["postgresql"]["status"] == "unavailable"
        assert result["services"]["redis"]["status"] == "unavailable"
        # Ollama will be unavailable since there is no local instance
        assert result["services"]["ollama"]["status"] in ("unavailable", "error")

    @pytest.mark.asyncio
    async def test_redis_ok(self):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        ctx = _make_context(metadata={"redis": mock_redis})
        cap = SystemHealthCapability()
        result = await cap.execute(ctx)

        assert result["services"]["redis"]["status"] == "ok"

    @pytest.mark.asyncio
    async def test_redis_error(self):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=ConnectionError("refused"))

        ctx = _make_context(metadata={"redis": mock_redis})
        cap = SystemHealthCapability()
        result = await cap.execute(ctx)

        assert result["services"]["redis"]["status"] == "error"
        assert "refused" in result["services"]["redis"]["detail"]

    @pytest.mark.asyncio
    async def test_postgresql_ok(self):
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_engine = AsyncMock()
        mock_engine.begin = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))

        ctx = _make_context(metadata={"engine": mock_engine})
        cap = SystemHealthCapability()
        result = await cap.execute(ctx)

        assert result["services"]["postgresql"]["status"] == "ok"


class TestMemoryInspect:
    """Tests for memory.inspect capability."""

    @pytest.mark.asyncio
    async def test_no_context_bus(self):
        ctx = _make_context(metadata={})
        cap = MemoryInspectCapability()
        result = await cap.execute(ctx)

        assert result["capability"] == "memory.inspect"
        assert result["session_id"] == "session-1"
        assert result["tiers"]["working"]["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_with_working_memory(self):
        from agentend.memory.working import WorkingMemory

        working = WorkingMemory()
        working.set("session-1:user:msg1", {"role": "user", "content": "hello"})

        mock_bus = MagicMock()
        mock_bus.working_memory = working
        mock_bus.session_memory = None
        mock_bus.semantic_memory = None
        mock_bus.consolidation_engine = None

        ctx = _make_context(metadata={"context_bus": mock_bus})
        cap = MemoryInspectCapability()
        result = await cap.execute(ctx)

        assert result["tiers"]["working"]["total_keys"] == 1
        assert result["tiers"]["working"]["session_keys"] == 1
        assert result["tiers"]["session"]["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_with_session_memory(self):
        from agentend.memory.working import WorkingMemory

        mock_session_mem = AsyncMock()
        mock_session_mem.get_history = AsyncMock(return_value=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ])
        mock_session_mem.get_metadata = AsyncMock(return_value={"lang": "en"})

        mock_bus = MagicMock()
        mock_bus.working_memory = WorkingMemory()
        mock_bus.session_memory = mock_session_mem
        mock_bus.semantic_memory = None
        mock_bus.consolidation_engine = None

        ctx = _make_context(metadata={"context_bus": mock_bus})
        cap = MemoryInspectCapability()
        result = await cap.execute(ctx)

        assert result["tiers"]["session"]["message_count"] == 2
        assert result["tiers"]["session"]["metadata"] == {"lang": "en"}


class TestMetricsUsage:
    """Tests for metrics.usage capability."""

    @pytest.mark.asyncio
    async def test_no_metrics_collector(self):
        ctx = _make_context(metadata={})
        cap = MetricsUsageCapability()
        result = await cap.execute(ctx)

        assert result["capability"] == "metrics.usage"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_with_metrics(self):
        from agentend.observability.metrics import MetricsCollector

        collector = MetricsCollector()
        collector.track_worker_call(
            worker_id="gen-1",
            capability="generate",
            tokens_in=100,
            tokens_out=200,
            cost=0.005,
            latency_ms=350.0,
        )
        collector.track_tenant_usage("tenant-1", tokens=300, cost=0.005)

        ctx = _make_context(metadata={"metrics": collector})
        cap = MetricsUsageCapability()
        result = await cap.execute(ctx)

        assert result["capability"] == "metrics.usage"
        assert "gen-1" in result["workers"]
        assert result["workers"]["gen-1"]["tokens_in"] == 100
        assert result["workers"]["gen-1"]["tokens_out"] == 200
        assert result["capabilities"]["generate"]["call_count"] == 1
        assert result["current_tenant"]["tokens"] == 300


class TestSessionsList:
    """Tests for sessions.list capability."""

    @pytest.mark.asyncio
    async def test_no_database(self):
        ctx = _make_context(metadata={})
        cap = SessionsListCapability()
        result = await cap.execute(ctx)

        assert result["capability"] == "sessions.list"
        assert "error" in result
        assert result["sessions"] == []

    @pytest.mark.asyncio
    async def test_no_tenant_id(self):
        ctx = _make_context(tenant_id=None, metadata={"session_factory": MagicMock()})
        cap = SessionsListCapability()
        result = await cap.execute(ctx)

        assert "error" in result
        assert "tenant_id" in result["error"]


class TestWorkflowStatus:
    """Tests for workflow.status capability."""

    @pytest.mark.asyncio
    async def test_no_database(self):
        ctx = _make_context(metadata={})
        cap = WorkflowStatusCapability()
        result = await cap.execute(ctx)

        assert result["capability"] == "workflow.status"
        assert "error" in result
        assert result["runs"] == []

    @pytest.mark.asyncio
    async def test_no_tenant_id(self):
        ctx = _make_context(tenant_id=None, metadata={"session_factory": MagicMock()})
        cap = WorkflowStatusCapability()
        result = await cap.execute(ctx)

        assert "error" in result
        assert "tenant_id" in result["error"]
