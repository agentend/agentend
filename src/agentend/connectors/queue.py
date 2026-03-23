"""Message queue connectors for asynchronous task processing.

Provides connectors for in-memory queues and distributed message brokers
like Redis, RabbitMQ, and Kafka.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional

from agentend.connectors.base import Connector, ConnectorConfig

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import pika
    RABBITMQ_AVAILABLE = True
except ImportError:
    RABBITMQ_AVAILABLE = False

try:
    from kafka import KafkaProducer, KafkaConsumer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False


class QueueConnector(Connector):
    """Abstract base connector for message queues.

    Provides common interface for publishing and subscribing to topics.
    """

    async def publish(self, topic: str, message: Any) -> None:
        """Publish a message to a topic.

        Args:
            topic: Topic name.
            message: Message to publish.
        """
        pass

    async def subscribe(
        self, topic: str, callback: Callable[[Any], None]
    ) -> None:
        """Subscribe to a topic and receive messages.

        Args:
            topic: Topic name.
            callback: Async callback function to handle messages.
        """
        pass


class InMemoryQueueConnector(QueueConnector):
    """In-memory message queue using asyncio.Queue.

    Zero external dependencies, suitable for single-process applications.
    Not suitable for distributed systems.

    Configuration:
        ConnectorConfig(
            name="queue",
            connector_type="memory_queue"
        )
    """

    def __init__(self, config: ConnectorConfig):
        """Initialize in-memory queue connector."""
        super().__init__(config)
        self._queues: Dict[str, asyncio.Queue] = {}
        self._subscriptions: Dict[str, list[Callable]] = {}
        self._tasks: list[asyncio.Task] = []

    async def connect(self) -> None:
        """Initialize in-memory queue system."""
        self._queues.clear()
        self._subscriptions.clear()
        self._connected = True
        logger.info("In-memory queue connector initialized")

    async def disconnect(self) -> None:
        """Shutdown in-memory queue system."""
        # Cancel all subscription tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to finish
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._queues.clear()
        self._subscriptions.clear()
        self._tasks.clear()
        self._connected = False

    async def health_check(self) -> bool:
        """In-memory queue is always available."""
        return True

    async def execute(self, operation: str, **kwargs) -> Any:
        """Execute queue operation.

        Operations:
            - publish: Publish message (requires 'topic', 'message')
            - subscribe: Subscribe to topic (requires 'topic', 'callback')
        """
        if operation == "publish":
            await self.publish(kwargs.get("topic"), kwargs.get("message"))
            return True
        elif operation == "subscribe":
            await self.subscribe(kwargs.get("topic"), kwargs.get("callback"))
            return True
        else:
            raise ValueError(f"Unknown queue operation: {operation}")

    async def publish(self, topic: str, message: Any) -> None:
        """Publish message to topic."""
        # Ensure queue exists
        if topic not in self._queues:
            self._queues[topic] = asyncio.Queue()

        await self._queues[topic].put(message)

        # Notify subscribers
        if topic in self._subscriptions:
            for callback in self._subscriptions[topic]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    logger.error(f"Error in queue callback: {e}")

    async def subscribe(
        self, topic: str, callback: Callable[[Any], None]
    ) -> None:
        """Subscribe to topic messages."""
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []

        self._subscriptions[topic].append(callback)

        # Ensure queue exists
        if topic not in self._queues:
            self._queues[topic] = asyncio.Queue()

        # Start background task to listen for messages
        task = asyncio.create_task(self._listen(topic, callback))
        self._tasks.append(task)

    async def _listen(self, topic: str, callback: Callable) -> None:
        """Listen for messages on a topic."""
        queue = self._queues[topic]
        try:
            while True:
                message = await queue.get()
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(message)
                    else:
                        callback(message)
                except Exception as e:
                    logger.error(f"Error in callback for {topic}: {e}")
        except asyncio.CancelledError:
            pass


def _make_redis_queue_stub() -> type:
    """Create a stub RedisQueueConnector for when redis is not installed."""
    class RedisQueueConnector(QueueConnector):
        """Stub: Redis queue connector.

        Requires optional 'redis' dependency.
        Install with: pip install redis
        """

        async def connect(self) -> None:
            raise ImportError(
                "Redis queue requires the 'redis' package. "
                "Install with: pip install redis"
            )

        async def disconnect(self) -> None:
            pass

        async def health_check(self) -> bool:
            return False

        async def execute(self, operation: str, **kwargs) -> Any:
            raise ImportError(
                "Redis queue requires the 'redis' package. "
                "Install with: pip install redis"
            )

        async def publish(self, topic: str, message: Any) -> None:
            raise ImportError(
                "Redis queue requires the 'redis' package. "
                "Install with: pip install redis"
            )

        async def subscribe(
            self, topic: str, callback: Callable[[Any], None]
        ) -> None:
            raise ImportError(
                "Redis queue requires the 'redis' package. "
                "Install with: pip install redis"
            )

    return RedisQueueConnector


def _make_rabbitmq_stub() -> type:
    """Create a stub RabbitMQConnector for when pika is not installed."""
    class RabbitMQConnector(QueueConnector):
        """Stub: RabbitMQ connector.

        Requires optional 'pika' dependency.
        Install with: pip install pika
        """

        async def connect(self) -> None:
            raise ImportError(
                "RabbitMQ support requires the 'pika' package. "
                "Install with: pip install pika"
            )

        async def disconnect(self) -> None:
            pass

        async def health_check(self) -> bool:
            return False

        async def execute(self, operation: str, **kwargs) -> Any:
            raise ImportError(
                "RabbitMQ support requires the 'pika' package. "
                "Install with: pip install pika"
            )

        async def publish(self, topic: str, message: Any) -> None:
            raise ImportError(
                "RabbitMQ support requires the 'pika' package. "
                "Install with: pip install pika"
            )

        async def subscribe(
            self, topic: str, callback: Callable[[Any], None]
        ) -> None:
            raise ImportError(
                "RabbitMQ support requires the 'pika' package. "
                "Install with: pip install pika"
            )

    return RabbitMQConnector


def _make_kafka_stub() -> type:
    """Create a stub KafkaConnector for when kafka is not installed."""
    class KafkaConnector(QueueConnector):
        """Stub: Apache Kafka connector.

        Requires optional 'kafka-python' dependency.
        Install with: pip install kafka-python
        """

        async def connect(self) -> None:
            raise ImportError(
                "Kafka support requires the 'kafka-python' package. "
                "Install with: pip install kafka-python"
            )

        async def disconnect(self) -> None:
            pass

        async def health_check(self) -> bool:
            return False

        async def execute(self, operation: str, **kwargs) -> Any:
            raise ImportError(
                "Kafka support requires the 'kafka-python' package. "
                "Install with: pip install kafka-python"
            )

        async def publish(self, topic: str, message: Any) -> None:
            raise ImportError(
                "Kafka support requires the 'kafka-python' package. "
                "Install with: pip install kafka-python"
            )

        async def subscribe(
            self, topic: str, callback: Callable[[Any], None]
        ) -> None:
            raise ImportError(
                "Kafka support requires the 'kafka-python' package. "
                "Install with: pip install kafka-python"
            )

    return KafkaConnector


# Create actual or stub connectors based on availability
if REDIS_AVAILABLE:
    class RedisQueueConnector(QueueConnector):
        """Redis-based message queue connector.

        Uses Redis Streams or Pub/Sub for message queuing.

        Configuration:
            ConnectorConfig(
                name="redis_queue",
                connector_type="redis_queue",
                connection_string="redis://localhost:6379/0"
            )
        """

        def __init__(self, config: ConnectorConfig):
            super().__init__(config)
            self._client: Optional[redis.Redis] = None

        async def connect(self) -> None:
            if not self.config.connection_string:
                raise ValueError("Redis queue requires connection_string")

            try:
                self._client = await redis.from_url(
                    self.config.connection_string
                )
                await self._client.ping()
                self._connected = True
                logger.info("Connected to Redis queue")
            except Exception as e:
                logger.error(f"Failed to connect to Redis queue: {e}")
                raise ConnectionError(f"Redis queue connection failed: {e}")

        async def disconnect(self) -> None:
            if self._client:
                try:
                    await self._client.close()
                except Exception as e:
                    logger.error(f"Error closing Redis connection: {e}")
            self._connected = False

        async def health_check(self) -> bool:
            if not self._client:
                return False
            try:
                await self._client.ping()
                return True
            except Exception:
                return False

        async def execute(self, operation: str, **kwargs) -> Any:
            if not self._connected or not self._client:
                raise RuntimeError("Redis queue is not connected")

            if operation == "publish":
                await self.publish(kwargs.get("topic"), kwargs.get("message"))
                return True
            else:
                raise ValueError(f"Unknown queue operation: {operation}")

        async def publish(self, topic: str, message: Any) -> None:
            if not self._client:
                raise RuntimeError("Redis queue is not connected")

            # Serialize message if needed
            msg_str = str(message) if not isinstance(message, str) else message
            await self._client.xadd(topic, {"message": msg_str})

        async def subscribe(
            self, topic: str, callback: Callable[[Any], None]
        ) -> None:
            if not self._client:
                raise RuntimeError("Redis queue is not connected")

            # Listen for new messages
            last_id = "0"
            try:
                while self._connected:
                    messages = await self._client.xread({topic: last_id})
                    for stream, msg_list in messages:
                        for msg_id, msg_data in msg_list:
                            last_id = msg_id
                            message = msg_data.get("message")
                            if asyncio.iscoroutinefunction(callback):
                                await callback(message)
                            else:
                                callback(message)
            except asyncio.CancelledError:
                pass

else:
    RedisQueueConnector = _make_redis_queue_stub()


# Stubs for RabbitMQ and Kafka
if RABBITMQ_AVAILABLE:
    class RabbitMQConnector(QueueConnector):
        """RabbitMQ message broker connector.

        Configuration:
            ConnectorConfig(
                name="rabbitmq",
                connector_type="rabbitmq",
                connection_string="amqp://user:pass@localhost/"
            )
        """

        def __init__(self, config: ConnectorConfig):
            super().__init__(config)
            self._connection = None
            self._channel = None

        async def connect(self) -> None:
            raise NotImplementedError(
                "RabbitMQ connector is not yet fully implemented"
            )

        async def disconnect(self) -> None:
            pass

        async def health_check(self) -> bool:
            return False

        async def execute(self, operation: str, **kwargs) -> Any:
            raise NotImplementedError(
                "RabbitMQ connector is not yet fully implemented"
            )

        async def publish(self, topic: str, message: Any) -> None:
            raise NotImplementedError(
                "RabbitMQ connector is not yet fully implemented"
            )

        async def subscribe(
            self, topic: str, callback: Callable[[Any], None]
        ) -> None:
            raise NotImplementedError(
                "RabbitMQ connector is not yet fully implemented"
            )

else:
    RabbitMQConnector = _make_rabbitmq_stub()


if KAFKA_AVAILABLE:
    class KafkaConnector(QueueConnector):
        """Apache Kafka connector for distributed streaming.

        Configuration:
            ConnectorConfig(
                name="kafka",
                connector_type="kafka",
                connection_string="localhost:9092"
            )
        """

        def __init__(self, config: ConnectorConfig):
            super().__init__(config)
            self._producer = None
            self._consumer = None

        async def connect(self) -> None:
            raise NotImplementedError("Kafka connector is not yet fully implemented")

        async def disconnect(self) -> None:
            pass

        async def health_check(self) -> bool:
            return False

        async def execute(self, operation: str, **kwargs) -> Any:
            raise NotImplementedError("Kafka connector is not yet fully implemented")

        async def publish(self, topic: str, message: Any) -> None:
            raise NotImplementedError("Kafka connector is not yet fully implemented")

        async def subscribe(
            self, topic: str, callback: Callable[[Any], None]
        ) -> None:
            raise NotImplementedError("Kafka connector is not yet fully implemented")

else:
    KafkaConnector = _make_kafka_stub()
