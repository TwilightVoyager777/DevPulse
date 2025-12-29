import pytest
from app.services.retrieval_service import _rrf_score, _reciprocal_rank_fusion


def test_rrf_score_decreases_with_rank():
    assert _rrf_score(0) > _rrf_score(1)
    assert _rrf_score(1) > _rrf_score(10)
    assert _rrf_score(10) > _rrf_score(100)


def test_rrf_score_bounded():
    # All scores between 0 and 1
    for rank in range(100):
        s = _rrf_score(rank)
        assert 0 < s <= 1.0


def test_rrf_fusion_deduplicates():
    bm25 = [
        {"id": "c1", "content": "Python", "document_id": "d1", "chunk_index": 0},
        {"id": "c2", "content": "Redis", "document_id": "d1", "chunk_index": 1},
    ]
    vector = [
        {"id": "c1", "content": "Python", "document_id": "d1", "chunk_index": 0, "score": 0.9, "title": "Doc"},
        {"id": "c3", "content": "Java", "document_id": "d2", "chunk_index": 0, "score": 0.7, "title": "Doc2"},
    ]
    results = _reciprocal_rank_fusion(bm25, vector)
    ids = [r["id"] for r in results]
    # c1 appears in both → deduplicated and ranked higher
    assert ids.count("c1") == 1
    assert ids[0] == "c1"  # appears in both lists → highest RRF score


def test_rrf_fusion_empty_inputs():
    results = _reciprocal_rank_fusion([], [])
    assert results == []


def test_rrf_fusion_bm25_only():
    bm25 = [{"id": "c1", "content": "x", "document_id": "d1", "chunk_index": 0}]
    results = _reciprocal_rank_fusion(bm25, [])
    assert len(results) == 1
    assert results[0]["id"] == "c1"


@pytest.mark.asyncio
async def test_hybrid_search_integrates_services(mocker):
    import numpy as np
    _DOC_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    mocker.patch(
        "app.services.retrieval_service.embed_query",
        return_value=np.zeros(384, dtype=np.float32),
    )
    mocker.patch(
        "app.services.retrieval_service.search_bm25",
        return_value=[
            {"id": "c1", "content": "Python GIL", "document_id": _DOC_ID, "chunk_index": 0}
        ],
    )
    mocker.patch(
        "app.services.retrieval_service.vector_search",
        return_value=[
            {"id": "c1", "content": "Python GIL", "document_id": _DOC_ID,
             "chunk_index": 0, "score": 0.95, "title": "Python Guide"},
        ],
    )
    from app.services.retrieval_service import hybrid_search
    chunks, sources = await hybrid_search("ws-1", "Python GIL")
    assert len(chunks) >= 1
    assert len(sources) >= 1
    assert sources[0].snippet == "Python GIL"
