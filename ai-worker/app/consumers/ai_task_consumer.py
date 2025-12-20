import asyncio
import logging
import time

from confluent_kafka import Consumer, KafkaError

from app.config import get_settings
from app.models.schemas import AiTaskEvent
from app.services.ai_service import process_ai_task
from app.utils.metrics import (
    AI_TASKS_TOTAL,
    AI_TASK_DURATION_SECONDS,
    KAFKA_MESSAGES_CONSUMED_TOTAL,
)

logger = logging.getLogger(__name__)

TOPIC = "ai-tasks"


class AiTaskConsumer:
    def __init__(self):
        self._running = False
        self._consumer: Consumer = None

    def _create_consumer(self) -> Consumer:
        settings = get_settings()
        return Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id + "-ai-task",
            "auto.offset.reset": settings.kafka_auto_offset_reset,
            "enable.auto.commit": False,
        })

    async def start(self) -> None:
        self._running = True
        self._consumer = self._create_consumer()
        self._consumer.subscribe([TOPIC])
        logger.info("AI task consumer started, subscribed to %s", TOPIC)

        loop = asyncio.get_event_loop()
        while self._running:
            msg = await loop.run_in_executor(
                None, lambda: self._consumer.poll(timeout=1.0)
            )
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("AI task consumer error: %s", msg.error())
                KAFKA_MESSAGES_CONSUMED_TOTAL.labels(
                    topic=TOPIC, status="error"
                ).inc()
                continue

            await self._handle_message(msg)

        self._consumer.close()
        logger.info("AI task consumer stopped")

    def stop(self) -> None:
        self._running = False

    async def _handle_message(self, msg) -> None:
        start = time.time()
        try:
            event = AiTaskEvent.model_validate_json(msg.value().decode("utf-8"))
            logger.info(
                "Processing AI task %s (session=%s)",
                event.taskId, event.sessionId,
            )

            await process_ai_task(event)

            duration = time.time() - start
            AI_TASKS_TOTAL.labels(status="success").inc()
            AI_TASK_DURATION_SECONDS.observe(duration)
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="success").inc()
            self._consumer.commit(msg)

        except Exception as e:
            logger.exception("Failed to process AI task: %s", e)
            AI_TASKS_TOTAL.labels(status="failed").inc()
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="error").inc()
            self._consumer.commit(msg)
