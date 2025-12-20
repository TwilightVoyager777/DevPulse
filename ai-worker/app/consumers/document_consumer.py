import asyncio
import json
import logging
import time

from confluent_kafka import Consumer, KafkaError

from app.config import get_settings
from app.models.schemas import DocumentIngestionEvent
from app.services.document_service import ingest_document
from app.services.bm25_service import build_and_save_index
from app.utils.metrics import (
    DOCS_INGESTED_TOTAL,
    CHUNKS_CREATED_TOTAL,
    INGESTION_DURATION_SECONDS,
    KAFKA_MESSAGES_CONSUMED_TOTAL,
)

logger = logging.getLogger(__name__)

TOPIC = "document-ingestion"


class DocumentConsumer:
    def __init__(self):
        self._running = False
        self._consumer: Consumer = None

    def _create_consumer(self) -> Consumer:
        settings = get_settings()
        return Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id + "-document",
            "auto.offset.reset": settings.kafka_auto_offset_reset,
            "enable.auto.commit": False,
        })

    async def start(self) -> None:
        self._running = True
        self._consumer = self._create_consumer()
        self._consumer.subscribe([TOPIC])
        logger.info("Document consumer started, subscribed to %s", TOPIC)

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
                logger.error("Document consumer error: %s", msg.error())
                KAFKA_MESSAGES_CONSUMED_TOTAL.labels(
                    topic=TOPIC, status="error"
                ).inc()
                continue

            await self._handle_message(msg)

        self._consumer.close()
        logger.info("Document consumer stopped")

    def stop(self) -> None:
        self._running = False

    async def _handle_message(self, msg) -> None:
        start = time.time()
        try:
            event = DocumentIngestionEvent.model_validate_json(msg.value().decode("utf-8"))
            logger.info(
                "Ingesting document %s (workspace=%s, type=%s)",
                event.documentId, event.workspaceId, event.sourceType,
            )

            chunk_count = await ingest_document(
                document_id=str(event.documentId),
                workspace_id=str(event.workspaceId),
                content=event.contentOrPath,
                source_type=event.sourceType,
                metadata=event.metadata,
            )

            # Rebuild BM25 index for the workspace after new document
            if chunk_count > 0:
                await build_and_save_index(str(event.workspaceId))

            duration = time.time() - start
            DOCS_INGESTED_TOTAL.labels(status="success").inc()
            CHUNKS_CREATED_TOTAL.inc(chunk_count)
            INGESTION_DURATION_SECONDS.observe(duration)
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="success").inc()

            self._consumer.commit(msg)
            logger.info(
                "Document %s ingested: %d chunks in %.2fs",
                event.documentId, chunk_count, duration,
            )

        except Exception as e:
            logger.exception("Failed to process document ingestion: %s", e)
            DOCS_INGESTED_TOTAL.labels(status="failed").inc()
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="error").inc()
            self._consumer.commit(msg)  # Commit to avoid reprocessing bad messages
