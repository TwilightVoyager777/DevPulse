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
