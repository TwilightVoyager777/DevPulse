import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import get_settings
from app.utils.db import get_pool, close_pool, list_bm25_workspace_ids
from app.utils.redis_client import get_redis, close_redis
from app.utils.metrics import APP_INFO
from app.consumers.document_consumer import DocumentConsumer
from app.consumers.ai_task_consumer import AiTaskConsumer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB pool, Redis, restore BM25 indexes, start Kafka consumers."""
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level))

    logger.info("Starting AI Worker...")

    # Init DB pool
    await get_pool()
    logger.info("DB pool initialized")

    # Init Redis
    await get_redis()
    logger.info("Redis connected")

    # Restore BM25 indexes from DB into memory cache
    from app.services.bm25_service import get_index, _index_cache
    try:
        workspace_ids = await list_bm25_workspace_ids()
        for wid in workspace_ids:
            await get_index(wid)
        logger.info("Restored BM25 indexes for %d workspaces", len(_index_cache))
    except Exception as e:
        logger.warning("BM25 index restore failed (non-fatal): %s", e)

    # Start Kafka consumers
    doc_consumer = DocumentConsumer()
    ai_consumer = AiTaskConsumer()

    doc_task = asyncio.create_task(doc_consumer.start())
    ai_task = asyncio.create_task(ai_consumer.start())

    APP_INFO.labels(version="1.0.0").set(1)
    logger.info("AI Worker ready")

    yield

    # Shutdown
    logger.info("Shutting down AI Worker...")
    doc_consumer.stop()
    ai_consumer.stop()
    await asyncio.gather(doc_task, ai_task, return_exceptions=True)
    await close_pool()
    await close_redis()
    logger.info("AI Worker stopped")


app = FastAPI(title="DevPulse AI Worker", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    from app.services.bm25_service import _index_cache
    return {"status": "ok", "bm25_indexes_loaded": len(_index_cache)}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST
    )
