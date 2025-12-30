import asyncio
import logging
import time

from confluent_kafka import Consumer, KafkaError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.models.schemas import DocumentIngestionEvent
from app.services.document_service import ingest_document
from app.services.bm25_service import build_and_save_index
from app.utils.metrics import (
    INGESTION_DOCUMENTS_TOTAL,
    INGESTION_CHUNKS_TOTAL,
    INGESTION_LATENCY_SECONDS,
    KAFKA_MESSAGES_CONSUMED_TOTAL,
)
from app.utils.redis_client import is_event_processed, mark_event_processed
from app.utils.kafka_producer import publish_to_dlq
from app.utils.db import update_document_status

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
        doc_id: str = ""
        workspace_id: str = ""
        try:
            event = DocumentIngestionEvent.model_validate_json(msg.value().decode("utf-8"))
            doc_id = str(event.documentId)
            workspace_id = str(event.workspaceId)

            # Idempotency: skip if already processed
            if await is_event_processed(doc_id):
                logger.debug("Skipping duplicate ingestion for document %s", doc_id)
                self._consumer.commit(msg)
                return

            logger.info(
                "Ingesting document %s (workspace=%s, type=%s)",
                doc_id, event.workspaceId, event.sourceType,
            )

            chunk_count = await _ingest_with_retry(
                document_id=doc_id,
                workspace_id=str(event.workspaceId),
                content=event.contentOrPath,
                source_type=event.sourceType,
                metadata=event.metadata,
            )

            # Rebuild BM25 index for the workspace after new document
            if chunk_count > 0:
                await build_and_save_index(str(event.workspaceId))

            await mark_event_processed(doc_id)

            duration = time.time() - start
            INGESTION_DOCUMENTS_TOTAL.labels(status="indexed").inc()
            INGESTION_CHUNKS_TOTAL.inc(chunk_count)
            INGESTION_LATENCY_SECONDS.observe(duration)
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="success").inc()

            self._consumer.commit(msg)
            logger.info(
                "Document %s ingested: %d chunks in %.2fs",
                doc_id, chunk_count, duration,
            )

        except Exception as e:
            error_msg = str(e)
            logger.exception("Failed to process document ingestion after retries: %s", error_msg)
            INGESTION_DOCUMENTS_TOTAL.labels(status="failed").inc()
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="error").inc()

            # Mark document as FAILED in DB and send to DLQ
            if doc_id:
                try:
                    await update_document_status(doc_id, "FAILED", error_message=error_msg)
                    publish_to_dlq(doc_id, workspace_id, error_msg)
                except Exception as dlq_err:
                    logger.error("Failed to update status / publish DLQ for %s: %s", doc_id, dlq_err)

            self._consumer.commit(msg)  # Commit to avoid infinite reprocessing


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=1, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _ingest_with_retry(
    document_id: str,
    workspace_id: str,
    content: str,
    source_type: str,
    metadata,
) -> int:
    """Ingest a document with tenacity exponential backoff (3 attempts, 1s→2s→4s)."""
    return await ingest_document(
        document_id=document_id,
        workspace_id=workspace_id,
        content=content,
        source_type=source_type,
        metadata=metadata,
    )
