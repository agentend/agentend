"""
LiteLLM backend for unified LLM access across multiple providers.
"""

from typing import Any, AsyncGenerator, Dict, List, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)


class LiteLLMBackend:
    """
    Backend using LiteLLM for unified LLM access.

    Wraps litellm.acompletion and litellm.aembedding with support for:
    - Multiple LLM providers (OpenAI, Anthropic, Cohere, etc.)
    - Smart routing with RouteLLM
    - Fallback chains
    - Streaming and embedding operations
    """

    def __init__(self) -> None:
        """Initialize the LiteLLM backend."""
        self._init_litellm()

    def _init_litellm(self) -> None:
        """Initialize LiteLLM with proper settings."""
        try:
            import litellm

            litellm.set_verbose = False
        except ImportError:
            logger.warning("LiteLLM not installed. Install with: pip install litellm")

    async def complete(
        self, messages: List[Dict[str, str]], model: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Get a completion from an LLM.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model identifier (e.g., 'gpt-4', 'claude-3-opus').
            **kwargs: Additional arguments (temperature, max_tokens, routing, etc.).

        Returns:
            Response dict with 'content' and optional 'usage' fields.
        """
        try:
            import litellm
        except ImportError:
            raise ImportError("LiteLLM required. Install with: pip install litellm")

        # Extract routing config if present
        routing_config = kwargs.pop("routing", None)
        routing_threshold = kwargs.pop("routing_threshold", 0.5)

        # Handle RouteLLM smart routing
        if routing_config:
            model = await self._apply_routing(
                model, messages, routing_config, routing_threshold
            )

        try:
            # Make async completion call
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                **kwargs,
            )

            # Extract content from response
            content = ""
            if hasattr(response, "choices") and response.choices:
                content = response.choices[0].message.content

            return {
                "content": content,
                "model": model,
                "usage": getattr(response, "usage", None),
            }

        except Exception as e:
            logger.error(f"LiteLLM completion failed: {e}")
            raise

    async def stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Stream completion tokens from an LLM.

        Args:
            messages: List of message dicts.
            model: Model identifier.
            **kwargs: Additional arguments.

        Yields:
            Response tokens as they are produced.
        """
        try:
            import litellm
        except ImportError:
            raise ImportError("LiteLLM required")

        routing_config = kwargs.pop("routing", None)
        routing_threshold = kwargs.pop("routing_threshold", 0.5)

        if routing_config:
            model = await self._apply_routing(
                model, messages, routing_config, routing_threshold
            )

        try:
            # Create async stream
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                stream=True,
                **kwargs,
            )

            # Iterate over stream
            async for chunk in response:
                if hasattr(chunk, "choices") and chunk.choices:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        yield delta.content

        except Exception as e:
            logger.error(f"LiteLLM streaming failed: {e}")
            raise

    async def embed(self, text: str, model: str) -> List[float]:
        """
        Get embeddings for text.

        Args:
            text: Text to embed.
            model: Embedding model identifier.

        Returns:
            Embedding vector as list of floats.
        """
        try:
            import litellm
        except ImportError:
            raise ImportError("LiteLLM required")

        try:
            response = await litellm.aembedding(
                model=model,
                input=text,
            )

            if hasattr(response, "data") and response.data:
                return response.data[0]["embedding"]

            return []

        except Exception as e:
            logger.error(f"LiteLLM embedding failed: {e}")
            raise

    async def _apply_routing(
        self,
        model: str,
        messages: List[Dict[str, str]],
        routing_config: Dict[str, Any],
        threshold: float,
    ) -> str:
        """
        Apply RouteLLM smart routing to select best model.

        Args:
            model: Default model.
            messages: Message history for context.
            routing_config: Routing configuration (route_url, api_key, etc.).
            threshold: Score threshold for routing decision.

        Returns:
            Selected model after routing.
        """
        try:
            route_url = routing_config.get("route_url")
            if not route_url:
                logger.warning("No route_url in routing config, skipping routing")
                return model

            # Get latest message content for routing
            user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break

            # Call RouteLLM endpoint
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        route_url,
                        json={"messages": [{"role": "user", "content": user_message}]},
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            score = data.get("score", 0.5)

                            # Route based on score
                            if score >= threshold:
                                alt_model = routing_config.get("fast_model")
                                if alt_model:
                                    logger.info(
                                        f"RouteLLM score {score} >= {threshold}, "
                                        f"routing from {model} to {alt_model}"
                                    )
                                    return alt_model

                            return model
            except Exception as e:
                logger.warning(f"RouteLLM call failed: {e}, using default model")

        except Exception as e:
            logger.error(f"Routing application failed: {e}")

        return model
