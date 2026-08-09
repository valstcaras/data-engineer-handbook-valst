# AI Agent Setup for Day One: Data Engineer

## ✅ READY TO USE!

Your AI agent is **already configured** with Databricks Foundation Models:

* ✅ **No API keys required**
* ✅ **No external dependencies**
* ✅ **Full tool calling support**
* ✅ **Uses your Databricks workspace authentication**

🚀 **Start here:** [QUICK_START.md](./QUICK_START.md) for 3-step integration

---

## Architecture Decision: MCP vs Direct Integration

### ✅ Recommended: Direct LLM Integration (What We've Built)

**You should use this approach** because:
- Your app is entirely within Databricks
- You need tight integration with your Flask web app
- You want both read AND write operations
- You control both the agent and the data
- Simpler deployment and authentication

**Architecture:**
```
User Browser
    ↓
Flask App (app.py)
    ↓
Agent Runner (agent_runner.py) ← LLM with Function Calling
    ↓
Agent Tools (agent_tools.py) ← Your existing tool functions
    ↓
Lakebase Postgres Database
```


## Setup Instructions

### 1. Setup (✅ Already Done!)

**Your agent is already configured to use Databricks Foundation Models!**

✅ No API keys needed
✅ No external LLM dependencies
✅ Uses your existing Databricks workspace authentication
✅ No extra cost beyond your Databricks usage

**Available Models:**
- `databricks-meta-llama-3-1-70b-instruct` (default, recommended for tool calling)
- `databricks-meta-llama-3-1-405b-instruct` (most capable)
- `databricks-dbrx-instruct`
- `databricks-mixtral-8x7b-instruct`

The agent is already configured in `agent_runner.py` - no changes needed!

### 2. Alternative: Use External LLM (Optional)

If you prefer OpenAI or Anthropic instead:

<details>
<summary>Click to see OpenAI setup</summary>

```python
# Install: pip install openai
import openai

class ScenarioAgent:
    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        self.client = openai.OpenAI(api_key=api_key)
        # ... rest of implementation
```

Store API key in Databricks Secrets:
```bash
databricks secrets put-secret --scope <scope> --key openai-api-key
```
</details>

<details>
<summary>Click to see Anthropic setup</summary>

```python
# Install: pip install anthropic
import anthropic

class ScenarioAgent:
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = anthropic.Anthropic(api_key=api_key)
        # ... rest of implementation
```
</details>

### 3. Integrate with Flask App

In your `app.py`, add:

```python
from flask_agent_routes import register_agent_routes

# After creating your Flask app
app = Flask(__name__)
# ... existing setup ...

# Register agent endpoints
register_agent_routes(app)
```

### 4. Add Frontend Integration

Create a simple chat interface in your templates:

```html
<!-- templates/scenario_play.html -->
<div id="agent-help" class="agent-panel">
    <h3>AI Mentor</h3>
    <div id="chat-history"></div>
    <input type="text" id="chat-input" placeholder="Ask for help...">
    <button onclick="sendMessage()">Send</button>
</div>

<script>
function sendMessage() {
    const message = document.getElementById('chat-input').value;
    const attemptId = {{ state.attempt_id }};
    
    fetch('/agent/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            message: message,
            attempt_id: attemptId,
            user_id: {{ user.user_id }}
        })
    })
    .then(r => r.json())
    .then(data => {
        // Display response in chat-history
        document.getElementById('chat-history').innerHTML += 
            `<div class="message bot">${data.response}</div>`;
    });
}
</script>
```

### 5. Key Agent Endpoints

Your agent now exposes these REST endpoints:

#### POST `/agent/chat`
General-purpose chat with the AI mentor
```json
{
    "message": "How do I optimize this Spark join?",
    "user_id": 123,
    "attempt_id": 456
}
```

#### POST `/agent/help`
Get contextual help for current scenario
```json
{
    "attempt_id": 456,
    "question": "What should I consider here?"
}
```

#### POST `/agent/evaluate-answer`
Have AI evaluate free-text answers
```json
{
    "attempt_id": 456,
    "node_id": "node_3",
    "answer": "I would use Spark structured streaming..."
}
```

#### POST `/agent/recommend`
Get personalized learning recommendations
```json
{
    "user_id": 123
}
```

#### GET `/agent/conversations?user_id=<id>&limit=10`
List recent conversations for a user
```json
{
    "conversations": [
        {
            "conversation_id": "abc-123",
            "attempt_id": "xyz-789",
            "message_count": 15,
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T11:45:00Z"
        }
    ],
    "total": 5
}
```

#### GET `/agent/conversation/<conversation_id>`
Get full conversation history
```json
{
    "conversation_id": "abc-123",
    "user_id": "user123",
    "messages": [{"role": "user", "content": "..."}, ...],
    "created_at": "2024-01-15T10:30:00Z"
}
```

## Tool Capabilities

Your agent can autonomously:

### READ Operations
- ✅ Get scenario state and user progress
- ✅ Search Stack Overflow for technical evidence (using semantic search)
- ✅ Read user interest profiles
- ✅ List available scenarios

### WRITE Operations
- ✅ Record user decisions with competence scores
- ✅ Advance scenarios to next nodes
- ✅ Complete scenario attempts
- ✅ Update user interest profiles
- ✅ Add learning recommendations

## How It Works

Your agent is **already configured** to use Databricks Foundation Models!

**Key Features:**
* ✅ No API keys - uses your Databricks workspace authentication
* ✅ Full tool calling support - agent can autonomously call your tools
* ✅ Multiple model options - from fast (70B) to most capable (405B)
* ✅ Cost-effective - included in your Databricks usage

**The Implementation:**
```python
# agent_runner.py (already done!)
from databricks.sdk import WorkspaceClient

class ScenarioAgent:
    def __init__(self, model="databricks-meta-llama-3-1-70b-instruct"):
        self.w = WorkspaceClient()  # Auto-authenticates
        self.model = model
    
    def run(self, user_message, context=None):
        # Calls Databricks Foundation Model with tool support
        response = self.w.serving.query(
            name=self.model,
            messages=[...],
            tools=TOOLS,  # Your agent_tools functions
            temperature=0.7
        )
        # Agent autonomously decides which tools to call!
```

**Model Comparison:**

| Model | Parameters | Best For | Speed |
|-------|-----------|----------|-------|
| llama-3-1-70b-instruct | 70B | **Recommended** - Great balance of speed & capability | Fast |
| llama-3-1-405b-instruct | 405B | Most capable - complex reasoning | Slower |
| dbrx-instruct | 132B | Good all-rounder | Medium |
| mixtral-8x7b-instruct | 47B | Fast responses | Very Fast |

## Testing Your Agent

### Test Tool Execution
```python
# Test individual tools
import agent_runner

# Test search
results = agent_runner.execute_tool(
    "search_evidence",
    {"query": "spark join optimization", "k": 3}
)
print(results)
```

### Test Agent
```python
# Test full agent
agent = agent_runner.ScenarioAgent()
result = agent.run(
    user_message="How do I optimize Spark joins?",
    context={"user_id": 1}
)
print(result["response"])
print("Tools called:", result["tool_calls"])
```

### Test via HTTP
```bash
curl -X POST http://localhost:5000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What should I consider for this data quality scenario?",
    "user_id": 1,
    "attempt_id": 1
  }'
```

## Production Considerations

### 1. Conversation State ✅ IMPLEMENTED
Conversations are now stored in the database for persistence:
```sql
-- Already created in sql/04_setup_agent_conversations.sql
CREATE TABLE agent_conversations (
    conversation_id UUID PRIMARY KEY,
    user_id TEXT REFERENCES users(user_id),
    attempt_id TEXT REFERENCES scenario_attempts(attempt_id),
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Features:**
- ✅ Persistent storage across app restarts
- ✅ Automatic timestamp updates
- ✅ Indexed for fast queries
- ✅ Linked to users and scenario attempts

**New Endpoints:**
- `GET /agent/conversations?user_id=<id>` - List user's conversations
- `GET /agent/conversation/<id>` - Get full conversation history

### 2. Rate Limiting
```python
from flask_limiter import Limiter

limiter = Limiter(app, key_func=lambda: session.get('user_id'))

@agent_bp.route('/chat', methods=['POST'])
@limiter.limit("10 per minute")  # Prevent abuse
def chat():
    ...
```

### 3. Cost Monitoring
Track LLM API costs:
```python
# Log token usage
logger.info(
    f"LLM call - User: {user_id}, "
    f"Tokens: {response.usage.total_tokens}, "
    f"Cost: ${response.usage.total_tokens * 0.00002}"
)
```

### 4. Error Handling
```python
try:
    result = agent.run(user_message, context)
except openai.RateLimitError:
    return jsonify({"error": "Rate limit exceeded. Please try again."}), 429
except Exception as e:
    logger.error(f"Agent error: {e}")
    return jsonify({"error": "Sorry, something went wrong."}), 500
```


## Summary

✅ **What we built:**
- Direct LLM integration with function calling
- Agent can search evidence AND take actions (write to DB)
- Fully integrated with your Flask app
- Works with OpenAI, Anthropic, or Databricks Foundation Models

❌ **What we DIDN'T build (MCP):**
- Not needed for your use case
- Would add unnecessary complexity
- Only useful if exposing tools externally

🚀 **Next Steps:**
1. Choose your LLM provider (Databricks Foundation Models recommended)
2. Add API keys to your environment
3. Test the agent endpoints
4. Add chat UI to your templates
5. Deploy and iterate!
