"""SQLAlchemy 2.0 async models for agentend."""

from datetime import datetime
from typing import Optional
import uuid

try:
    from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, Index
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import Mapped, mapped_column, relationship
except ImportError:
    # Create stub objects if SQLAlchemy is not installed
    String = None
    Integer = None
    Float = None
    Boolean = None
    DateTime = None
    Text = None
    JSON = None
    ForeignKey = None
    Index = None
    Mapped = None
    mapped_column = None
    relationship = None
    declarative_base = None


_HAS_SQLALCHEMY = declarative_base is not None

if _HAS_SQLALCHEMY:
    Base = declarative_base()
else:
    # Stub Base so class definitions parse without SQLAlchemy installed.
    # The classes won't be functional, but the module can be imported.
    class _StubMeta(type):
        def __new__(mcs, name, bases, namespace, **kwargs):
            return super().__new__(mcs, name, bases, namespace)
    class Base(metaclass=_StubMeta):  # type: ignore
        __tablename__ = ""
        __table_args__: tuple = ()

    # Stub decorators / types
    def mapped_column(*a, **kw): return None  # type: ignore
    def relationship(*a, **kw): return None  # type: ignore
    class Mapped:  # type: ignore
        def __class_getitem__(cls, item): return cls
    String = Integer = Float = Boolean = DateTime = Text = JSON = str  # type: ignore
    def ForeignKey(*a, **kw): return None  # type: ignore
    def Index(*a, **kw): return None  # type: ignore


class Tenant(Base):
    """Tenant model."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    plan: Mapped[str] = mapped_column(String(50), default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("idx_tenants_name", "name"),
        Index("idx_tenants_is_active", "is_active"),
    )


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    full_name: Mapped[str] = mapped_column(String(255))
    roles: Mapped[list] = mapped_column(JSON, default=["user"])
    capabilities: Mapped[list] = mapped_column(JSON, default=["execute"])
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("idx_users_tenant_id", "tenant_id"),
        Index("idx_users_email", "email"),
    )


class Agent(Base):
    """Agent/Capability configuration."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    system_prompt: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100))
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    tools: Mapped[list] = mapped_column(JSON, default=[])
    extra_data: Mapped[dict] = mapped_column("metadata", JSON, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("idx_agents_tenant_id", "tenant_id"),
        Index("idx_agents_name", "name"),
    )


class WorkerConfig(Base):
    """Worker configuration."""

    __tablename__ = "worker_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    name: Mapped[str] = mapped_column(String(255))
    worker_type: Mapped[str] = mapped_column(String(50))
    capabilities: Mapped[list] = mapped_column(JSON, default=[])
    instances: Mapped[int] = mapped_column(Integer, default=1)
    memory_mb: Mapped[int] = mapped_column(Integer, default=512)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    skip_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_data: Mapped[dict] = mapped_column("metadata", JSON, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_worker_configs_tenant_id", "tenant_id"),
        Index("idx_worker_configs_name", "name"),
    )


class Session(Base):
    """User session."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    capability: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (
        Index("idx_sessions_tenant_id_user_id", "tenant_id", "user_id"),
        Index("idx_sessions_status", "status"),
    )


class Message(Base):
    """Message in conversation."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"))
    role: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_messages_session_id", "session_id"),
        Index("idx_messages_tenant_id", "tenant_id"),
    )


class Run(Base):
    """Async run/task execution."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    workflow: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="submitted")
    input_params: Mapped[dict] = mapped_column(JSON, default={})
    output_result: Mapped[Optional[dict]] = mapped_column(JSON)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    __table_args__ = (
        Index("idx_runs_tenant_id_user_id", "tenant_id", "user_id"),
        Index("idx_runs_status", "status"),
        Index("idx_runs_created_at", "created_at"),
    )


class Step(Base):
    """Execution step within a run."""

    __tablename__ = "steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"))
    step_number: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50))
    input_data: Mapped[dict] = mapped_column(JSON)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_steps_run_id", "run_id"),
        Index("idx_steps_tenant_id", "tenant_id"),
    )


class ToolCall(Base):
    """Tool invocation record."""

    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"))
    tool_name: Mapped[str] = mapped_column(String(255))
    arguments: Mapped[dict] = mapped_column(JSON)
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_tool_calls_run_id", "run_id"),
        Index("idx_tool_calls_tenant_id", "tenant_id"),
    )


class MemoryBlock(Base):
    """Memory block (facts, context, etc)."""

    __tablename__ = "memory_blocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    session_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sessions.id"))
    block_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[list]] = mapped_column(JSON)
    extra_data: Mapped[dict] = mapped_column("metadata", JSON, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    accessed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_memory_blocks_tenant_id", "tenant_id"),
        Index("idx_memory_blocks_session_id", "session_id"),
        Index("idx_memory_blocks_block_type", "block_type"),
    )


class MemoryFact(Base):
    """Individual fact in memory."""

    __tablename__ = "memory_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    memory_block_id: Mapped[str] = mapped_column(String(36), ForeignKey("memory_blocks.id"))
    fact: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_memory_facts_tenant_id", "tenant_id"),
        Index("idx_memory_facts_block_id", "memory_block_id"),
    )


class MemoryGraphEdge(Base):
    """Edge in memory graph."""

    __tablename__ = "memory_graph_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    from_block_id: Mapped[str] = mapped_column(String(36), ForeignKey("memory_blocks.id"))
    to_block_id: Mapped[str] = mapped_column(String(36), ForeignKey("memory_blocks.id"))
    relationship_type: Mapped[str] = mapped_column(String(100))
    weight: Mapped[float] = mapped_column(Float, default=1.0)

    __table_args__ = (
        Index("idx_edges_tenant_id", "tenant_id"),
        Index("idx_edges_from_to", "from_block_id", "to_block_id"),
    )


class Checkpoint(Base):
    """Execution checkpoint for resumption."""

    __tablename__ = "checkpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"))
    checkpoint_number: Mapped[int] = mapped_column(Integer)
    state: Mapped[dict] = mapped_column(JSON)
    memory_state: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_checkpoints_run_id", "run_id"),
        Index("idx_checkpoints_tenant_id", "tenant_id"),
    )


class Metric(Base):
    """Performance metric."""

    __tablename__ = "metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    metric_type: Mapped[str] = mapped_column(String(100))
    metric_name: Mapped[str] = mapped_column(String(255))
    value: Mapped[float] = mapped_column(Float)
    labels: Mapped[dict] = mapped_column(JSON, default={})
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_metrics_tenant_id", "tenant_id"),
        Index("idx_metrics_type_name", "metric_type", "metric_name"),
        Index("idx_metrics_recorded_at", "recorded_at"),
    )


class Evaluation(Base):
    """Evaluation result."""

    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("runs.id"))
    evaluation_type: Mapped[str] = mapped_column(String(100))
    score: Mapped[float] = mapped_column(Float)
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    extra_data: Mapped[dict] = mapped_column("metadata", JSON, default={})
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_evaluations_run_id", "run_id"),
        Index("idx_evaluations_tenant_id", "tenant_id"),
    )
