"""Fleet status capability: returns worker slot configs from fleet.yaml."""

from dataclasses import asdict
from typing import Any, Dict

from agentend.kernel.kernel import RequestContext


class FleetStatusCapability:
    """Returns worker slot configurations from fleet.yaml.

    Reports model, backend, fallback, routing, temperature, and max_tokens
    for each worker slot (classify, extract, verify, summarize, generate, tool_call).
    """

    name: str = "fleet.status"
    description: str = "Returns worker slot configs from fleet.yaml"

    async def execute(self, context: RequestContext, **kwargs: Any) -> Dict[str, Any]:
        """Return fleet worker slot configurations.

        Args:
            context: Request context with app state in metadata.

        Returns:
            Dict with slot names mapped to their configuration.
        """
        config = context.metadata.get("app_config")
        if config is None:
            return {"error": "Configuration not available", "slots": {}}

        fleet = config.fleet
        slots = {}
        for slot_name in ("classify", "extract", "verify", "summarize", "generate", "tool_call"):
            slot_config = getattr(fleet, slot_name, None)
            if slot_config is not None:
                slots[slot_name] = {
                    "model": slot_config.model,
                    "backend": slot_config.backend,
                    "fallback": slot_config.fallback,
                    "routing": slot_config.routing,
                    "routing_threshold": slot_config.routing_threshold,
                    "temperature": slot_config.temperature,
                    "max_tokens": slot_config.max_tokens,
                }

        return {"capability": "fleet.status", "slots": slots}
