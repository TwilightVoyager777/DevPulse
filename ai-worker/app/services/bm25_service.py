import logging
import pickle
import re
from typing import List, Dict, Optional, Tuple

from rank_bm25 import BM25Okapi

from app.utils.db import (
    get_chunks_for_workspace,
    save_bm25_index,
    load_bm25_index,
)
from app.utils.redis_client import (
    save_bm25_to_redis,
    load_bm25_from_redis,
    acquire_bm25_lock,
    release_bm25_lock,
)
from app.utils.metrics import BM25_CACHE_HIT_TOTAL

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> List[str]:
    """Simple whitespace + punctuation tokenizer (lowercase)."""
    return re.findall(r"\b\w+\b", text.lower())


class BM25Index:
    """Wraps BM25Okapi with chunk metadata for retrieval."""

    def __init__(self, chunks: List[dict]):
        self.chunks = chunks  # [{id, document_id, content, chunk_index}]
        corpus = [_tokenize(c["content"]) for c in chunks]
        self.bm25 = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, top_k: int = 20) -> List[Dict]:
        """Return top-k chunks with BM25 scores."""
        if not self.bm25 or not self.chunks:
            return []
        tokens = _tokenize(query)
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )[:top_k]
        return [
            {**self.chunks[i], "bm25_score": float(score)}
            for i, score in ranked
            if score > 0
        ]

    def to_bytes(self) -> bytes:
        return pickle.dumps({"bm25": self.bm25, "chunks": self.chunks})

    @classmethod
    def from_bytes(cls, data: bytes) -> "BM25Index":
        obj = pickle.loads(data)
        instance = cls.__new__(cls)
        instance.bm25 = obj["bm25"]
        instance.chunks = obj["chunks"]
        return instance


# In-memory cache: workspace_id → BM25Index
_index_cache: Dict[str, BM25Index] = {}


async def build_and_save_index(workspace_id: str) -> BM25Index:
    """Rebuild BM25 from DB chunks and write to all 3 cache layers.

    Uses a distributed Redis lock (bm25:lock:{workspaceId}, TTL 60s) to prevent
    concurrent rebuilds for the same workspace.
    """
    # Acquire distributed lock to prevent duplicate rebuilds
    locked = False
    try:
        locked = await acquire_bm25_lock(workspace_id)
        if not locked:
            # Another instance is rebuilding — wait for it to finish then read from cache
            logger.info("BM25 rebuild already in progress for workspace %s, waiting...", workspace_id)
            import asyncio as _asyncio
            await _asyncio.sleep(2)
            existing = await get_index(workspace_id)
            if existing:
                return existing

        BM25_CACHE_HIT_TOTAL.labels(layer="rebuild").inc()
        chunks = await get_chunks_for_workspace(workspace_id)
        if not chunks:
            logger.info("No chunks for workspace %s, building empty index", workspace_id)

        index = BM25Index(chunks)
        index_bytes = index.to_bytes()

        # Write to all 3 layers simultaneously
        await save_bm25_index(workspace_id, index_bytes, doc_count=len(chunks))  # postgres
        try:
            await save_bm25_to_redis(workspace_id, index_bytes)                  # redis
        except Exception as e:
            logger.warning("Failed to save BM25 to Redis for workspace %s: %s", workspace_id, e)
        _index_cache[workspace_id] = index                                        # memory

        logger.info("BM25 index built for workspace %s: %d chunks", workspace_id, len(chunks))
        return index

    finally:
        if locked:
            try:
                await release_bm25_lock(workspace_id)
            except Exception as e:
                logger.warning("Failed to release BM25 lock for workspace %s: %s", workspace_id, e)


async def get_index(workspace_id: str) -> Optional[BM25Index]:
    """3-layer BM25 cache: memory → Redis → PostgreSQL."""
    # Layer 1: memory
    if workspace_id in _index_cache:
        BM25_CACHE_HIT_TOTAL.labels(layer="memory").inc()
        return _index_cache[workspace_id]

    # Layer 2: Redis
    try:
        redis_data = await load_bm25_from_redis(workspace_id)
        if redis_data:
            BM25_CACHE_HIT_TOTAL.labels(layer="redis").inc()
            index = BM25Index.from_bytes(redis_data)
            _index_cache[workspace_id] = index
            return index
    except Exception as e:
        logger.warning("Redis BM25 lookup failed for workspace %s: %s", workspace_id, e)

    # Layer 3: PostgreSQL (+ write back to Redis)
    pg_data = await load_bm25_index(workspace_id)
    if pg_data:
        BM25_CACHE_HIT_TOTAL.labels(layer="postgres").inc()
        index = BM25Index.from_bytes(pg_data)
        _index_cache[workspace_id] = index
        try:
            await save_bm25_to_redis(workspace_id, pg_data)  # write-back
        except Exception as e:
            logger.warning("Failed to write BM25 back to Redis for workspace %s: %s", workspace_id, e)
        return index

    return None


async def search_bm25(
    workspace_id: str, query: str, top_k: int = 20
) -> List[Dict]:
    """Search BM25 index; rebuilds index if not found."""
    index = await get_index(workspace_id)
    if index is None:
        logger.info("No BM25 index for workspace %s, building...", workspace_id)
        index = await build_and_save_index(workspace_id)
    return index.search(query, top_k=top_k)
