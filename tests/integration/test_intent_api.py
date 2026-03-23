"""Integration tests for the /intent API endpoint."""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from agentend.auth.jwt import encode_token
from agentend.server.app import create_app
from agentend.config import Config
from agentend.persistence.models import Base


DB_URL = "postgresql+asyncpg://agentend:agentend@localhost:5432/agentend"
REDIS_URL = "redis://localhost:6379/0"


@pytest.fixture
async def app():
    """Create app with initialized state (lifespan doesn't run in test transport)."""
    cfg = Config.load()
    cfg.memory.database_url = DB_URL
    cfg.memory.redis_url = REDIS_URL

    fastapi_app = create_app(cfg)

    # Manually init what lifespan would do
    engine = create_async_engine(DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    import redis.asyncio as aioredis
    redis_client = await aioredis.from_url(REDIS_URL, encoding="utf8", decode_responses=True)

    fastapi_app.state.config = cfg
    fastapi_app.state.engine = engine
    fastapi_app.state.session_factory = session_factory
    fastapi_app.state.redis = redis_client
    fastapi_app.state.tracer = None
    fastapi_app.state.metrics = None

    yield fastapi_app

    await redis_client.close()
    await engine.dispose()


@pytest.fixture
def token():
    return encode_token(
        user_id="user-1",
        tenant_id="tenant-1",
        roles=["admin"],
        capabilities=["execute", "invoice_processing", "summarize"],
        secret="dev-secret",
    )


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def expired_token():
    return encode_token(
        user_id="user-1",
        tenant_id="tenant-1",
        roles=["admin"],
        capabilities=["execute"],
        secret="dev-secret",
        expires_in_hours=-1,
    )


class TestHealthEndpoints:

    @pytest.mark.asyncio
    async def test_health(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"
            assert resp.json()["version"] == "0.1.0"

    @pytest.mark.asyncio
    async def test_agent_card(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/.well-known/agent.json")
            assert resp.status_code == 200
            data = resp.json()
            assert data["name"] == "agentend"
            assert len(data["capabilities"]) > 0

    @pytest.mark.asyncio
    async def test_readiness_checks_services(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.get("/ready")
            assert resp.status_code == 200
            data = resp.json()
            assert data["checks"]["redis"] is True
            assert data["checks"]["postgresql"] is True


class TestIntentAuth:

    @pytest.mark.asyncio
    async def test_no_auth_rejected(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent", json={
                "capability": "summarize", "input": "test", "stream": False,
            })
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self, app, expired_token):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent",
                headers={"Authorization": f"Bearer {expired_token}", "Content-Type": "application/json"},
                json={"capability": "summarize", "input": "test", "stream": False},
            )
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_wrong_secret_rejected(self, app):
        bad_token = encode_token("u", "t", ["user"], ["execute"], secret="wrong-secret")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent",
                headers={"Authorization": f"Bearer {bad_token}", "Content-Type": "application/json"},
                json={"capability": "summarize", "input": "test", "stream": False},
            )
            assert resp.status_code == 401


class TestIntentValidation:

    @pytest.mark.asyncio
    async def test_empty_input_rejected(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent", headers=auth_headers, json={
                "capability": "summarize", "input": "", "stream": False,
            })
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_capability_rejected(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent", headers=auth_headers, json={
                "input": "test", "stream": False,
            })
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_input_rejected(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent", headers=auth_headers, json={
                "capability": "summarize", "stream": False,
            })
            assert resp.status_code == 422


class TestIntentSuccess:

    @pytest.mark.asyncio
    async def test_stream_returns_session_and_url(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent", headers=auth_headers, json={
                "capability": "invoice_processing",
                "input": "Extract data from invoice 1234, amount 5000",
                "stream": True,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "session_id" in data
            assert data["status"] == "created"
            assert data["stream_url"] is not None
            assert data["session_id"] in data["stream_url"]

    @pytest.mark.asyncio
    async def test_no_stream_returns_session_without_url(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent", headers=auth_headers, json={
                "capability": "summarize",
                "input": "Summarize the benefits of AI",
                "stream": False,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["session_id"]
            assert data["stream_url"] is None

    @pytest.mark.asyncio
    async def test_unique_session_ids(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r1 = await c.post("/intent", headers=auth_headers, json={
                "capability": "summarize", "input": "First", "stream": False,
            })
            r2 = await c.post("/intent", headers=auth_headers, json={
                "capability": "summarize", "input": "Second", "stream": False,
            })
            assert r1.json()["session_id"] != r2.json()["session_id"]

    @pytest.mark.asyncio
    async def test_dollar_amounts_not_blocked(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent", headers=auth_headers, json={
                "capability": "invoice_processing",
                "input": "Invoice total is $5,000 due March 15",
                "stream": False,
            })
            assert resp.status_code == 200


class TestIntentSecurity:

    @pytest.mark.asyncio
    async def test_script_tag_stripped(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent", headers=auth_headers, json={
                "capability": "summarize",
                "input": "<script>alert('xss')</script>Summarize this",
                "stream": False,
            })
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_shell_command_chain_blocked(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent", headers=auth_headers, json={
                "capability": "summarize",
                "input": "; rm -rf /",
                "stream": False,
            })
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_backtick_injection_blocked(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent", headers=auth_headers, json={
                "capability": "summarize",
                "input": "run `whoami` now",
                "stream": False,
            })
            assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_template_injection_stripped(self, app, auth_headers):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            resp = await c.post("/intent", headers=auth_headers, json={
                "capability": "summarize",
                "input": "Hello {{config}} world",
                "stream": False,
            })
            # Template tags are stripped, remaining text is valid
            assert resp.status_code == 200
