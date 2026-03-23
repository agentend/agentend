"""API routes for agentend server."""

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Body
from fastapi.responses import StreamingResponse
import json

from agentend.auth.middleware import get_current_user
from agentend.auth.jwt import TokenPayload
from agentend.async_.tasks import AsyncTaskManager, RunStatus
from agentend.observability.traces import traced
from agentend.persistence.models import Session as SessionModel
from agentend.security.sanitizer import InputSanitizer
from pydantic import BaseModel, Field


router = APIRouter()


class IntentRequest(BaseModel):
    """Request model for /intent endpoint."""
    capability: str = Field(..., min_length=1)
    input: str = Field(..., min_length=1)
    stream: bool = Field(default=True)


class IntentResponse(BaseModel):
    """Response model for /intent endpoint."""
    session_id: str
    stream_url: Optional[str] = None
    status: str


class RunRequest(BaseModel):
    """Request model for async run submission."""
    workflow: str = Field(..., min_length=1)
    parameters: dict = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=100)


class RunResponse(BaseModel):
    """Response model for run submission."""
    run_id: str
    status: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


class ReadinessResponse(BaseModel):
    """Readiness check response."""
    ready: bool
    checks: dict[str, bool]


class AgentCard(BaseModel):
    """Agent capability card for A2A discovery."""
    name: str
    description: str
    capabilities: list[str]
    version: str


@router.post("/intent")
async def submit_intent(
    request: IntentRequest,
    current_user: TokenPayload = Depends(get_current_user),
    server_request: Request = None,
):
    """
    Accept an intent, execute the capability, and return results.

    When stream=True, returns an SSE stream with AG-UI events.
    When stream=False, returns JSON with session_id and status.
    """
    import logging
    import time
    logger = logging.getLogger(__name__)

    sanitizer = InputSanitizer()
    try:
        cleaned_input = sanitizer.sanitize(request.input)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")

    session_id = str(uuid4())

    # Persist session if database is available
    session_factory = getattr(server_request.app.state, "session_factory", None)
    if session_factory:
        try:
            session = SessionModel(
                id=session_id,
                tenant_id=current_user.tenant_id,
                user_id=current_user.user_id,
                capability=request.capability,
                status="created",
            )
            task_manager = AsyncTaskManager(session_factory)
            await task_manager.create_session(session)
        except Exception as e:
            logger.warning(f"Failed to persist session: {e}")

    # Look up capability from registry
    registry = getattr(server_request.app.state, "registry", None)
    capability = registry.lookup(request.capability) if registry else None

    if not request.stream:
        return IntentResponse(
            session_id=session_id,
            stream_url=None,
            status="created",
        )

    # Stream mode: execute capability and return SSE
    from agentend.kernel.kernel import RequestContext

    context = RequestContext(
        user_id=current_user.user_id,
        session_id=session_id,
        tenant_id=current_user.tenant_id,
        metadata={
            "app_config": getattr(server_request.app.state, "config", None),
            "redis": getattr(server_request.app.state, "redis", None),
            "engine": getattr(server_request.app.state, "engine", None),
            "session_factory": session_factory,
            "metrics": getattr(server_request.app.state, "metrics", None),
        },
    )

    async def event_generator():
        ts = lambda: datetime.utcnow().isoformat()

        # run_started
        yield f"data: {json.dumps({'type': 'run_started', 'timestamp': ts(), 'run_id': session_id, 'session_id': session_id, 'input': cleaned_input})}\n\n"

        if not capability:
            yield f"data: {json.dumps({'type': 'run_error', 'timestamp': ts(), 'run_id': session_id, 'error_type': 'not_found', 'message': f'Capability not found: {request.capability}', 'recoverable': False})}\n\n"
            return

        try:
            # Execute capability
            result = await capability.execute(context, intent=cleaned_input)

            # Emit state_snapshot with the result
            yield f"data: {json.dumps({'type': 'state_snapshot', 'timestamp': ts(), 'run_id': session_id, 'state': result if isinstance(result, dict) else {'result': result}, 'memory': {}})}\n\n"

            # Emit text summary
            yield f"data: {json.dumps({'type': 'text_message_start', 'timestamp': ts(), 'run_id': session_id, 'content_type': 'text'})}\n\n"

            # Generate a human-readable summary from result
            if isinstance(result, dict):
                summary = json.dumps(result, indent=2, default=str)
            else:
                summary = str(result)
            yield f"data: {json.dumps({'type': 'text_message_content', 'timestamp': ts(), 'run_id': session_id, 'content': summary, 'delta': False})}\n\n"
            yield f"data: {json.dumps({'type': 'text_message_end', 'timestamp': ts(), 'run_id': session_id, 'stop_reason': 'end_turn'})}\n\n"

            # run_finished
            yield f"data: {json.dumps({'type': 'run_finished', 'timestamp': ts(), 'run_id': session_id, 'result': 'success', 'stop_reason': 'end_turn', 'messages_sent': 1, 'tools_used': []})}\n\n"

        except Exception as e:
            logger.error(f"Capability execution error: {e}")
            yield f"data: {json.dumps({'type': 'run_error', 'timestamp': ts(), 'run_id': session_id, 'error_type': type(e).__name__, 'message': str(e), 'recoverable': False})}\n\n"

    from datetime import datetime
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/stream/{session_id}")
async def stream_events(
    session_id: str,
    request: Request = None,
    token: Optional[str] = None,
):
    """
    Server-sent events stream for real-time session updates.
    Accepts auth via Authorization header or ?token= query param
    (needed because EventSource cannot send custom headers).
    """
    import os
    from agentend.auth.jwt import verify_token

    # Try query param token first (for EventSource), then header
    secret = os.getenv("JWT_SECRET", "dev-secret")
    auth_token = token
    if not auth_token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            auth_token = auth_header[7:]

    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        current_user = verify_token(auth_token, secret)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        raise HTTPException(status_code=503, detail="Database unavailable")

    task_manager = AsyncTaskManager(session_factory)

    async def event_generator():
        """Generate SSE events for session."""
        async for event in task_manager.stream_session(session_id, current_user.tenant_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/runs/{run_id}", response_model=dict)
@traced("poll_run_status_endpoint")
async def get_run_status(
    run_id: str,
    current_user: TokenPayload = Depends(get_current_user),
    request: Request = None,
) -> dict:
    """
    Poll async run status.

    Args:
        run_id: Run ID to check.
        current_user: Authenticated user.
        request: FastAPI request object.

    Returns:
        Run status and metadata.
    """
    task_manager = AsyncTaskManager(request.app.state.session_factory)
    status = await task_manager.poll_run_status(run_id, current_user.tenant_id)

    if status is None:
        raise HTTPException(status_code=404, detail="Run not found")

    return status


@router.post("/runs", response_model=RunResponse)
@traced("submit_workflow_endpoint")
async def submit_workflow(
    request: RunRequest,
    current_user: TokenPayload = Depends(get_current_user),
    server_request: Request = None,
) -> RunResponse:
    """
    Submit an async workflow (fire-and-forget).

    Args:
        request: Workflow request with name and parameters.
        current_user: Authenticated user.
        server_request: FastAPI request object.

    Returns:
        Run ID and initial status.
    """
    sanitizer = InputSanitizer()
    try:
        for key, value in request.parameters.items():
            if isinstance(value, str):
                request.parameters[key] = sanitizer.sanitize(value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {str(e)}")

    run_id = str(uuid4())
    task_manager = AsyncTaskManager(server_request.app.state.session_factory)
    await task_manager.submit_workflow(
        run_id,
        request.workflow,
        request.parameters,
        current_user.tenant_id,
        current_user.user_id,
        request.priority,
    )

    return RunResponse(run_id=run_id, status="submitted")


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.

    Returns:
        Health status and version.
    """
    return HealthResponse(
        status="healthy",
        version="0.1.0",
    )


@router.get("/ready", response_model=ReadinessResponse)
@traced("readiness_check_endpoint")
async def readiness_check(request: Request = None) -> ReadinessResponse:
    """
    Readiness check for Kubernetes/orchestration.

    Returns:
        Readiness status with component checks.
    """
    checks = {
        "postgresql": False,
        "redis": False,
        "ollama": False,
    }

    try:
        # Check PostgreSQL
        from sqlalchemy import text
        engine = request.app.state.engine
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgresql"] = True
    except Exception:
        pass

    try:
        # Check Redis
        redis_client = request.app.state.redis
        await redis_client.ping()
        checks["redis"] = True
    except Exception:
        pass

    try:
        # Check Ollama (optional, failures don't fail readiness)
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://ollama:11434/api/tags", timeout=2.0)
            checks["ollama"] = response.status_code == 200
    except Exception:
        checks["ollama"] = False

    ready = checks["postgresql"] and checks["redis"]

    return ReadinessResponse(
        ready=ready,
        checks=checks,
    )


@router.get("/dev/token")
async def dev_token() -> dict:
    """
    Generate a development JWT token. Only works when JWT_SECRET=dev-secret.
    """
    import os
    secret = os.getenv("JWT_SECRET", "dev-secret")
    if secret != "dev-secret":
        raise HTTPException(status_code=404, detail="Not found")

    from agentend.auth.jwt import encode_token
    token = encode_token(
        user_id="dev-user",
        tenant_id="dev-tenant",
        roles=["admin"],
        capabilities=[
            "execute", "fleet.status", "system.health",
            "memory.inspect", "metrics.usage", "sessions.list",
            "workflow.status",
        ],
        secret=secret,
        expires_in_hours=720,
    )
    return {"token": token}


@router.get("/.well-known/agent.json", response_model=AgentCard)
async def agent_card() -> AgentCard:
    """
    A2A (Agent-to-Agent) capability discovery endpoint.

    Returns:
        Agent capability card.
    """
    return AgentCard(
        name="agentend",
        description="Agent execution and orchestration engine",
        capabilities=[
            "semantic_search",
            "document_ingestion",
            "memory_management",
            "tool_execution",
            "workflow_orchestration",
        ],
        version="0.1.0",
    )
