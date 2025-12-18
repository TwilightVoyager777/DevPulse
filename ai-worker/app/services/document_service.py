import logging
import re
from typing import List, Dict, Any

import tiktoken
from bs4 import BeautifulSoup

from app.config import get_settings
from app.services.embedding_service import embed_texts
from app.utils.db import save_document_chunks, update_document_status

logger = logging.getLogger(__name__)

# Use cl100k_base tokenizer (GPT-4 / Claude compatible token counts)
_TOKENIZER = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_TOKENIZER.encode(text))


def _parse_content(content: str, source_type: str) -> str:
    """Convert raw content to clean plain text."""
    if source_type == "SO_IMPORT":
        # Stack Overflow HTML → plain text
        soup = BeautifulSoup(content, "lxml")
        # Preserve code blocks with markers
        for code in soup.find_all("code"):
            code.replace_with(f"\n```\n{code.get_text()}\n```\n")
        return soup.get_text(separator="\n").strip()
    # UPLOAD: already plain text or markdown
    return content.strip()


def _chunk_text(text: str, chunk_size: int, overlap: int, min_chars: int) -> List[str]:
    """
    Split text into overlapping token-based chunks.
    Splits on paragraph boundaries first, then token-counts each chunk.
    """
    # Split on double newlines (paragraph boundaries)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    chunks: List[str] = []
    current_tokens = 0
    current_parts: List[str] = []

    for para in paragraphs:
        para_tokens = _count_tokens(para)

        # If single paragraph exceeds chunk_size, split it by sentences
        if para_tokens > chunk_size:
            sentences = re.split(r"(?<=[.!?])\s+", para)
            for sent in sentences:
                sent_tokens = _count_tokens(sent)
                if current_tokens + sent_tokens > chunk_size and current_parts:
                    chunks.append("\n\n".join(current_parts))
                    # Keep last overlap tokens worth of content
                    overlap_parts = _trim_to_tokens(current_parts, overlap)
                    current_parts = overlap_parts
                    current_tokens = sum(_count_tokens(p) for p in current_parts)
                current_parts.append(sent)
                current_tokens += sent_tokens
        else:
            if current_tokens + para_tokens > chunk_size and current_parts:
                chunks.append("\n\n".join(current_parts))
                overlap_parts = _trim_to_tokens(current_parts, overlap)
                current_parts = overlap_parts
                current_tokens = sum(_count_tokens(p) for p in current_parts)
            current_parts.append(para)
            current_tokens += para_tokens

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    # Filter out tiny chunks
    return [c for c in chunks if len(c) >= min_chars]


def _trim_to_tokens(parts: List[str], max_tokens: int) -> List[str]:
    """Keep the trailing parts that fit within max_tokens."""
    result = []
    total = 0
    for part in reversed(parts):
        t = _count_tokens(part)
        if total + t <= max_tokens:
            result.insert(0, part)
            total += t
        else:
            break
    return result


async def ingest_document(
    document_id: str,
    workspace_id: str,
    content: str,
    source_type: str,
    metadata: Dict[str, Any] = None,
) -> int:
    """
    Parse → chunk → embed → store in document_chunks.
    Returns: number of chunks created.
    Raises: Exception (caller should catch and update document status to FAILED).
    """
    settings = get_settings()

    # 1. Parse
    clean_text = _parse_content(content, source_type)
    if not clean_text:
        logger.warning("Empty content for document %s", document_id)
        await update_document_status(document_id, "FAILED", error_message="Empty content after parsing")
        return 0

    # 2. Chunk
    chunks_text = _chunk_text(
        clean_text,
        chunk_size=settings.chunk_size_tokens,
        overlap=settings.chunk_overlap_tokens,
        min_chars=settings.chunk_min_chars,
    )
    if not chunks_text:
        logger.warning("No chunks produced for document %s", document_id)
        await update_document_status(document_id, "FAILED", error_message="No chunks produced")
        return 0

    logger.info("Document %s → %d chunks", document_id, len(chunks_text))

    # 3. Embed (batch)
    embeddings = embed_texts(chunks_text)  # shape: (n_chunks, 384)

    # 4. Store
    chunk_records = [
        {
            "chunk_index": i,
            "content": chunks_text[i],
            "embedding": embeddings[i],
        }
        for i in range(len(chunks_text))
    ]
    await save_document_chunks(document_id, workspace_id, chunk_records)

    # 5. Update document status
    await update_document_status(document_id, "INDEXED", chunk_count=len(chunk_records))

    return len(chunk_records)
