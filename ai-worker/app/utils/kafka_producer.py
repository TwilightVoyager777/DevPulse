import json
import logging
from typing import Optional

from confluent_kafka import Producer

from app.config import get_settings
from app.models.schemas import TaskStatusEvent

logger = logging.getLogger(__name__)
_producer: Optional[Producer] = None

TOPIC_TASK_STATUS = "task-status"
TOPIC_INGESTION_DLQ = "document-ingestion-dlq"


def get_producer() -> Producer:
    global _producer
    if _producer is None:
        settings = get_settings()
        _producer = Producer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "client.id": "ai-worker-producer",
            "acks": "1",
            "retries": 3,
            "retry.backoff.ms": 500,
        })
        logger.info("Kafka producer created")
    return _producer


def _delivery_callback(err, msg):
    if err:
        logger.error("Kafka delivery failed for topic %s: %s", msg.topic(), err)


def publish_task_status(event: TaskStatusEvent) -> None:
    producer = get_producer()
    payload = event.model_dump_json()
    producer.produce(
        TOPIC_TASK_STATUS,
        key=str(event.taskId),
        value=payload.encode("utf-8"),
        callback=_delivery_callback,
    )
    producer.poll(0)  # trigger delivery callbacks without blocking


def publish_to_dlq(document_id: str, workspace_id: str, error: str) -> None:
    """Publish a failed ingestion event to the DLQ topic."""
    producer = get_producer()
    payload = json.dumps({
        "documentId": document_id,
        "workspaceId": workspace_id,
        "error": error,
    })
    producer.produce(
        TOPIC_INGESTION_DLQ,
        key=document_id,
        value=payload.encode("utf-8"),
        callback=_delivery_callback,
    )
    producer.poll(0)
    logger.warning("Published document %s to DLQ: %s", document_id, error)


def flush_producer() -> None:
    if _producer:
        _producer.flush(timeout=5)
