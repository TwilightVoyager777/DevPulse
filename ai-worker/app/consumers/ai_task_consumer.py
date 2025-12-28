import asyncio
import logging

from confluent_kafka import Consumer, KafkaError

from app.config import get_settings
from app.models.schemas import AiTaskEvent
from app.services.ai_service import process_ai_task
from app.utils.metrics import KAFKA_MESSAGES_CONSUMED_TOTAL
from app.utils.redis_client import (
    is_event_processed,
    mark_event_processed,
    acquire_event_lock,
    release_event_lock,
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
        try:
            event = AiTaskEvent.model_validate_json(msg.value().decode("utf-8"))
            task_id = str(event.taskId)

            # Idempotency: skip if already processed
            if await is_event_processed(task_id):
                logger.debug("Skipping duplicate AI task %s", task_id)
                self._consumer.commit(msg)
                return

            # Distributed lock: prevent concurrent processing
            locked = await acquire_event_lock(task_id)
            if not locked:
                logger.debug("AI task %s already locked by another instance, skipping", task_id)
                self._consumer.commit(msg)
                return

            try:
                logger.info("Processing AI task %s (session=%s)", task_id, event.sessionId)
                await process_ai_task(event)
                await mark_event_processed(task_id)
                KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="success").inc()
            finally:
                await release_event_lock(task_id)

            self._consumer.commit(msg)

        except Exception as e:
            logger.exception("Failed to process AI task: %s", e)
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="error").inc()
            self._consumer.commit(msg)
