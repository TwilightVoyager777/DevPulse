import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import numpy as np

from app.services.document_service import _parse_content, _chunk_text, _count_tokens


def test_parse_content_plain_text():
    text = "Hello world.\n\nThis is a test."
    result = _parse_content(text, "UPLOAD")
    assert "Hello world" in result
    assert result == text.strip()


def test_parse_content_so_html():
    html = "<p>How do I use Python?</p><code>print('hello')</code>"
    result = _parse_content(html, "SO_IMPORT")
    assert "How do I use Python?" in result
    assert "print('hello')" in result
    assert "<p>" not in result


def test_chunk_text_splits_large_text():
    # 3 paragraphs, each ~100 tokens → should produce multiple chunks with small chunk_size
    para = "This is a test sentence with some words. " * 15  # ~120 tokens
    text = f"{para}\n\n{para}\n\n{para}"
    chunks = _chunk_text(text, chunk_size=150, overlap=20, min_chars=50)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert _count_tokens(chunk) <= 200  # allow some slack


def test_chunk_text_short_text_stays_single_chunk():
    text = "Short text. Just one paragraph."
    chunks = _chunk_text(text, chunk_size=512, overlap=64, min_chars=10)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_filters_tiny_chunks():
    text = "A.\n\nThis is a real paragraph with actual content worth embedding."
    chunks = _chunk_text(text, chunk_size=512, overlap=64, min_chars=30)
    # "A." is 2 chars, filtered out
    for chunk in chunks:
        assert len(chunk) >= 30


@pytest.mark.asyncio
async def test_ingest_document_calls_store(mocker):
    mocker.patch(
        "app.services.document_service.embed_texts",
        return_value=np.zeros((2, 384), dtype=np.float32),
    )
    mock_save = mocker.patch(
        "app.services.document_service.save_document_chunks",
        new_callable=AsyncMock,
    )
    mock_update = mocker.patch(
        "app.services.document_service.update_document_status",
        new_callable=AsyncMock,
    )

    from app.services.document_service import ingest_document

    # Long enough to produce chunks
    content = "Python is a high-level language. " * 100
    count = await ingest_document(
        document_id="doc-1",
        workspace_id="ws-1",
        content=content,
        source_type="UPLOAD",
    )

    assert count > 0
    mock_save.assert_called_once()
    mock_update.assert_called_once_with("doc-1", "INDEXED", chunk_count=count)
