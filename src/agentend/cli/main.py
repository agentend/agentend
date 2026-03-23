"""CLI application using Typer."""

from typing import Optional
from pathlib import Path
import os
import sys
import subprocess
import logging

import typer
import yaml

from agentend.server.app import create_app


logger = logging.getLogger(__name__)

app = typer.Typer(
    name="agentend",
    help="Agent execution and orchestration engine",
)


@app.command()
def init(
    name: str = typer.Argument("my-agent", help="Project name"),
    python_version: str = typer.Option("3.11", help="Python version"),
):
    """
    Scaffold a new agentend project.

    Creates project directory with:
    - app.py: Application entry point
    - fleet.yaml: Fleet configuration
    - Dockerfile: Container definition
    - requirements.txt: Dependencies
    """
    project_path = Path(name)

    if project_path.exists():
        typer.echo(f"Error: Directory already exists: {name}", err=True)
        raise typer.Exit(code=1)

    project_path.mkdir(parents=True)
    typer.echo(f"Created project directory: {name}")

    # Create app.py
    app_content = '''"""Generated agentend application."""

import uvicorn
from agentend.server import create_app
from agentend.config import Config

if __name__ == "__main__":
    config = Config.load()
    app = create_app(config)
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
    (project_path / "app.py").write_text(app_content)
    typer.echo("Created app.py")

    # Create fleet.yaml
    fleet_content = f'''# Agentend Fleet Configuration
version: "1"
name: {name}
description: "{name} agent fleet"

agents:
  - name: main-agent
    capabilities:
      - semantic_search
      - document_ingestion
      - memory_management

workers:
  - name: executor
    capabilities: ["execute"]
    instances: 2
    memory_mb: 512
    timeout_seconds: 300

storage:
  type: postgresql
  url: "postgresql://user:password@localhost/agentend"

cache:
  type: redis
  url: "redis://localhost:6379"

observability:
  tracing:
    enabled: true
    endpoint: "http://localhost:4318"
  metrics:
    enabled: true
    interval_seconds: 60
'''
    (project_path / "fleet.yaml").write_text(fleet_content)
    typer.echo("Created fleet.yaml")

    # Create requirements.txt
    requirements = """agentend>=0.1.0
uvicorn[standard]>=0.24.0
fastapi>=0.104.0
sqlalchemy[asyncio]>=2.0.0
redis[asyncio]>=5.0.0
pydantic>=2.0.0
opentelemetry-api>=1.20.0
opentelemetry-sdk>=1.20.0
"""
    (project_path / "requirements.txt").write_text(requirements)
    typer.echo("Created requirements.txt")

    # Create Dockerfile
    dockerfile = f"""FROM python:{python_version}-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
"""
    (project_path / "Dockerfile").write_text(dockerfile)
    typer.echo("Created Dockerfile")

    # Create .env.example
    env_example = """# Database
DATABASE_URL=postgresql://user:password@localhost/agentend

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET=your-secret-key

# API Keys
VALID_API_KEYS=key1,key2

# Debug
DEBUG=false

# CORS
CORS_ORIGINS=http://localhost:3000

# Logging
LOG_LEVEL=INFO
"""
    (project_path / ".env.example").write_text(env_example)
    typer.echo("Created .env.example")

    typer.echo(f"\nProject initialized: {name}")
    typer.echo(f"Next steps:\n  cd {name}\n  pip install -r requirements.txt\n  python app.py")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
    workers: int = typer.Option(1, help="Number of worker processes"),
):
    """
    Start the agentend server.

    Runs FastAPI application with configurable host, port, and reload.
    """
    try:
        from agentend.config import Config

        config = Config.load()
        app_instance = create_app(config)

        typer.echo(f"Starting agentend server on {host}:{port}")

        import uvicorn

        uvicorn.run(
            app_instance,
            host=host,
            port=port,
            reload=reload,
            workers=workers,
            log_level="info",
        )

    except Exception as e:
        typer.echo(f"Error: Failed to start server: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def fleet():
    """Show current fleet configuration."""
    fleet_path = Path("fleet.yaml")

    if not fleet_path.exists():
        typer.echo("Error: fleet.yaml not found", err=True)
        raise typer.Exit(code=1)

    try:
        with open(fleet_path) as f:
            config = yaml.safe_load(f)

        typer.echo("\nFleet Configuration:")
        typer.echo(f"  Name: {config.get('name')}")
        typer.echo(f"  Version: {config.get('version')}")
        typer.echo(f"  Description: {config.get('description')}")

        agents = config.get("agents", [])
        typer.echo(f"\nAgents ({len(agents)}):")
        for agent in agents:
            typer.echo(f"  - {agent['name']}")
            for cap in agent.get("capabilities", []):
                typer.echo(f"    * {cap}")

        workers = config.get("workers", [])
        typer.echo(f"\nWorkers ({len(workers)}):")
        for worker in workers:
            typer.echo(f"  - {worker['name']} ({worker.get('instances', 1)} instances)")
            typer.echo(f"    Memory: {worker.get('memory_mb', 512)}MB")
            typer.echo(f"    Timeout: {worker.get('timeout_seconds', 300)}s")

    except Exception as e:
        typer.echo(f"Error: Failed to read fleet.yaml: {e}", err=True)
        raise typer.Exit(code=1)


@app.command()
def memory():
    """Show memory status and statistics."""
    try:
        import redis
        import os

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = redis.from_url(redis_url, decode_responses=True)

        info = client.info()

        typer.echo("\nMemory Status:")
        typer.echo(f"  Used: {info.get('used_memory_human', 'unknown')}")
        typer.echo(f"  Peak: {info.get('used_memory_peak_human', 'unknown')}")
        typer.echo(f"  RSS: {info.get('used_memory_rss_human', 'unknown')}")

        typer.echo(f"\nCache Stats:")
        keys = client.dbsize()
        typer.echo(f"  Total Keys: {keys}")

        # Get cache key patterns
        cache_keys = client.keys("cache:*")
        typer.echo(f"  Cache Entries: {len(cache_keys)}")

        session_keys = client.keys("session:*")
        typer.echo(f"  Active Sessions: {len(session_keys)}")

        budget_keys = client.keys("budget:*")
        typer.echo(f"  Budget Tracking Keys: {len(budget_keys)}")

    except Exception as e:
        typer.echo(f"Error: Failed to connect to Redis: {e}", err=True)
        typer.echo("Make sure Redis is running and REDIS_URL is set", err=True)


@app.command()
def version():
    """Show version information."""
    import agentend

    typer.echo(f"agentend {getattr(agentend, '__version__', '0.1.0')}")


if __name__ == "__main__":
    app()
