import logging
import time
from typing import List, Dict, Tuple

from app.config import get_settings
from app.models.schemas import SourceInfo
from app.services.embedding_service import embed_query
from app.services.bm25_service import search_bm25
from app.utils.db import vector_search
from app.utils.metrics import RETRIEVAL_LATENCY_SECONDS, RETRIEVAL_TOP_SCORE, RETRIEVAL_SOURCES_COUNT

logger = logging.getLogger(__name__)


def _rrf_score(rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score."""
    return 1.0 / (k + rank + 1)


def _reciprocal_rank_fusion(
    bm25_results: List[Dict],
    vector_results: List[Dict],
    rrf_k: int = 60,
) -> List[Dict]:
    """
    Merge BM25 and vector search results via RRF.
    Returns deduplicated list sorted by fused score, highest first.
    """
    scores: Dict[str, float] = {}
    meta: Dict[str, Dict] = {}

    # BM25 rankings
    for rank, item in enumerate(bm25_results):
        chunk_id = item["id"]
        scores[chunk_id] = scores.get(chunk_id, 0.0) + _rrf_score(rank, rrf_k)
        meta[chunk_id] = item

    # Vector rankings
    for rank, item in enumerate(vector_results):
        chunk_id = item["id"]
        scores[chunk_id] = scores.get(chunk_id, 0.0) + _rrf_score(rank, rrf_k)
        meta.setdefault(chunk_id, item)

    # Sort by fused score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    results = []
    for chunk_id, rrf in ranked:
        entry = dict(meta[chunk_id])
        entry["rrf_score"] = rrf
        results.append(entry)
    return results


async def hybrid_search(
    workspace_id: str,
    query: str,
    top_k: int = None,
) -> Tuple[List[Dict], List[SourceInfo]]:
    """
    Hybrid search: BM25 + pgvector → RRF → top_k chunks.
    Returns: (raw_chunks, source_info_list)
    """
    settings = get_settings()
    if top_k is None:
        top_k = settings.retrieval_top_k

    query_embedding = embed_query(query)

    t0 = time.perf_counter()
    bm25_results = await search_bm25(
        workspace_id, query, top_k=settings.bm25_candidate_k
    )
    RETRIEVAL_LATENCY_SECONDS.labels(method="bm25").observe(time.perf_counter() - t0)

    t1 = time.perf_counter()
    vector_results = await vector_search(
        workspace_id, query_embedding.tolist(), top_k=settings.vector_candidate_k
    )
    RETRIEVAL_LATENCY_SECONDS.labels(method="vector").observe(time.perf_counter() - t1)

    logger.debug(
        "BM25: %d results, Vector: %d results for workspace %s",
        len(bm25_results), len(vector_results), workspace_id,
    )

    t2 = time.perf_counter()
    fused = _reciprocal_rank_fusion(
        bm25_results, vector_results, rrf_k=settings.rrf_k
    )[:top_k]
    RETRIEVAL_LATENCY_SECONDS.labels(method="rrf").observe(time.perf_counter() - t2)

    if fused:
        RETRIEVAL_TOP_SCORE.observe(fused[0]["rrf_score"])
    RETRIEVAL_SOURCES_COUNT.observe(len(fused))

    # Build SourceInfo list
    sources = [
        SourceInfo(
            title=chunk.get("title", "Unknown"),
            score=round(chunk["rrf_score"], 4),
            snippet=chunk["content"][:300],
            documentId=chunk["document_id"],
        )
        for chunk in fused
    ]

    return fused, sources
