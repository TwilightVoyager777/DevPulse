import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from app.services.embedding_service import embed_texts, embed_query


@pytest.fixture(autouse=True)
def mock_model():
    """Mock SentenceTransformer to avoid downloading weights in CI."""
    mock = MagicMock()
    # Return deterministic fake embeddings
    mock.encode.side_effect = lambda texts, **kwargs: np.random.randn(
        len(texts), 384
    ).astype(np.float32)
    with patch("app.services.embedding_service._load_model", return_value=mock):
        # Clear lru_cache so the mock is used
        from app.services import embedding_service
        embedding_service._load_model.cache_clear()
        yield mock


def test_embed_texts_returns_correct_shape():
    texts = ["What is Python?", "How does Redis work?", "Explain Java GC"]
    result = embed_texts(texts)
    assert result.shape == (3, 384)
    assert result.dtype == np.float32


def test_embed_texts_empty_input():
    result = embed_texts([])
    assert result.shape == (0, 384)


def test_embed_query_returns_1d():
    result = embed_query("Hello world")
    assert result.shape == (384,)
    assert result.dtype == np.float32


def test_embed_texts_calls_model_with_normalize():
    texts = ["test"]
    embed_texts(texts)
    from app.services.embedding_service import _load_model
    model = _load_model()
    model.encode.assert_called_once_with(texts, normalize_embeddings=True, show_progress_bar=False)
