# Day One: Data Engineer

A career try-out simulator where users play through realistic data engineering scenarios, get mentored by an AI agent, and build an evidence-based interest profile.

## Overview

This app meets all five core requirements:

1. **Spark Data Pipeline**: Ingests Stack Overflow questions, processes text, computes embeddings
2. **Third-Party API Integration**: Stack Overflow API for real-world evidence retrieval  
3. **Unstructured Data Processing**: Question bodies → semantic embeddings for RAG
4. **Databricks App with Frontend**: Interactive scenario player with decision trees
5. **AI Agent with Tools**: Fully autonomous agent using Databricks Foundation Models that guides scenarios, scores decisions, searches evidence, updates profiles, and recommends resources

### Key Features ✨

* **🤖 AI Agent Integration** - Built-in conversational AI mentor powered by Databricks Foundation Models (Llama 3.1 70B)
* **🔍 Semantic Search** - Natural language search over Stack Overflow using pgvector similarity
* **🎯 Interactive Scenarios** - Play through 5 realistic data engineering situations
* **📊 Interest Profiling** - Evidence-based career fit assessment through competence + enjoyment signals
* **🚀 Production Ready** - Deployable as Databricks App with Lakebase Postgres backend

## Architecture

### Data Model (Lakebase / Postgres)

**Core Tables:**
- `users` - User profiles with background tags
- `scenarios` - Scenario definitions with decision trees (JSONB)
- `scenario_attempts` - User progress through scenarios  
- `decisions` - Individual choices with competence scores
- `skills` - Catalog of data engineering skills
- `user_skill_signals` - Competence and enjoyment signals per skill
- `interest_profiles` - Rolling aggregate profiles per category
- `learning_recommendations` - Personalized next steps
- `agent_conversations` - Persistent AI agent conversation history (JSONB)

**Evidence Tables:**
- `scenario_evidence` - Stack Overflow content with pgvector embeddings

### Delta Lake (Spark)

- `bronze.stackoverflow_questions` - Raw API pulls, daily batch
- `silver.so_questions_clean` - Deduped, tagged, quality-filtered
- `gold.scenario_evidence` - Chunked + embedded for retrieval

### Agent Tools

**Read Tools:**
- `get_scenario_state(attempt_id)` - Current node, options, history
- `search_evidence(query, category?, k=5)` - Semantic search over SO
- `get_interest_profile(user_id)` - Current profile
- `list_scenarios(user_id)` - Catalog with completion status

**Write Tools:**
- `record_decision(...)` - Log choice + score + feedback
- `advance_scenario(...)` - Move state machine forward
- `complete_attempt(...)` - Close attempt, update profile
- `update_interest_profile(...)` - Recompute rolling profile
- `add_learning_recommendation(...)` - Suggest next steps

## The Five Scenarios

### S1 - "The Monday Morning Red Dashboard" (incident_debugging)
Nightly ingestion failed for 3 of 12 sources. Client report due at noon. Tests triage, communication under pressure.

### S2 - "The Number Is 40x Too Big" (data_quality)  
Revenue report shows 40x expected value. Client noticed first. Tests systematic debugging, root cause analysis.

### S3 - "The Metric That Doesn't Exist" (stakeholder_communication)
Stakeholder requests a metric that doesn't exist, thinks it's simple. Tests requirements elicitation, expectation management.

### S4 - "Twelve Sources, One Table" (pipeline_design)
Consolidate journal data from 12 different systems. Tests data modeling, defensive design, verification.

### S5 - "The Job That Eats All the Memory" (performance_optimization)
Extraction job OOMs at 40M rows. Tests resource reasoning, incremental thinking.

## Project Structure

```
day-one-data-engineer/
├── sql/
│   ├── 01_setup_core_tables.sql       # Lakebase schema
│   ├── 02_setup_scenario_evidence.sql # pgvector table
│   ├── 03_setup_stack_overflow.sql    # Stack Overflow tables
│   └── 04_setup_agent_conversations.sql # AI agent conversation storage
├── notebooks/
│   └── ingest_stackoverflow_questions # Spark ETL for SO data (notebook)
├── templates/
│   ├── index.html                     # Landing page
│   ├── scenarios_list.html            # Scenario catalog
│   ├── scenario_play.html             # Scenario player with AI chat
│   ├── scenario_complete.html         # Completion survey
│   ├── scenario.html                  # Legacy scenario template
│   ├── profile.html                   # Interest profile view
│   ├── search.html                    # Semantic search UI
│   ├── test_chat.html                 # AI agent test page
│   └── create_user.html               # User creation form
├── resources/
│   └── stackoverflow_ingestion_job.yml # DAB config
├── app.py                             # Flask app + agent
├── lakebase.py                        # DB connection helper
├── stackoverflow_client.py            # SO API client
├── agent_tools.py                     # Agent tool implementations
├── scenarios_seed.py                  # Scenario definitions
├── app.yaml                           # Databricks App config
├── requirements.txt
└── README.md
```

## Setup Instructions

### 1. Create Lakebase Instance

1. Go to **Catalog** > **Lakebase** in your Databricks workspace
2. Click **Create Lakebase instance** (name: `day-one-de`)
3. Enable **native password authentication**
4. Create a role (e.g., `day_one_app`) with password auth
5. Copy the connection URL:
   ```
   postgresql://<role>:<password>@<host>:5432/databricks_postgres?sslmode=require
   ```

### 2. Store Secrets

Create a notebook cell and run:
```python
from databricks.sdk import WorkspaceClient
import base64
import getpass

w = WorkspaceClient()

# Create secret scope
try:
    w.secrets.create_scope("day-one")
except Exception:
    pass  # Scope already exists

# Store Lakebase URL
lakebase_url = getpass.getpass("Paste your Lakebase connection URL: ")
encoded = base64.b64encode(lakebase_url.encode('utf-8')).decode('utf-8')
w.secrets.put_secret(scope="day-one", key="lakebase-url", string_value=encoded)

# Store Stack Overflow API key (optional, API has unauthenticated access)
so_key = getpass.getpass("Stack Overflow API key (or press Enter to skip): ")
if so_key:
    encoded_so = base64.b64encode(so_key.encode('utf-8')).decode('utf-8')
    w.secrets.put_secret(scope="day-one", key="so-api-key", string_value=encoded_so)

print("✅ Secrets stored successfully")
```

### 3. Initialize Database Schema

1. Connect to your Lakebase instance using a SQL client or Databricks SQL
2. Run `sql/01_setup_core_tables.sql`
3. Run `sql/02_setup_scenario_evidence.sql`
4. Run `python scenarios_seed.py` to load initial scenarios

### 4. Run the Spark ETL

1. Open `notebooks/ingest_stackoverflow.py`
2. Attach to a Serverless cluster
3. Update the widgets with your Lakebase credentials
4. Run all cells to:
   - Fetch Stack Overflow questions for DE topics
   - Clean and dedupe
   - Compute embeddings with sentence-transformers
   - Write to Lakebase with pgvector

### 5. Deploy the App

**Option A: Local Development**
```bash
cd day-one-data-engineer
pip install -r requirements.txt
python app.py
```
Open https://data-engineer-app-7474648794140478.aws.databricksapps.com

**Option B: Databricks App**
1. Create a Git folder in Databricks pointing to this repo
2. Go to **Compute** > **Apps** > **Create app**
3. Point to the `day-one-data-engineer` folder
4. The app reads `app.yaml` automatically
5. Click **Deploy**

### 6. Schedule the SO Ingestion (Optional)

If using Databricks Asset Bundles:
```bash
databricks bundle deploy -t dev
```

This schedules the `ingest_stackoverflow_questions` notebook to run daily.

## AI Agent Integration

This app features a **fully integrated AI agent** powered by Databricks Foundation Models:

* **No API keys required** - Uses workspace authentication
* **Autonomous tool calling** - Agent decides which tools to call based on context
* **Conversational mentorship** - Guides users through scenarios with natural dialogue
* **Evidence-based feedback** - Retrieves relevant Stack Overflow examples via semantic search
* **Profile-aware recommendations** - Personalizes based on user progress and preferences

### Agent Architecture

```
User Browser → Flask App → Agent Runner → Databricks Foundation Model (Llama 3.1 70B)
                                    │
                                    ↳── Tool Execution → Agent Tools → Lakebase DB
                                    │
                                    ↳── Semantic Search → pgvector
```

**Available Models:**
- `databricks-meta-llama-3-1-70b-instruct` (default, best for tool calling)
- `databricks-meta-llama-3-1-405b-instruct` (most capable, slower)
- `databricks-dbrx-instruct` (good balance)
- `databricks-mixtral-8x7b-instruct` (fastest)

**Agent Endpoints:**
- `POST /agent/chat` - General conversational agent chat
- `POST /agent/help` - Get contextual help for current scenario
- `POST /agent/evaluate-answer` - AI evaluation of free-text responses
- `POST /agent/recommend` - Get personalized learning recommendations
- `GET /test-chat` - Test page for agent integration

See [AGENT_SETUP.md](AGENT_SETUP.md) for complete technical documentation and [DEPLOY_APP.md](DEPLOY_APP.md) for deployment troubleshooting.

## Testing

### Test the AI Agent

**Option 1: Web UI Test Page**
1. Deploy your app (see step 5 above)
2. Visit `https://your-app-url/test-chat`
3. Click "Test Endpoint" to verify the agent is working

**Option 2: Unit Tests**
```python
# Run agent tests
python test_agent.py

# Direct agent testing
python test_agent_direct.py
```

**Option 3: Interactive Testing**
```python
import agent_runner

# Test individual tool
results = agent_runner.execute_tool(
    "search_evidence",
    {"query": "spark join optimization", "k": 3}
)

# Test full agent conversation
agent = agent_runner.ScenarioAgent()
response = agent.run(
    user_message="How do I optimize a slow Spark join?",
    context={"user_id": 1}
)
print(response["response"])
```

## How It Works

### 1. User Flow

1. User lands on home page, sees scenario catalog
2. Picks a scenario (e.g., "The Number Is 40x Too Big")
3. Agent presents the setup and first decision point
4. User chooses an option or provides free-text
5. Agent:
   - Scores the decision against a rubric
   - Provides feedback
   - Retrieves relevant Stack Overflow threads as "evidence from the wild"
   - Advances to the next node
6. After completing the scenario, user answers:
   - "How did this feel?" (energizing ↔ draining)
   - "Would you want this to be 30% of your job?"
7. Agent updates the interest profile
8. After ≥3 completed scenarios across ≥2 categories, agent writes a personalized verdict

### 2. Scoring Philosophy

**Competence signals** test instincts, not knowledge:
- Did they check logs before guessing?
- Did they ask about requirements before building?
- Did they consider tradeoffs?

**Enjoyment signals** build the career-fit profile:
- Weighted by scenario category
- Honest answer: "Can I do it?" ≠ "Do I want to do it?"

### 3. Agent Behavior

- **Conversational** - Narrates situation, responds with consequences
- **Evidence-based** - Shows real SO threads for each decision
- **Deterministic scoring** - Rubric-based, transparent feedback
- **Profile-aware** - Personalizes tone based on progress
- **Verdict after ≥3 scenarios** - No premature judgments

### 4. Semantic Search Feature

The app includes a powerful semantic search feature that lets you explore Stack Overflow questions using natural language queries:

- **How it works:**
  1. Questions from the ingestion notebook are stored in Lakebase with pgvector embeddings
  2. User queries are embedded using the same sentence-transformers model
  3. pgvector performs cosine similarity search to find the most relevant questions
  4. Results are ranked by similarity score and displayed with metadata (votes, views, tags)

- **Example queries:**
  - "debugging data quality issues"
  - "handling data skew in Spark"
  - "optimizing slow ETL pipelines"
  - "PySpark performance tuning"
  - "incremental data processing patterns"

- **Technical stack:**
  - `sentence-transformers/all-MiniLM-L6-v2` for embeddings (384 dimensions)
  - pgvector extension for efficient vector similarity search
  - Cosine distance operator (`<=>`) for ranking

- **Access:**
  - UI: Click "Search Stack Overflow Scenarios" on the home page or navigate to `/search`
  - API: POST to `/api/search` with JSON `{"query": "your question", "k": 10}`

## API Endpoints

- `GET /` - Landing page
- `GET /scenarios` - List available scenarios (JSON)
- `GET /scenarios/<id>` - Get scenario definition
- `POST /attempts/start` - Begin a scenario attempt
- `GET /attempts/<id>` - Get current state
- `POST /attempts/<id>/decide` - Record a decision
- `POST /attempts/<id>/complete` - Finish attempt with survey
- `GET /profile/<user_id>` - Get interest profile
- `GET /profile/<user_id>/recommendations` - Get learning recommendations
- `GET /search?q=<query>` - Semantic search UI over Stack Overflow questions
- `POST /api/search` - Semantic search API endpoint (JSON)
- `POST /agent/chat` - AI agent chat endpoint
- `POST /agent/help` - Get contextual help from AI agent
- `POST /agent/evaluate-answer` - AI evaluation of free-text answers
- `POST /agent/recommend` - Get personalized recommendations
- `GET /agent/conversations?user_id=<id>` - List user's conversation history
- `GET /agent/conversation/<id>` - Get full conversation details
- `GET /test-chat` - Test page for AI agent integration

## Development Roadmap

**Phase 1: MVP (1 scenario end-to-end)**
- ✅ Lakebase schema
- ✅ Scenario S2 definition
- ✅ Flask app skeleton
- ✅ Agent tool framework
- ⏳ Basic frontend
- ⏳ SO ingestion notebook
- ⏳ Deploy as Databricks App

**Phase 2: Full Scenario Suite**
- ⏳ Implement S1, S3, S4, S5
- ⏳ Rubric refinement
- ⏳ Profile algorithm tuning

**Phase 3: Polish**
- ⏳ Enhanced UI
- ⏳ Learning recommendation engine
- ⏳ Analytics dashboard

## License

MIT

## Contributing

This is an educational project. Pull requests welcome!