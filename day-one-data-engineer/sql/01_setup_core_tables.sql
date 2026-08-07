-- Day One: Data Engineer - Core Tables Schema
-- Run this script first to set up the foundational tables in Lakebase Postgres

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    display_name TEXT NOT NULL UNIQUE,
    background_tag TEXT CHECK (background_tag IN ('software_eng', 'analyst', 'student', 'other')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_display_name ON users (display_name);

-- Scenarios table (decision tree definitions)
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'incident_debugging',
        'data_quality',
        'stakeholder_communication',
        'pipeline_design',
        'performance_optimization'
    )),
    difficulty INTEGER NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
    est_minutes INTEGER NOT NULL,
    definition JSONB NOT NULL,  -- The decision tree structure
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scenarios_category ON scenarios (category);
CREATE INDEX IF NOT EXISTS idx_scenarios_active ON scenarios (is_active);

-- Scenario attempts table
CREATE TABLE IF NOT EXISTS scenario_attempts (
    attempt_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    scenario_id INTEGER NOT NULL REFERENCES scenarios(scenario_id),
    status TEXT NOT NULL DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'abandoned')),
    current_node_id TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    enjoyment_score INTEGER CHECK (enjoyment_score BETWEEN 1 AND 5),
    would_do_as_job BOOLEAN,
    CONSTRAINT valid_completion CHECK (
        (status = 'completed' AND completed_at IS NOT NULL) OR
        (status != 'completed' AND completed_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_attempts_user ON scenario_attempts (user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_scenario ON scenario_attempts (scenario_id);
CREATE INDEX IF NOT EXISTS idx_attempts_status ON scenario_attempts (status);

-- Decisions table (records each choice made)
CREATE TABLE IF NOT EXISTS decisions (
    decision_id SERIAL PRIMARY KEY,
    attempt_id INTEGER NOT NULL REFERENCES scenario_attempts(attempt_id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    chosen_option TEXT NOT NULL,
    free_text_answer TEXT,
    competence_score NUMERIC(3, 2) CHECK (competence_score BETWEEN 0 AND 1),
    agent_feedback TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_decisions_attempt ON decisions (attempt_id);

-- Interest profiles table (aggregated from attempts)
CREATE TABLE IF NOT EXISTS interest_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(user_id),
    profile JSONB NOT NULL,  -- {category: {enjoyment: [scores], competence: [scores]}}
    verdict TEXT,  -- AI-generated career recommendation
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Skills table (reference data)
CREATE TABLE IF NOT EXISTS skills (
    skill_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skills_category ON skills (category);

-- Learning recommendations table
CREATE TABLE IF NOT EXISTS learning_recommendations (
    recommendation_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    title TEXT NOT NULL,
    url TEXT,
    reason TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'agent',  -- 'agent' or 'system'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_recommendations_user ON learning_recommendations (user_id);

-- Comments table (optional: for feedback on scenarios)
CREATE TABLE IF NOT EXISTS scenario_comments (
    comment_id SERIAL PRIMARY KEY,
    scenario_id INTEGER NOT NULL REFERENCES scenarios(scenario_id),
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    comment_text TEXT NOT NULL,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_comments_scenario ON scenario_comments (scenario_id);
