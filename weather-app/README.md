# Weather Alert & Forecast Vector Search App

A semantic search application for National Weather Service (NWS) weather alerts and forecasts, built on Databricks Lakebase (Postgres + pgvector).

## Architecture

This app mirrors the structure of `databricks-lakebase-app-day-2` but targets weather data instead of financial news:

1. **Data Ingestion**: Harvest weather alerts and forecasts from NWS API (`api.weather.gov`)
2. **Vector Embeddings**: Chunk and embed weather narratives using sentence-transformers
3. **Semantic Search**: Query weather documents using natural language

## Components

### Core Files

* `app.py` - Flask REST API with sync and search endpoints
* `weather_client.py` - NWS API client (alerts, forecasts, grid resolution)
* `lakebase.py` - Lakebase Postgres connection helper
* `requirements.txt` - Python dependencies

### Database Schema

* `sql/setup_weather_embeddings.sql` - Complete schema for both tables
  * `weather_documents` - Raw weather data (alerts + forecasts)
  * `weather_embeddings` - Vector embeddings (384-dim, HNSW indexed)

### Notebooks

* `notebooks/ingest_weather_embeddings.py` - Embedding pipeline (Part 2)

## Setup

### 1. Prerequisites

Ensure you have a Lakebase Postgres instance with:
* `pgvector` extension enabled
* Databricks secret: `database/lakebase-url` (base64-encoded Postgres URL)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Key packages:
* `psycopg2` - Postgres client
* `sentence-transformers` - Embedding model
* `databricks-sdk` - Secrets access
* `flask` - REST API
* `requests` - NWS API calls

### 3. Initialize Database

Run the schema setup:

```sql
-- From sql/setup_weather_embeddings.sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Creates weather_documents table
-- Creates weather_embeddings table with vector(384) column
-- Creates HNSW index for fast similarity search
```

Or let the app auto-create tables on first run.

## Usage

### Part 1: Ingest Weather Data

Sync weather data from NWS API:

```bash
curl -X POST http://localhost:8080/weather/sync \
  -H "Content-Type: application/json" \
  -d '{
    "locations": [
      {"label": "Chicago, IL", "lat": 41.88, "lon": -87.63},
      {"label": "Austin, TX", "lat": 30.27, "lon": -97.74}
    ],
    "limit": 50
  }'
```

Response:
```json
{
  "documents_synced": 42,
  "locations_processed": ["Chicago, IL", "Austin, TX"]
}
```

### Part 2: Generate Embeddings

Run the embedding pipeline:

```bash
python notebooks/ingest_weather_embeddings.py
```

This will:
1. Fetch unembedded documents from `weather_documents`
2. Chunk long narratives (CHUNK_SIZE=800, CHUNK_OVERLAP=100)
3. Generate embeddings using `sentence-transformers/all-MiniLM-L6-v2`
4. Write to `weather_embeddings` via psycopg2

Environment variables:
* `CHUNK_SIZE` - Default: 800
* `CHUNK_OVERLAP` - Default: 100
* `BATCH_SIZE` - Default: 100
* `EMBEDDING_MODEL` - Default: sentence-transformers/all-MiniLM-L6-v2

### Part 3: Search Weather Data

Query weather documents semantically:

```bash
curl -X POST http://localhost:8080/weather/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "risk of flooding near rivers",
    "top_k": 5
  }'
```

Response:
```json
{
  "results": [
    {
      "id": "abc123",
      "location": "Chicago, IL",
      "source_type": "alert",
      "headline": "Flood Warning",
      "event": "Flood Warning - Urban and Small Stream Flood Advisory",
      "chunk_text": "Heavy rainfall has caused river levels to rise...",
      "chunk_index": 0,
      "effective_at": "2024-01-15T10:00:00Z",
      "expires_at": "2024-01-15T22:00:00Z",
      "severity": "Moderate",
      "similarity": 0.85
    }
  ],
  "count": 5
}
```

## API Endpoints

### GET /
Health check - returns service status

### POST /weather/sync
Sync weather data from NWS API

**Request:**
```json
{
  "locations": [
    {"label": "City, ST", "lat": 41.88, "lon": -87.63}
  ],
  "limit": 50
}
```

**Response:**
```json
{
  "documents_synced": 42,
  "locations_processed": ["City, ST"]
}
```

### POST /weather/search
Search weather documents using semantic similarity

**Request:**
```json
{
  "query": "severe thunderstorms with hail",
  "top_k": 10
}
```

**Response:**
```json
{
  "results": [...],
  "count": 10
}
```

**Query parameters:**
* `query` (required) - Natural language search query
* `top_k` (optional) - Number of results (1-20, default: 5)

## Data Schema

### weather_documents

Raw weather data from NWS API:

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key (alert ID or hash) |
| location | TEXT | Location label (e.g. "Chicago, IL") |
| source_type | TEXT | "alert" or "forecast" |
| headline | TEXT | Alert headline or forecast period name |
| event | TEXT | Alert event type or forecast summary |
| narrative_text | TEXT | Detailed description/forecast text |
| effective_at | TIMESTAMPTZ | Start time |
| expires_at | TIMESTAMPTZ | End time |
| severity | TEXT | Alert severity (Minor/Moderate/Severe/Extreme) |
| urgency | TEXT | Alert urgency |
| certainty | TEXT | Alert certainty |
| temperature | NUMERIC | Forecast temperature |
| temperature_unit | TEXT | "F" or "C" |
| wind_speed | TEXT | Wind speed |
| wind_direction | TEXT | Wind direction |
| payload | JSONB | Full NWS API response |
| synced_at | TIMESTAMPTZ | Ingestion timestamp |

### weather_embeddings

Vector embeddings for semantic search:

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| document_id | TEXT | FK to weather_documents.id |
| chunk_index | INTEGER | Chunk position (0, 1, 2, ...) |
| chunk_text | TEXT | Text chunk content |
| embedding | vector(384) | Embedding vector |
| model_name | TEXT | Model identifier |
| created_at | TIMESTAMPTZ | Embedding timestamp |

Indexes:
* `UNIQUE(document_id, chunk_index)` - Prevent duplicate chunks
* `HNSW(embedding vector_cosine_ops)` - Fast similarity search

## Vector Search Implementation

The search uses **pgvector's cosine distance operator** (`<=>`):

```sql
SELECT 
    d.id,
    d.location,
    d.headline,
    e.chunk_text,
    1 - (e.embedding <=> '[...]'::vector) AS similarity
FROM weather_embeddings e
JOIN weather_documents d ON d.id = e.document_id
ORDER BY e.embedding <=> '[...]'::vector
LIMIT 5;
```

The `<=>` operator computes cosine distance (0 = identical, 2 = opposite), so we return `1 - distance` as the similarity score (higher = more similar).

## Chunking Strategy

Most NWS alerts and forecasts are short (<800 chars), so chunking primarily matters for:
* Combined alert description + instruction text
* Multi-day detailed forecasts
* Extended weather discussions

**Chunking parameters:**
* CHUNK_SIZE = 800 characters
* CHUNK_OVERLAP = 100 characters

This sliding-window approach ensures important phrases aren't split across chunk boundaries.

## Model Choice

**sentence-transformers/all-MiniLM-L6-v2**
* Dimension: 384
* Speed: Fast inference (~50ms on CPU)
* Quality: Good for general semantic search
* Size: Small (~80MB download)

Alternative models can be configured via the `EMBEDDING_MODEL` environment variable. Update `EMBEDDING_DIM` in both `app.py` and the ingestion script if you change models.

## Comparison to Reference App

| Feature | Ticker News App | Weather App |
|---------|----------------|-------------|
| Data source | Massive API | NWS API (free) |
| Document types | News articles | Alerts + Forecasts |
| Chunking | Article bodies | Narrative text |
| Embedding model | all-MiniLM-L6-v2 | all-MiniLM-L6-v2 |
| Vector dimension | 384 | 384 |
| Write method | Spark JDBC | psycopg2 |
| Search endpoint | /vector-search/query | /weather/search |

## Development

Run the Flask app locally:

```bash
export FLASK_ENV=development
python app.py
```

The app will start on `http://localhost:8080`.

## Production Deployment

For production use:
1. Use a production WSGI server (gunicorn, uwsgi)
2. Set up proper authentication/authorization
3. Configure CORS if serving a web frontend
4. Set up monitoring and logging
5. Schedule the embedding pipeline as a cron job or Databricks Job

## Troubleshooting

**"No embeddings available yet"**
* Run `notebooks/ingest_weather_embeddings.py` to generate embeddings

**"Connection failed"**
* Check Databricks secret: `database/lakebase-url`
* Verify Lakebase instance is running
* Confirm network connectivity

**"Table does not exist"**
* Run `sql/setup_weather_embeddings.sql`
* Or let the app auto-create on first `/weather/sync` call

**Empty search results**
* Verify embeddings table has data: `SELECT COUNT(*) FROM weather_embeddings;`
* Check query text matches document content
* Try broader queries

## License

This project is part of the Databricks Lakebase tutorial series.
