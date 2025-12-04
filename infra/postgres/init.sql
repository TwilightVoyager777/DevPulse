-- Required for 384-dimensional vector embeddings (all-MiniLM-L6-v2 output)
CREATE EXTENSION IF NOT EXISTS vector;
-- Required for BM25 fallback full-text trigram search on document_chunks.content
CREATE EXTENSION IF NOT EXISTS pg_trgm;
