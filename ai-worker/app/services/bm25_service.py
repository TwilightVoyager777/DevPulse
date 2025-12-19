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
    """Load all chunks from DB, build BM25 index, persist to bm25_indexes table."""
    chunks = await get_chunks_for_workspace(workspace_id)
    if not chunks:
        logger.info("No chunks for workspace %s, building empty index", workspace_id)

    index = BM25Index(chunks)
    index_bytes = index.to_bytes()
    await save_bm25_index(workspace_id, index_bytes, doc_count=len(chunks))
    _index_cache[workspace_id] = index
    logger.info("BM25 index built for workspace %s: %d chunks", workspace_id, len(chunks))
    return index


async def get_index(workspace_id: str) -> Optional[BM25Index]:
    """Get BM25 index from cache, then DB. Returns None if not found."""
    if workspace_id in _index_cache:
        return _index_cache[workspace_id]

    index_bytes = await load_bm25_index(workspace_id)
    if index_bytes is None:
        return None

    index = BM25Index.from_bytes(index_bytes)
    _index_cache[workspace_id] = index
    return index


async def search_bm25(
    workspace_id: str, query: str, top_k: int = 20
) -> List[Dict]:
    """Search BM25 index; rebuilds index if not found."""
    index = await get_index(workspace_id)
    if index is None:
        logger.info("No BM25 index for workspace %s, building...", workspace_id)
        index = await build_and_save_index(workspace_id)
    return index.search(query, top_k=top_k)
