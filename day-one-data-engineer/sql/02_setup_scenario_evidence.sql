-- Day One: Data Engineer - Scenario Evidence Table
-- This table stores Stack Overflow content with pgvector embeddings for semantic search

-- Ensure pgvector extension is enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Scenario evidence table with embeddings
CREATE TABLE IF NOT EXISTS scenario_evidence (
    evidence_id TEXT PRIMARY KEY,
    question_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    chunk_text TEXT NOT NULL,  -- The actual text chunk that was embedded
    tags TEXT[],
    score INTEGER,
    view_count INTEGER,
    answer_count INTEGER,
    question_url TEXT,
    category TEXT NOT NULL CHECK (category IN (
        'incident_debugging',
        'data_quality',
        'stakeholder_communication',
        'pipeline_design',
        'performance_optimization'
    )),
    embedding vector(384),  -- sentence-transformers/all-MiniLM-L6-v2 produces 384-dim vectors
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_evidence_embedding ON scenario_evidence 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Index for category filtering
CREATE INDEX IF NOT EXISTS idx_evidence_category ON scenario_evidence (category);

-- Index for question lookup
CREATE INDEX IF NOT EXISTS idx_evidence_question_id ON scenario_evidence (question_id);

-- Optional: skill market signals table (for tracking SO tag trends over time)
CREATE TABLE IF NOT EXISTS skill_market_signals (
    signal_id TEXT PRIMARY KEY,
    tag TEXT NOT NULL,
    month DATE NOT NULL,
    question_count INTEGER NOT NULL,
    avg_score NUMERIC(10, 2),
    avg_views INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tag, month)
);

CREATE INDEX IF NOT EXISTS idx_skill_signals_tag ON skill_market_signals (tag);
CREATE INDEX IF NOT EXISTS idx_skill_signals_month ON skill_market_signals (month);
