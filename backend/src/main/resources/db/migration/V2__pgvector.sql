CREATE TABLE document_chunks (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    content      TEXT NOT NULL,
    metadata     JSONB,
    embedding    vector(384),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chunks_workspace  ON document_chunks(workspace_id);
CREATE INDEX idx_chunks_document   ON document_chunks(document_id);
CREATE INDEX idx_chunks_content_trgm ON document_chunks USING gin(content gin_trgm_ops);
CREATE INDEX idx_chunks_embedding  ON document_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE bm25_indexes (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id   UUID NOT NULL UNIQUE REFERENCES workspaces(id) ON DELETE CASCADE,
    index_data     BYTEA NOT NULL,
    document_count INTEGER NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
