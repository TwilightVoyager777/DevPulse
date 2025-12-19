import pytest
from unittest.mock import AsyncMock, patch

from app.services.bm25_service import BM25Index, _tokenize


def make_chunks(texts):
    return [
        {"id": str(i), "document_id": "doc-1", "content": t, "chunk_index": i}
        for i, t in enumerate(texts)
    ]


def test_tokenize_lowercases_and_splits():
    tokens = _tokenize("Hello, World! This is Python.")
    assert "hello" in tokens
    assert "world" in tokens
    assert "python" in tokens
    assert "," not in tokens


def test_bm25_index_search_returns_relevant():
    chunks = make_chunks([
        "Python is a high-level programming language.",
        "Redis is an in-memory data structure store.",
        "Java uses garbage collection for memory management.",
    ])
    index = BM25Index(chunks)
    results = index.search("Python programming", top_k=2)
    assert len(results) >= 1
    assert results[0]["content"].startswith("Python")


def test_bm25_index_search_empty_index():
    index = BM25Index([])
    results = index.search("anything")
    assert results == []


def test_bm25_index_roundtrip_serialization():
    chunks = make_chunks([
        "Machine learning is a subset of AI.",
        "Deep learning uses neural networks.",
    ])
    index = BM25Index(chunks)
    data = index.to_bytes()
    restored = BM25Index.from_bytes(data)

    original_results = index.search("neural networks", top_k=2)
    restored_results = restored.search("neural networks", top_k=2)

    assert len(original_results) == len(restored_results)
    if original_results:
        assert original_results[0]["content"] == restored_results[0]["content"]


@pytest.mark.asyncio
async def test_search_bm25_builds_index_if_missing(mocker):
    mocker.patch(
        "app.services.bm25_service.get_chunks_for_workspace",
        new_callable=AsyncMock,
        return_value=[
            {"id": "1", "document_id": "d1", "content": "Python rocks", "chunk_index": 0}
        ],
    )
    mocker.patch("app.services.bm25_service.save_bm25_index", new_callable=AsyncMock)
    mocker.patch("app.services.bm25_service.load_bm25_index", new_callable=AsyncMock, return_value=None)
    # Clear cache
    import app.services.bm25_service as bm25_mod
    bm25_mod._index_cache.clear()

    from app.services.bm25_service import search_bm25
    results = await search_bm25("ws-test", "Python", top_k=5)
    assert len(results) >= 1
