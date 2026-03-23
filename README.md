<p align="center">
  <h1 align="center">agentend</h1>
  <p align="center"><strong>The framework where the agent IS the backend.</strong></p>
  <p align="center">No routes. No controllers. No endpoint versioning.<br/>A user sends an intent, and the agent figures out the rest.</p>
</p>

<p align="center">
  <a href="https://pypi.org/project/agentend/"><img src="https://img.shields.io/pypi/v/agentend?color=blue" alt="PyPI" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL%203.0-blue.svg" alt="License" /></a>
</p>

---

## What is this?

A traditional backend maps `GET /api/invoices/123` to a handler. Agentend receives `"extract data from this invoice"` and independently decides which models to call, what data to retrieve, and how to format the response.

You define **Capabilities** (what the agent can do), configure a **Fleet** (which models handle what), and agentend handles intent routing, memory, streaming, tool calling, and multi-step workflows.

```python
from agentend import Agentend, Capability, tool

app = Agentend()

@app.capability("invoice_processing")
class InvoiceProcessor(Capability):
    """Extract and verify invoice data."""

    workers = ["extract", "verify", "summarize"]

    def get_domain_context(self, ctx):
        return "You are processing business invoices. Be precise with amounts."

    @tool
    def save_invoice(self, data: dict) -> str:
        """Save extracted invoice to database."""
        # Your persistence logic here
        return f"Invoice saved: {data.get('invoice_id')}"

if __name__ == "__main__":
    app.serve()
```

That's it. No routes to write. The agent classifies the intent, picks the right workers, hydrates context from memory, and streams AG-UI events to the frontend.

---

## Install

```bash
pip install agentend
```

With optional backends:

```bash
pip install agentend[llm]          # LiteLLM + Instructor (model calls)
pip install agentend[memory]       # Redis + Mem0 (session + long-term memory)
pip install agentend[db]           # PostgreSQL + pgvector (persistence + vectors)
pip install agentend[all]          # Everything
```

## Quickstart

```bash
# Scaffold a new project
agentend init myapp
cd myapp

# Start the server
agentend serve
# → http://localhost:8000
# → POST /intent to send intents
# → GET /stream/{session_id} for AG-UI event streaming
# → GET /health for health check
```

Or with Docker:

```bash
docker compose up   # agentend + PostgreSQL + Redis + Ollama
```

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                 Agentic Frontend  (Next.js + assistant-ui)                 │
│   Chat Stream  ·  Data Cards  ·  Workflow Progress  ·  Memory UI           │
└─────────────────────────┬──────────────────────────────────────────────────┘
                          │  AG-UI Events (SSE)
┌─────────────────────────┴──────────────────────────────────────────────────┐
│                          Agent Kernel  (agentend)                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Intent Router  (kernel.classify  ->  Capability dispatch)           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │classify │ │ extract │ │ verify  │ │summarize│ │ generate│ │tool_call│   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│  ┌── Model Fleet  (LiteLLM + RouteLLM) ─────────────────────────────────┐  │
│  │  100+ providers  ·  cost routing: RouteLLM  ·  benchmark defaults    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│  ┌── Context Bus  (5-tier memory) ──────────────────────────────────────┐  │
│  │  Working: in-memory  ·  Session: Redis  ·  Semantic: pgvector + Mem0 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

### How a request flows

1. Frontend sends intent via `POST /intent`
2. **Auth** verifies JWT, checks RBAC permissions, enforces rate limits
3. **Security** sanitizes input (PALADIN injection defense)
4. **Router** classifies intent using a small model (~360M params, <10ms)
5. **Context Bus** hydrates memory progressively (load only what's needed)
6. **Workers** execute with the right model for each task
7. **AG-UI events** stream back: text chunks, tool calls, data cards, progress
8. **Post-request**: Mem0 extracts facts (ADD/UPDATE/DELETE/NOOP) asynchronously

---

## Core Concepts

### Capabilities (replace controllers)

A Capability defines what the agent can do. Each one declares which workers it needs and how to prompt them.

```python
@app.capability("legal_review")
class LegalReviewer(Capability):
    workers = ["extract", "verify", "generate"]

    def get_persona(self):
        return "You are a senior legal analyst."

    def get_constraints(self):
        return "Flag non-standard indemnification clauses."

    @tool
    def lookup_precedent(self, term: str) -> str:
        """Search legal database for precedent."""
        return legal_db.search(term)
```

### Fleet Configuration (replace infrastructure code)

One YAML file controls which model handles what. Swap models without touching code.

```yaml
fleet:
  classify:
    model: "HuggingFaceTB/SmolLM2-360M"
    backend: local
  extract:
    model: "numind/NuExtract-tiny-v1.5"
    backend: ollama
  generate:
    model: "anthropic/claude-sonnet-4-20250514"
    fallback: "ollama/qwen2.5:14b"        # auto-fallback to local
    routing: cost_optimized                 # RouteLLM picks cheap vs expensive

memory:
  session_backend: redis
  consolidation:
    engine: mem0                            # ADD/UPDATE/DELETE/NOOP

mcp:
  servers:
    github:
      command: "npx"
      args: ["-y", "@modelcontextprotocol/server-github"]
```

### 3-Level Override

```python
# Global default ← fleet.yaml
# Per-slot override:
app.configure(generate=WorkerConfig(model="gpt-4o"))
# Per-request override (highest priority):
with app.context(generate_model="claude-opus-4-20250514"):
    result = await app.process_intent("Analyze this contract")
```

### 5-Tier Memory (the hard part, solved)

| Tier | Backend | Latency | What it stores |
|------|---------|---------|---------------|
| Working | Python dict | <1ms | Current request context |
| Session | Redis | 1-5ms | Conversation history |
| Semantic | pgvector | 5-50ms | Long-term facts, preferences |
| Core Blocks | System prompt | 0ms | Agent identity, pinned knowledge |
| Consolidation | Mem0 | async | Incremental fact extraction (ADD/UPDATE/DELETE/NOOP) |

The Context Bus loads progressively — simple requests use minimal tokens, complex ones pull more context on demand.

### Protocol Triangle

| Protocol | Direction | Purpose |
|----------|-----------|---------|
| **AG-UI** | Agent → User | Stream events to frontend (SSE) |
| **MCP** | Agent → Tools | Connect to any MCP server via config |
| **A2A** | Agent → Agent | Delegate tasks to peer agents |

---

## What's Included

| Module | What it does |
|--------|-------------|
| `kernel/` | Intent routing, capability dispatch, request lifecycle |
| `fleet/` | 6 typed workers, LiteLLM backend, RouteLLM cost routing |
| `memory/` | 5-tier context bus, Mem0 consolidation, progressive hydration |
| `events/` | AG-UI protocol, 13 event types, SSE + WebSocket |
| `orchestrator/` | Multi-step workflows, DAG execution, HITL interrupts |
| `protocols/` | MCP aggregation, MCP server mode, A2A agent cards |
| `prompts/` | Template Method slots, middleware chain, priority truncation |
| `auth/` | JWT, API keys, per-capability RBAC |
| `security/` | PALADIN 3-layer injection defense |
| `cache/` | Dual-layer semantic cache (exact hash + vector similarity) |
| `guardrails/` | Input/output moderation, tool call validation |
| `budgets/` | Per-tenant/user token budgets and rate limiting |
| `ingest/` | Document pipeline: acquire → transform → classify → chunk+embed |
| `plugins/` | 8 hook points, YAML manifests, pip-installable |
| `persistence/` | 15 SQLAlchemy models, multi-tenant RLS |
| `observability/` | OpenTelemetry traces + metrics |
| `connectors/` | 17 infra connectors: SQL, cache, logging, queues |
| `builder/` | Chat-to-build capability generator with 7 templates |
| `fleet/benchmarks` | March 2026 model recommendations per worker slot |

---

## CLI

```bash
agentend init myapp     # Scaffold project (app.py, fleet.yaml, Dockerfile)
agentend serve          # Start server (--host, --port, --reload)
agentend fleet          # Show current fleet configuration
agentend memory         # Show memory status
agentend version        # Show version
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/intent` | Send a natural language intent |
| GET | `/stream/{session_id}` | SSE event stream (AG-UI) |
| POST | `/runs` | Submit async workflow (fire-and-forget) |
| GET | `/runs/{run_id}` | Poll async run status |
| GET | `/health` | Health check |
| GET | `/ready` | Readiness (checks PG, Redis, Ollama) |
| GET | `/.well-known/agent.json` | A2A Agent Card |

### Benchmark-Backed Model Defaults

Every worker slot comes with a recommended model backed by March 2026 benchmark data. No manual model research needed.

```python
from agentend.fleet.benchmarks import registry

# See what's recommended for each slot
for slot in registry.list_slots():
    rec = registry.get_recommendation(slot)
    print(f"{slot}: {rec.primary.model_id} (budget: {rec.budget_pick.model_id})")

# Auto-configure your fleet.yaml with the best models
fleet_config = registry.apply_to_fleet_config(my_config, strategy="budget")
```

| Slot | Primary (Best) | Budget (Cheapest) | Local (Self-hosted) |
|------|---------------|-------------------|---------------------|
| classify | claude-haiku-4-5 | gemini-2.0-flash | qwen2.5-7b |
| extract | claude-sonnet-4-6 | gemini-2.5-flash | qwen2.5-72b |
| verify | claude-opus-4-6 | gemini-2.5-flash | llama-4-maverick |
| generate | claude-opus-4-6 | gemini-2.5-flash | qwen2.5-coder-32b |
| tool_call | claude-sonnet-4-6 | gemini-2.5-flash | llama-4-maverick |

### Build Capabilities by Chatting

Don't want to write Python? Describe what you need in plain English.

```python
from agentend import CapabilityBuilder

builder = CapabilityBuilder()
session = builder.new_session()

# Describe what you want
response = await builder.process_message(session.session_id,
    "I need a capability that classifies customer support tickets "
    "by urgency (critical/high/medium/low) and department (billing/technical/general)")

# The builder asks clarifying questions, you respond...
# When ready, generate deployable code:
code = builder.generate_code(session.session_id)

# Or deploy it live to a running instance:
await builder.deploy(session.session_id, app)
```

7 pre-built templates included: `ticket_classifier`, `data_extractor`, `content_generator`, `summarizer`, `sentiment_analyzer`, `qa_bot`, `workflow_router`.

### Infrastructure Connectors

Plug into your existing stack with zero config changes. 17 connector types, zero-dependency defaults.

```python
from agentend.connectors import ConnectorConfig, registry

# Configure your infrastructure
db = registry.create(ConnectorConfig(
    name="main_db", connector_type="postgresql",
    connection_string="postgresql://localhost/myapp"
))

cache = registry.create(ConnectorConfig(
    name="app_cache", connector_type="memory_cache"  # zero deps, works instantly
))

async with db:
    rows = await db.query("SELECT * FROM users WHERE active = true")
```

Supported: PostgreSQL, MySQL, SQLite, Redis, in-memory cache, file logging, stdout logging, in-memory queue — plus stubs for Datadog, Elasticsearch, RabbitMQ, and Kafka.

---

## The Django Analogy

| Django | Agentend |
|--------|----------|
| URL routes | Intent classification |
| Views | Capabilities |
| Models (ORM) | Persistence schema |
| Template system | Prompt slots |
| Middleware | Context bus + prompt middleware |
| `manage.py runserver` | `agentend serve` |
| `manage.py startapp` | `agentend init` |
| `settings.py` | `fleet.yaml` |

---

## Development

```bash
git clone https://github.com/agentend/agentend.git
cd agentend
pip install -e ".[dev]"
pytest tests/
```
