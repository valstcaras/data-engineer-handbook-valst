# Day One: Data Engineer

A career try-out simulator where users play through realistic data engineering scenarios, get mentored by an AI agent, and build an evidence-based interest profile.

## Overview

This app meets all five core requirements:

1. **Spark Data Pipeline**: Ingests Stack Overflow questions, processes text, computes embeddings
2. **Third-Party API Integration**: Stack Overflow API for real-world evidence retrieval  
3. **Unstructured Data Processing**: Question bodies → semantic embeddings for RAG
4. **Databricks App with Frontend**: Interactive scenario player with decision trees
5. **AI Agent with Tools**: Agent that guides scenarios, scores decisions, searches evidence, updates profiles, and recommends resources

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
│   └── 03_seed_scenarios.sql          # Initial scenario data
├── notebooks/
│   └── ingest_stackoverflow.py        # Spark ETL for SO data
├── templates/
│   ├── index.html                     # Landing page
│   ├── scenario.html                  # Scenario player
│   └── profile.html                   # Interest profile view
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
Open http://localhost:5000

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

This schedules `ingest_stackoverflow.py` to run daily.

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
- `POST /evidence/search` - Semantic search over SO content

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