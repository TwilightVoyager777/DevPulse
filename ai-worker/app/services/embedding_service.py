import logging
from functools import lru_cache
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    settings = get_settings()
    logger.info("Loading embedding model: %s", settings.embedding_model)
    model = SentenceTransformer(settings.embedding_model)
    logger.info("Embedding model loaded")
    return model


def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Embed a list of texts.
    Returns: np.ndarray of shape (len(texts), embedding_dim), dtype float32.
    """
    if not texts:
        settings = get_settings()
        return np.empty((0, settings.embedding_dim), dtype=np.float32)
    model = _load_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.astype(np.float32)


def embed_query(text: str) -> np.ndarray:
    """Embed a single query string. Returns shape (embedding_dim,)."""
    return embed_texts([text])[0]
