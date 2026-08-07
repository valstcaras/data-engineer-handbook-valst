-- Setup script for the weather_embeddings table in Lakebase.
-- This table stores vector embeddings for weather document chunks.

-- Ensure pgvector extension is enabled (should already be enabled in Lakebase)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the weather_documents table (if not exists)
-- This is the source table for embeddings
CREATE TABLE IF NOT EXISTS weather_documents (
    id TEXT PRIMARY KEY,
    location TEXT NOT NULL,
    source_type TEXT NOT NULL,  -- 'alert' or 'forecast'
    headline TEXT,
    event TEXT,
    narrative_text TEXT,  -- Main text to embed
    effective_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    severity TEXT,
    urgency TEXT,
    certainty TEXT,
    temperature NUMERIC,
    temperature_unit TEXT,
    wind_speed TEXT,
    wind_direction TEXT,
    payload JSONB NOT NULL,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create indexes on weather_documents
CREATE INDEX IF NOT EXISTS idx_weather_documents_location ON weather_documents (location);
CREATE INDEX IF NOT EXISTS idx_weather_documents_source_type ON weather_documents (source_type);
CREATE INDEX IF NOT EXISTS idx_weather_documents_effective_at ON weather_documents (effective_at);

-- Create the weather_embeddings table
-- Stores vector embeddings for chunked weather document text
CREATE TABLE IF NOT EXISTS weather_embeddings (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES weather_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(384) NOT NULL,  -- 384-dim for sentence-transformers/all-MiniLM-L6-v2
    model_name TEXT NOT NULL DEFAULT 'sentence-transformers/all-MiniLM-L6-v2',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(document_id, chunk_index)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_weather_embeddings_document_id 
    ON weather_embeddings (document_id);

CREATE INDEX IF NOT EXISTS idx_weather_embeddings_created_at 
    ON weather_embeddings (created_at DESC);

-- Create HNSW index for fast vector similarity search
-- HNSW (Hierarchical Navigable Small World) is optimized for high-dimensional vectors
-- vector_cosine_ops: distance metric for cosine similarity
CREATE INDEX IF NOT EXISTS idx_weather_embeddings_vector_hnsw 
    ON weather_embeddings 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Alternative: IVFFlat index (faster to build, slightly slower queries)
-- Uncomment if you prefer IVFFlat over HNSW:
-- CREATE INDEX IF NOT EXISTS idx_weather_embeddings_vector_ivfflat 
--     ON weather_embeddings 
--     USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);

-- Example queries:

-- 1. Find top 5 most similar weather documents to a query embedding
-- (Replace the array with your actual query embedding)
/*
SELECT 
    we.id,
    we.document_id,
    we.chunk_index,
    we.chunk_text,
    wd.location,
    wd.source_type,
    wd.headline,
    1 - (we.embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM weather_embeddings we
JOIN weather_documents wd ON we.document_id = wd.id
ORDER BY we.embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;
*/

-- 2. Get all embeddings for a specific document
/*
SELECT chunk_index, chunk_text, created_at
FROM weather_embeddings
WHERE document_id = 'some-document-id'
ORDER BY chunk_index;
*/

-- 3. Check embedding statistics
/*
SELECT 
    COUNT(*) as total_embeddings,
    COUNT(DISTINCT document_id) as unique_documents,
    AVG(LENGTH(chunk_text)) as avg_chunk_length,
    MIN(created_at) as first_embedding,
    MAX(created_at) as last_embedding
FROM weather_embeddings;
*/

-- 4. Find documents with no embeddings yet
/*
SELECT wd.id, wd.location, wd.source_type, wd.headline, wd.synced_at
FROM weather_documents wd
LEFT JOIN weather_embeddings we ON wd.id = we.document_id
WHERE we.id IS NULL
ORDER BY wd.synced_at DESC;
*/
