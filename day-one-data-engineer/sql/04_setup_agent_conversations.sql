-- Day One: Data Engineer - Agent Conversations Table
-- Run this script to enable persistent conversation storage for AI agent

-- Agent conversations table (replaces in-memory CONVERSATIONS dict)
CREATE TABLE IF NOT EXISTS agent_conversations (
    conversation_id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(user_id),
    attempt_id TEXT REFERENCES scenario_attempts(attempt_id),
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_agent_conversations_user_id ON agent_conversations (user_id);
CREATE INDEX IF NOT EXISTS idx_agent_conversations_attempt_id ON agent_conversations (attempt_id);
CREATE INDEX IF NOT EXISTS idx_agent_conversations_updated_at ON agent_conversations (updated_at DESC);

-- Trigger to automatically update updated_at
CREATE OR REPLACE FUNCTION update_agent_conversation_timestamp()
RETURNS TRIGGER AS $func$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$func$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_agent_conversation_timestamp
    BEFORE UPDATE ON agent_conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_agent_conversation_timestamp();

-- Comment for documentation
COMMENT ON TABLE agent_conversations IS 'Stores AI agent conversation history with messages in JSONB format';
COMMENT ON COLUMN agent_conversations.messages IS 'Array of message objects with role, content, and timestamps';
