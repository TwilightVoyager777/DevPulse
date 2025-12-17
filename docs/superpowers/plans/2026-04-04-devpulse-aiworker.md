# DevPulse Sub-Project 3: AI Worker Implementation Plan

**Goal:** Build the Python AI Worker: Kafka consumer for document ingestion (parse → chunk → embed → pgvector + BM25) and AI task processing (Hybrid RAG retrieval → Claude `claude-sonnet-4-6` streaming → publish TaskStatusEvent back to Kafka). Expose `/health` and `/metrics` (Prometheus) endpoints.

**Architecture:** FastAPI + uvicorn (HTTP layer), confluent-kafka (consumers), asyncpg (PostgreSQL), anthropic SDK (LLM), sentence-transformers all-MiniLM-L6-v2 (embeddings, 384-dim), rank_bm25 (BM25 + pickle serialization to BYTEA), redis-py (task status cache), prometheus-client (/metrics scrape endpoint).

**Tech Stack:** Python 3.11, FastAPI 0.111, uvicorn 0.29, asyncpg 0.29, anthropic 0.28, sentence-transformers 2.7, torch 2.3 (CPU), rank-bm25 0.2.2, confluent-kafka 2.4, redis 5.0, prometheus-client 0.20, tiktoken 0.7, beautifulsoup4 4.12, pytest 8.2, pytest-asyncio 0.23

---

## File Map

| File | Responsibility |
|------|---------------|
| `ai-worker/requirements.txt` | All Python dependencies |
| `ai-worker/app/__init__.py` | Package marker |
| `ai-worker/app/config.py` | Pydantic Settings — all env vars |
| `ai-worker/app/main.py` | FastAPI app, startup/shutdown lifecycle, /health, /metrics |
| `ai-worker/app/models/__init__.py` | Package marker |
| `ai-worker/app/models/schemas.py` | Pydantic models mirroring Java Kafka records |
| `ai-worker/app/utils/__init__.py` | Package marker |
| `ai-worker/app/utils/db.py` | asyncpg pool, all SQL helpers |
| `ai-worker/app/utils/kafka_producer.py` | confluent-kafka Producer — publishes TaskStatusEvent |
| `ai-worker/app/utils/redis_client.py` | redis-py client — task status cache |
| `ai-worker/app/utils/metrics.py` | prometheus-client — 8 custom metrics |
| `ai-worker/app/services/__init__.py` | Package marker |
| `ai-worker/app/services/embedding_service.py` | sentence-transformers all-MiniLM-L6-v2 |
| `ai-worker/app/services/document_service.py` | Parse (md/html/text) → chunk → embed → store |
| `ai-worker/app/services/bm25_service.py` | BM25Okapi build/save/load/search per workspace |
| `ai-worker/app/services/retrieval_service.py` | Hybrid BM25 + pgvector + RRF reranking |
| `ai-worker/app/services/ai_service.py` | Claude streaming, prompt construction, publish chunks |
| `ai-worker/app/consumers/__init__.py` | Package marker |
| `ai-worker/app/consumers/document_consumer.py` | Kafka consumer for document-ingestion |
| `ai-worker/app/consumers/ai_task_consumer.py` | Kafka consumer for ai-tasks |
| `ai-worker/tests/__init__.py` | Package marker |
| `ai-worker/tests/test_embedding_service.py` | Unit tests — embedding shape/type |
| `ai-worker/tests/test_document_service.py` | Unit tests — chunking logic |
| `ai-worker/tests/test_bm25_service.py` | Unit tests — BM25 build/search/persist |
| `ai-worker/tests/test_retrieval_service.py` | Unit tests — RRF fusion logic |
| `ai-worker/tests/test_ai_service.py` | Unit tests — prompt construction, streaming mock |

---

## Tasks

### Task 1: Project setup — requirements.txt, config, main

**Files:**
- Create: `ai-worker/requirements.txt`
- Create: `ai-worker/app/__init__.py`
- Create: `ai-worker/app/config.py`
- Create: `ai-worker/app/main.py`

- [ ] **Step 1: Create requirements.txt**

`ai-worker/requirements.txt`:
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
pydantic==2.7.1
pydantic-settings==2.2.1
confluent-kafka==2.4.0
anthropic==0.28.0
sentence-transformers==2.7.0
torch==2.3.0
asyncpg==0.29.0
redis==5.0.4
prometheus-client==0.20.0
rank-bm25==0.2.2
tiktoken==0.7.0
beautifulsoup4==4.12.3
lxml==5.2.1
numpy==1.26.4
pytest==8.2.0
pytest-asyncio==0.23.6
pytest-mock==3.14.0
httpx==0.27.0
```

- [ ] **Step 2: Create app/__init__.py**

`ai-worker/app/__init__.py`:
```python
```
(empty file)

- [ ] **Step 3: Create app/config.py**

`ai-worker/app/config.py`:
```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://devpulse:devpulse@localhost:5432/devpulse"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "ai-worker"
    kafka_auto_offset_reset: str = "earliest"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_max_tokens: int = 2048

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Chunking
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    chunk_min_chars: int = 100

    # Retrieval
    retrieval_top_k: int = 5
    bm25_candidate_k: int = 20
    vector_candidate_k: int = 20
    rrf_k: int = 60

    # App
    log_level: str = "INFO"
    workers: int = 1

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Create app/main.py**

`ai-worker/app/main.py`:
```python
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.config import get_settings
from app.utils.db import get_pool, close_pool
from app.utils.redis_client import get_redis, close_redis
from app.utils.metrics import APP_INFO
from app.consumers.document_consumer import DocumentConsumer
from app.consumers.ai_task_consumer import AiTaskConsumer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB pool, Redis, start Kafka consumers."""
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level))

    logger.info("Starting AI Worker...")

    # Init DB pool
    await get_pool()
    logger.info("DB pool initialized")

    # Init Redis
    await get_redis()
    logger.info("Redis connected")

    # Start Kafka consumers in background threads
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
    return {"status": "ok", "service": "ai-worker"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return PlainTextResponse(
        content=generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST
    )
```

- [ ] **Step 5: Verify syntax**

```bash
cd ai-worker && python -c "from app.config import get_settings; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add ai-worker/requirements.txt ai-worker/app/__init__.py \
        ai-worker/app/config.py ai-worker/app/main.py
git commit -m "feat(ai-worker): project setup — requirements, config, FastAPI app with health + metrics endpoints"
```

---

### Task 2: Pydantic schemas + DB layer + Kafka producer + Redis client

**Files:**
- Create: `ai-worker/app/models/__init__.py`
- Create: `ai-worker/app/models/schemas.py`
- Create: `ai-worker/app/utils/__init__.py`
- Create: `ai-worker/app/utils/db.py`
- Create: `ai-worker/app/utils/kafka_producer.py`
- Create: `ai-worker/app/utils/redis_client.py`

- [ ] **Step 1: Create schemas.py**

`ai-worker/app/models/schemas.py`:
```python
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class ConversationMessage(BaseModel):
    role: str
    content: str


class DocumentIngestionEvent(BaseModel):
    documentId: uuid.UUID
    workspaceId: uuid.UUID
    sourceType: str          # "UPLOAD" | "SO_IMPORT"
    contentOrPath: str       # raw text content
    metadata: Optional[Dict[str, Any]] = None
    createdAt: datetime


class AiTaskEvent(BaseModel):
    taskId: uuid.UUID
    sessionId: uuid.UUID
    workspaceId: uuid.UUID
    userMessage: str
    conversationHistory: List[ConversationMessage] = Field(default_factory=list)
    createdAt: datetime


class SourceInfo(BaseModel):
    title: str
    score: float
    snippet: str
    documentId: uuid.UUID


class TaskStatusEvent(BaseModel):
    taskId: uuid.UUID
    sessionId: uuid.UUID
    workspaceId: uuid.UUID
    status: str              # "streaming" | "done" | "failed"
    chunk: Optional[str] = None
    isDone: bool = False
    fullResponse: Optional[str] = None
    sources: Optional[List[SourceInfo]] = None
    tokensUsed: Optional[int] = None
    latencyMs: Optional[int] = None
    errorMessage: Optional[str] = None
    userMessageHash: int = 0
```

- [ ] **Step 2: Create utils/db.py**

`ai-worker/app/utils/db.py`:
```python
import asyncpg
import logging
from typing import Optional, List

from app.config import get_settings

logger = logging.getLogger(__name__)
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("asyncpg pool created")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def save_document_chunks(
    document_id: str,
    workspace_id: str,
    chunks: List[dict],   # each: {content, embedding: np.ndarray, chunk_index}
) -> None:
    """Delete old chunks and insert new ones for a document."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM document_chunks WHERE document_id = $1::uuid",
            document_id,
        )
        records = [
            (
                document_id,
                workspace_id,
                c["chunk_index"],
                c["content"],
                "[" + ",".join(str(float(x)) for x in c["embedding"].tolist()) + "]",
            )
            for c in chunks
        ]
        await conn.executemany(
            """INSERT INTO document_chunks
               (document_id, workspace_id, chunk_index, content, embedding)
               VALUES ($1::uuid, $2::uuid, $3, $4, $5::vector)""",
            records,
        )


async def update_document_status(
    document_id: str,
    status: str,
    chunk_count: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if chunk_count is not None:
            await conn.execute(
                """UPDATE documents
                   SET status = $1, chunk_count = $2, indexed_at = NOW()
                   WHERE id = $3::uuid""",
                status, chunk_count, document_id,
            )
        elif error_message:
            await conn.execute(
                """UPDATE documents
                   SET status = $1, error_message = $2
                   WHERE id = $3::uuid""",
                status, error_message, document_id,
            )
        else:
            await conn.execute(
                "UPDATE documents SET status = $1 WHERE id = $2::uuid",
                status, document_id,
            )


async def get_chunks_for_workspace(workspace_id: str) -> List[dict]:
    """Load all chunks for a workspace (for BM25 rebuild)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id::text, document_id::text, content, chunk_index
               FROM document_chunks
               WHERE workspace_id = $1::uuid
               ORDER BY document_id, chunk_index""",
            workspace_id,
        )
        return [dict(r) for r in rows]


async def vector_search(
    workspace_id: str,
    embedding_list: list,
    top_k: int = 20,
) -> List[dict]:
    """Cosine similarity search via pgvector (<=> operator)."""
    pool = await get_pool()
    embedding_str = "[" + ",".join(str(float(x)) for x in embedding_list) + "]"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT dc.id::text, dc.document_id::text, dc.content, dc.chunk_index,
                      1 - (dc.embedding <=> $1::vector) AS score,
                      d.title
               FROM document_chunks dc
               JOIN documents d ON dc.document_id = d.id
               WHERE dc.workspace_id = $2::uuid
                 AND dc.embedding IS NOT NULL
               ORDER BY dc.embedding <=> $1::vector
               LIMIT $3""",
            embedding_str, workspace_id, top_k,
        )
        return [dict(r) for r in rows]


async def save_bm25_index(workspace_id: str, index_bytes: bytes, doc_count: int) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO bm25_indexes (workspace_id, index_data, document_count, updated_at)
               VALUES ($1::uuid, $2, $3, NOW())
               ON CONFLICT (workspace_id)
               DO UPDATE SET index_data = $2, document_count = $3, updated_at = NOW()""",
            workspace_id, index_bytes, doc_count,
        )


async def load_bm25_index(workspace_id: str) -> Optional[bytes]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT index_data FROM bm25_indexes WHERE workspace_id = $1::uuid",
            workspace_id,
        )
        return bytes(row["index_data"]) if row else None
```

- [ ] **Step 3: Create utils/kafka_producer.py**

`ai-worker/app/utils/kafka_producer.py`:
```python
import json
import logging
from typing import Optional

from confluent_kafka import Producer

from app.config import get_settings
from app.models.schemas import TaskStatusEvent

logger = logging.getLogger(__name__)
_producer: Optional[Producer] = None

TOPIC_TASK_STATUS = "task-status"


def get_producer() -> Producer:
    global _producer
    if _producer is None:
        settings = get_settings()
        _producer = Producer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "client.id": "ai-worker-producer",
            "acks": "1",
            "retries": 3,
            "retry.backoff.ms": 500,
        })
        logger.info("Kafka producer created")
    return _producer


def _delivery_callback(err, msg):
    if err:
        logger.error("Kafka delivery failed for topic %s: %s", msg.topic(), err)


def publish_task_status(event: TaskStatusEvent) -> None:
    producer = get_producer()
    payload = event.model_dump_json()
    producer.produce(
        TOPIC_TASK_STATUS,
        key=str(event.taskId),
        value=payload.encode("utf-8"),
        callback=_delivery_callback,
    )
    producer.poll(0)  # trigger delivery callbacks without blocking


def flush_producer() -> None:
    if _producer:
        _producer.flush(timeout=5)
```

- [ ] **Step 4: Create utils/redis_client.py**

`ai-worker/app/utils/redis_client.py`:
```python
import logging
from typing import Optional

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)
_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            decode_responses=True,
        )
        await _redis.ping()
        logger.info("Redis connected")
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def cache_task_status(task_id: str, status_json: str, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.set(f"task:{task_id}", status_json, ex=ttl)


async def mark_event_processed(task_id: str, ttl: int = 3600) -> None:
    r = await get_redis()
    await r.set(f"processed:event:{task_id}", "1", ex=ttl)


async def is_event_processed(task_id: str) -> bool:
    r = await get_redis()
    return await r.exists(f"processed:event:{task_id}") == 1
```

- [ ] **Step 5: Create package markers**

`ai-worker/app/models/__init__.py` — empty  
`ai-worker/app/utils/__init__.py` — empty

- [ ] **Step 6: Verify imports compile**

```bash
cd ai-worker && python -c "
from app.models.schemas import DocumentIngestionEvent, AiTaskEvent, TaskStatusEvent
from app.config import get_settings
print('schemas OK')
"
```

- [ ] **Step 7: Commit**

```bash
git add ai-worker/app/models/ ai-worker/app/utils/
git commit -m "feat(ai-worker): schemas (Kafka event models), DB layer, Kafka producer, Redis client"
```

---

### Task 3: Embedding service + tests

**Files:**
- Create: `ai-worker/app/services/__init__.py`
- Create: `ai-worker/app/services/embedding_service.py`
- Create: `ai-worker/tests/__init__.py`
- Create: `ai-worker/tests/test_embedding_service.py`

- [ ] **Step 1: Create embedding_service.py**

`ai-worker/app/services/embedding_service.py`:
```python
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
```

- [ ] **Step 2: Create tests/test_embedding_service.py**

`ai-worker/tests/test_embedding_service.py`:
```python
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
```

- [ ] **Step 3: Run tests**

```bash
cd ai-worker && python -m pytest tests/test_embedding_service.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add ai-worker/app/services/ ai-worker/tests/
git commit -m "feat(ai-worker): embedding service — all-MiniLM-L6-v2, normalize, batch + single query"
```

---

### Task 4: Document service (parse, chunk, embed, store) + tests

**Files:**
- Create: `ai-worker/app/services/document_service.py`
- Create: `ai-worker/tests/test_document_service.py`

- [ ] **Step 1: Create document_service.py**

`ai-worker/app/services/document_service.py`:
```python
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
```

- [ ] **Step 2: Create tests/test_document_service.py**

`ai-worker/tests/test_document_service.py`:
```python
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
```

- [ ] **Step 3: Run tests**

```bash
cd ai-worker && python -m pytest tests/test_document_service.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add ai-worker/app/services/document_service.py \
        ai-worker/tests/test_document_service.py
git commit -m "feat(ai-worker): document service — parse (md/html), token-based chunking with overlap, embed+store"
```

---

### Task 5: BM25 service (build, persist, load, search) + tests

**Files:**
- Create: `ai-worker/app/services/bm25_service.py`
- Create: `ai-worker/tests/test_bm25_service.py`

- [ ] **Step 1: Create bm25_service.py**

`ai-worker/app/services/bm25_service.py`:
```python
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
```

- [ ] **Step 2: Create tests/test_bm25_service.py**

`ai-worker/tests/test_bm25_service.py`:
```python
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
```

- [ ] **Step 3: Run tests**

```bash
cd ai-worker && python -m pytest tests/test_bm25_service.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add ai-worker/app/services/bm25_service.py \
        ai-worker/tests/test_bm25_service.py
git commit -m "feat(ai-worker): BM25 service — build/persist/load/search per workspace, pickle serialization"
```

---

### Task 6: Retrieval service (Hybrid BM25 + pgvector + RRF) + tests

**Files:**
- Create: `ai-worker/app/services/retrieval_service.py`
- Create: `ai-worker/tests/test_retrieval_service.py`

- [ ] **Step 1: Create retrieval_service.py**

`ai-worker/app/services/retrieval_service.py`:
```python
import logging
from typing import List, Dict, Tuple

from app.config import get_settings
from app.models.schemas import SourceInfo
from app.services.embedding_service import embed_query
from app.services.bm25_service import search_bm25
from app.utils.db import vector_search

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

    # Parallel-ish: BM25 is sync (in-memory), vector is async DB call
    query_embedding = embed_query(query)

    bm25_results = await search_bm25(
        workspace_id, query, top_k=settings.bm25_candidate_k
    )
    vector_results = await vector_search(
        workspace_id, query_embedding.tolist(), top_k=settings.vector_candidate_k
    )

    logger.debug(
        "BM25: %d results, Vector: %d results for workspace %s",
        len(bm25_results), len(vector_results), workspace_id,
    )

    # RRF fusion
    fused = _reciprocal_rank_fusion(
        bm25_results, vector_results, rrf_k=settings.rrf_k
    )[:top_k]

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
```

- [ ] **Step 2: Create tests/test_retrieval_service.py**

`ai-worker/tests/test_retrieval_service.py`:
```python
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
    mocker.patch(
        "app.services.retrieval_service.embed_query",
        return_value=np.zeros(384, dtype=np.float32),
    )
    mocker.patch(
        "app.services.retrieval_service.search_bm25",
        return_value=[
            {"id": "c1", "content": "Python GIL", "document_id": "d1", "chunk_index": 0}
        ],
    )
    mocker.patch(
        "app.services.retrieval_service.vector_search",
        return_value=[
            {"id": "c1", "content": "Python GIL", "document_id": "d1",
             "chunk_index": 0, "score": 0.95, "title": "Python Guide"},
        ],
    )
    from app.services.retrieval_service import hybrid_search
    chunks, sources = await hybrid_search("ws-1", "Python GIL")
    assert len(chunks) >= 1
    assert len(sources) >= 1
    assert sources[0].snippet == "Python GIL"
```

- [ ] **Step 3: Run tests**

```bash
cd ai-worker && python -m pytest tests/test_retrieval_service.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add ai-worker/app/services/retrieval_service.py \
        ai-worker/tests/test_retrieval_service.py
git commit -m "feat(ai-worker): retrieval service — hybrid BM25+pgvector with RRF fusion, top-k sources"
```

---

### Task 7: AI service (Claude streaming) + tests

**Files:**
- Create: `ai-worker/app/services/ai_service.py`
- Create: `ai-worker/tests/test_ai_service.py`

- [ ] **Step 1: Create ai_service.py**

`ai-worker/app/services/ai_service.py`:
```python
import logging
import time
from typing import List, AsyncIterator

import anthropic

from app.config import get_settings
from app.models.schemas import (
    AiTaskEvent,
    TaskStatusEvent,
    SourceInfo,
    ConversationMessage,
)
from app.services.retrieval_service import hybrid_search
from app.utils.kafka_producer import publish_task_status
from app.utils.redis_client import cache_task_status

logger = logging.getLogger(__name__)

_SYSTEM_TEMPLATE = """\
You are DevPulse, an expert AI assistant for software developers.
Answer questions based on the provided context documents.
If the context does not contain enough information, say so clearly.
Always cite relevant information from the context.

Context documents:
{context}
"""


def _build_messages(
    user_message: str,
    history: List[ConversationMessage],
) -> List[dict]:
    """Build Anthropic messages list from conversation history + new message."""
    messages = []
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def _build_system_prompt(chunks: List[dict]) -> str:
    if not chunks:
        return "You are DevPulse, an expert AI assistant for software developers. Answer based on your training knowledge."
    context_parts = []
    for i, chunk in enumerate(chunks[:5], 1):
        title = chunk.get("title", "Unknown")
        content = chunk["content"][:1000]  # limit per-chunk context
        context_parts.append(f"[{i}] {title}\n{content}")
    context = "\n\n---\n\n".join(context_parts)
    return _SYSTEM_TEMPLATE.format(context=context)


async def process_ai_task(event: AiTaskEvent) -> None:
    """
    Full RAG + LLM pipeline:
    1. Hybrid retrieval → top-k chunks
    2. Build prompt
    3. Stream Claude response
    4. Publish TaskStatusEvent chunks + final done event
    """
    settings = get_settings()
    start_ms = int(time.time() * 1000)
    task_id_str = str(event.taskId)

    # 1. Retrieve context
    try:
        chunks, sources = await hybrid_search(
            str(event.workspaceId), event.userMessage
        )
    except Exception as e:
        logger.error("Retrieval failed for task %s: %s", task_id_str, e)
        chunks, sources = [], []

    # 2. Build prompt
    system_prompt = _build_system_prompt(chunks)
    messages = _build_messages(event.userMessage, event.conversationHistory)

    # 3. Stream Claude
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    full_response = ""
    tokens_used = None

    try:
        async with client.messages.stream(
            model=settings.anthropic_model,
            max_tokens=settings.anthropic_max_tokens,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                # Publish streaming chunk
                chunk_event = TaskStatusEvent(
                    taskId=event.taskId,
                    sessionId=event.sessionId,
                    workspaceId=event.workspaceId,
                    status="streaming",
                    chunk=text,
                    isDone=False,
                    userMessageHash=hash(event.userMessage) & 0x7FFFFFFF,
                )
                publish_task_status(chunk_event)

            # Get final usage
            final_msg = await stream.get_final_message()
            tokens_used = final_msg.usage.input_tokens + final_msg.usage.output_tokens

    except anthropic.APIError as e:
        logger.error("Anthropic API error for task %s: %s", task_id_str, e)
        error_event = TaskStatusEvent(
            taskId=event.taskId,
            sessionId=event.sessionId,
            workspaceId=event.workspaceId,
            status="failed",
            isDone=True,
            errorMessage=str(e),
            userMessageHash=hash(event.userMessage) & 0x7FFFFFFF,
        )
        publish_task_status(error_event)
        return

    # 4. Publish done event
    latency_ms = int(time.time() * 1000) - start_ms
    done_event = TaskStatusEvent(
        taskId=event.taskId,
        sessionId=event.sessionId,
        workspaceId=event.workspaceId,
        status="done",
        isDone=True,
        fullResponse=full_response,
        sources=sources,
        tokensUsed=tokens_used,
        latencyMs=latency_ms,
        userMessageHash=hash(event.userMessage) & 0x7FFFFFFF,
    )
    publish_task_status(done_event)

    # Cache the response for circuit breaker fallback
    try:
        status_json = done_event.model_dump_json()
        await cache_task_status(task_id_str, status_json)
    except Exception as e:
        logger.warning("Failed to cache task status: %s", e)

    logger.info(
        "Task %s completed: %d tokens, %d ms, %d sources",
        task_id_str, tokens_used or 0, latency_ms, len(sources),
    )
```

- [ ] **Step 2: Create tests/test_ai_service.py**

`ai-worker/tests/test_ai_service.py`:
```python
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import AiTaskEvent, ConversationMessage
from app.services.ai_service import _build_messages, _build_system_prompt


def make_event(**kwargs):
    defaults = dict(
        taskId=uuid.uuid4(),
        sessionId=uuid.uuid4(),
        workspaceId=uuid.uuid4(),
        userMessage="What is Python GIL?",
        conversationHistory=[],
        createdAt=datetime.utcnow(),
    )
    defaults.update(kwargs)
    return AiTaskEvent(**defaults)


def test_build_messages_no_history():
    messages = _build_messages("What is Redis?", [])
    assert messages == [{"role": "user", "content": "What is Redis?"}]


def test_build_messages_with_history():
    history = [
        ConversationMessage(role="user", content="Hi"),
        ConversationMessage(role="assistant", content="Hello!"),
    ]
    messages = _build_messages("What is Redis?", history)
    assert len(messages) == 3
    assert messages[-1] == {"role": "user", "content": "What is Redis?"}
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_build_system_prompt_with_chunks():
    chunks = [
        {"title": "Python Guide", "content": "Python is a programming language.", "id": "c1", "document_id": "d1", "chunk_index": 0},
    ]
    prompt = _build_system_prompt(chunks)
    assert "Python Guide" in prompt
    assert "Python is a programming language." in prompt
    assert "Context documents" in prompt


def test_build_system_prompt_no_chunks():
    prompt = _build_system_prompt([])
    assert "training knowledge" in prompt


@pytest.mark.asyncio
async def test_process_ai_task_publishes_done_event(mocker):
    event = make_event()

    # Mock retrieval
    mocker.patch(
        "app.services.ai_service.hybrid_search",
        return_value=([], []),
    )

    # Mock Anthropic streaming
    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)

    async def fake_text_stream():
        for token in ["Paris ", "is ", "the ", "answer."]:
            yield token

    mock_stream.text_stream = fake_text_stream()
    mock_final = MagicMock()
    mock_final.usage.input_tokens = 50
    mock_final.usage.output_tokens = 20
    mock_stream.get_final_message = AsyncMock(return_value=mock_final)

    mock_client = AsyncMock()
    mock_client.messages.stream.return_value = mock_stream

    mocker.patch("app.services.ai_service.anthropic.AsyncAnthropic", return_value=mock_client)

    published = []
    mocker.patch(
        "app.services.ai_service.publish_task_status",
        side_effect=lambda e: published.append(e),
    )
    mocker.patch("app.services.ai_service.cache_task_status", new_callable=AsyncMock)

    from app.services.ai_service import process_ai_task
    await process_ai_task(event)

    # Should have streaming chunks + 1 done event
    assert len(published) >= 2
    done_events = [e for e in published if e.isDone]
    assert len(done_events) == 1
    assert done_events[0].status == "done"
    assert "Paris" in done_events[0].fullResponse
    assert done_events[0].tokensUsed == 70


@pytest.mark.asyncio
async def test_process_ai_task_handles_api_error(mocker):
    event = make_event()
    mocker.patch("app.services.ai_service.hybrid_search", return_value=([], []))

    mock_client = AsyncMock()
    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(side_effect=Exception("API Error"))
    mock_client.messages.stream.return_value = mock_stream
    mocker.patch("app.services.ai_service.anthropic.AsyncAnthropic", return_value=mock_client)

    published = []
    mocker.patch("app.services.ai_service.publish_task_status", side_effect=lambda e: published.append(e))

    from app.services.ai_service import process_ai_task
    await process_ai_task(event)

    failed = [e for e in published if e.status == "failed"]
    assert len(failed) == 1
```

- [ ] **Step 3: Run tests**

```bash
cd ai-worker && python -m pytest tests/test_ai_service.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add ai-worker/app/services/ai_service.py \
        ai-worker/tests/test_ai_service.py
git commit -m "feat(ai-worker): AI service — Claude claude-sonnet-4-6 streaming, RAG prompt, publish chunks + done event"
```

---

### Task 8: Kafka consumers + Prometheus metrics

**Files:**
- Create: `ai-worker/app/consumers/__init__.py`
- Create: `ai-worker/app/consumers/document_consumer.py`
- Create: `ai-worker/app/consumers/ai_task_consumer.py`
- Create: `ai-worker/app/utils/metrics.py`

- [ ] **Step 1: Create utils/metrics.py**

`ai-worker/app/utils/metrics.py`:
```python
from prometheus_client import Counter, Histogram, Gauge, Info

# App info gauge
APP_INFO = Info("devpulse_ai_worker", "AI Worker build info")

# Document ingestion
DOCS_INGESTED_TOTAL = Counter(
    "devpulse_docs_ingested_total",
    "Total documents ingested",
    ["status"],  # "success" | "failed"
)

CHUNKS_CREATED_TOTAL = Counter(
    "devpulse_chunks_created_total",
    "Total chunks created during ingestion",
)

INGESTION_DURATION_SECONDS = Histogram(
    "devpulse_ingestion_duration_seconds",
    "Document ingestion duration in seconds",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# AI tasks
AI_TASKS_TOTAL = Counter(
    "devpulse_ai_tasks_total",
    "Total AI tasks processed",
    ["status"],  # "success" | "failed"
)

AI_TASK_DURATION_SECONDS = Histogram(
    "devpulse_ai_task_duration_seconds",
    "AI task end-to-end duration (retrieval + LLM) in seconds",
    buckets=[1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0],
)

TOKENS_USED_TOTAL = Counter(
    "devpulse_tokens_used_total",
    "Total Anthropic tokens consumed",
)

# Retrieval
RETRIEVAL_SOURCES_COUNT = Histogram(
    "devpulse_retrieval_sources_count",
    "Number of sources returned per retrieval",
    buckets=[0, 1, 2, 3, 4, 5, 10],
)

# Kafka
KAFKA_MESSAGES_CONSUMED_TOTAL = Counter(
    "devpulse_kafka_messages_consumed_total",
    "Total Kafka messages consumed",
    ["topic", "status"],  # status: "success" | "error"
)
```

- [ ] **Step 2: Create consumers/document_consumer.py**

`ai-worker/app/consumers/document_consumer.py`:
```python
import asyncio
import json
import logging
import time

from confluent_kafka import Consumer, KafkaError

from app.config import get_settings
from app.models.schemas import DocumentIngestionEvent
from app.services.document_service import ingest_document
from app.services.bm25_service import build_and_save_index
from app.utils.metrics import (
    DOCS_INGESTED_TOTAL,
    CHUNKS_CREATED_TOTAL,
    INGESTION_DURATION_SECONDS,
    KAFKA_MESSAGES_CONSUMED_TOTAL,
)

logger = logging.getLogger(__name__)

TOPIC = "document-ingestion"


class DocumentConsumer:
    def __init__(self):
        self._running = False
        self._consumer: Consumer = None

    def _create_consumer(self) -> Consumer:
        settings = get_settings()
        return Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id + "-document",
            "auto.offset.reset": settings.kafka_auto_offset_reset,
            "enable.auto.commit": False,
        })

    async def start(self) -> None:
        self._running = True
        self._consumer = self._create_consumer()
        self._consumer.subscribe([TOPIC])
        logger.info("Document consumer started, subscribed to %s", TOPIC)

        loop = asyncio.get_event_loop()
        while self._running:
            msg = await loop.run_in_executor(
                None, lambda: self._consumer.poll(timeout=1.0)
            )
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("Document consumer error: %s", msg.error())
                KAFKA_MESSAGES_CONSUMED_TOTAL.labels(
                    topic=TOPIC, status="error"
                ).inc()
                continue

            await self._handle_message(msg)

        self._consumer.close()
        logger.info("Document consumer stopped")

    def stop(self) -> None:
        self._running = False

    async def _handle_message(self, msg) -> None:
        start = time.time()
        try:
            event = DocumentIngestionEvent.model_validate_json(msg.value().decode("utf-8"))
            logger.info(
                "Ingesting document %s (workspace=%s, type=%s)",
                event.documentId, event.workspaceId, event.sourceType,
            )

            chunk_count = await ingest_document(
                document_id=str(event.documentId),
                workspace_id=str(event.workspaceId),
                content=event.contentOrPath,
                source_type=event.sourceType,
                metadata=event.metadata,
            )

            # Rebuild BM25 index for the workspace after new document
            if chunk_count > 0:
                await build_and_save_index(str(event.workspaceId))

            duration = time.time() - start
            DOCS_INGESTED_TOTAL.labels(status="success").inc()
            CHUNKS_CREATED_TOTAL.inc(chunk_count)
            INGESTION_DURATION_SECONDS.observe(duration)
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="success").inc()

            self._consumer.commit(msg)
            logger.info(
                "Document %s ingested: %d chunks in %.2fs",
                event.documentId, chunk_count, duration,
            )

        except Exception as e:
            logger.exception("Failed to process document ingestion: %s", e)
            DOCS_INGESTED_TOTAL.labels(status="failed").inc()
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="error").inc()
            self._consumer.commit(msg)  # Commit to avoid reprocessing bad messages
```

- [ ] **Step 3: Create consumers/ai_task_consumer.py**

`ai-worker/app/consumers/ai_task_consumer.py`:
```python
import asyncio
import logging
import time

from confluent_kafka import Consumer, KafkaError

from app.config import get_settings
from app.models.schemas import AiTaskEvent
from app.services.ai_service import process_ai_task
from app.utils.metrics import (
    AI_TASKS_TOTAL,
    AI_TASK_DURATION_SECONDS,
    KAFKA_MESSAGES_CONSUMED_TOTAL,
)

logger = logging.getLogger(__name__)

TOPIC = "ai-tasks"


class AiTaskConsumer:
    def __init__(self):
        self._running = False
        self._consumer: Consumer = None

    def _create_consumer(self) -> Consumer:
        settings = get_settings()
        return Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id + "-ai-task",
            "auto.offset.reset": settings.kafka_auto_offset_reset,
            "enable.auto.commit": False,
        })

    async def start(self) -> None:
        self._running = True
        self._consumer = self._create_consumer()
        self._consumer.subscribe([TOPIC])
        logger.info("AI task consumer started, subscribed to %s", TOPIC)

        loop = asyncio.get_event_loop()
        while self._running:
            msg = await loop.run_in_executor(
                None, lambda: self._consumer.poll(timeout=1.0)
            )
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error("AI task consumer error: %s", msg.error())
                KAFKA_MESSAGES_CONSUMED_TOTAL.labels(
                    topic=TOPIC, status="error"
                ).inc()
                continue

            await self._handle_message(msg)

        self._consumer.close()
        logger.info("AI task consumer stopped")

    def stop(self) -> None:
        self._running = False

    async def _handle_message(self, msg) -> None:
        start = time.time()
        try:
            event = AiTaskEvent.model_validate_json(msg.value().decode("utf-8"))
            logger.info(
                "Processing AI task %s (session=%s)",
                event.taskId, event.sessionId,
            )

            await process_ai_task(event)

            duration = time.time() - start
            AI_TASKS_TOTAL.labels(status="success").inc()
            AI_TASK_DURATION_SECONDS.observe(duration)
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="success").inc()
            self._consumer.commit(msg)

        except Exception as e:
            logger.exception("Failed to process AI task: %s", e)
            AI_TASKS_TOTAL.labels(status="failed").inc()
            KAFKA_MESSAGES_CONSUMED_TOTAL.labels(topic=TOPIC, status="error").inc()
            self._consumer.commit(msg)
```

- [ ] **Step 4: Create consumers/__init__.py**

Empty file.

- [ ] **Step 5: Verify full compilation**

```bash
cd ai-worker && python -c "
from app.main import app
from app.consumers.document_consumer import DocumentConsumer
from app.consumers.ai_task_consumer import AiTaskConsumer
from app.utils.metrics import APP_INFO
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 6: Run all tests**

```bash
cd ai-worker && python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add ai-worker/app/consumers/ ai-worker/app/utils/metrics.py
git commit -m "feat(ai-worker): Kafka consumers (document-ingestion + ai-tasks) and 8 Prometheus metrics"
```

---

## Self-Review Checklist

| Requirement | Task |
|-------------|------|
| Consume `document-ingestion` → parse → chunk → embed → pgvector | Task 4, 8 |
| BM25 index per workspace, persisted to `bm25_indexes` BYTEA | Task 5, 8 |
| Hybrid retrieval: BM25 + cosine similarity + RRF | Task 6 |
| Claude `claude-sonnet-4-6` streaming | Task 7 |
| Streaming: publish `TaskStatusEvent` chunk by chunk to `task-status` | Task 7 |
| Final done event: fullResponse, sources, tokensUsed, latencyMs | Task 7 |
| Redis: cache task status for circuit breaker fallback | Task 7 |
| `/health` endpoint | Task 1 |
| `/metrics` Prometheus endpoint | Task 1, 8 |
| 8 custom Prometheus metrics | Task 8 |
| pytest tests: embedding, chunking, BM25, RRF, AI service | Tasks 3-7 |
| `sentence-transformers all-MiniLM-L6-v2` (384-dim) | Task 3 |
| asyncpg pool for PostgreSQL | Task 2 |
| confluent-kafka consumer with manual commit | Task 8 |
