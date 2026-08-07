"""
Weather Alert & Forecast Vector Search API

Provides endpoints to:
1. Sync weather data from NWS API into Lakebase Postgres
2. Search weather documents using semantic vector search
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from flask import Flask, jsonify, request

# Import local modules
import lakebase
from weather_client import WeatherClient, harvest_weather_documents

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Table names
WEATHER_TABLE_NAME = "weather_documents"
WEATHER_EMBEDDINGS_TABLE_NAME = "weather_embeddings"

# Embedding model (loaded lazily)
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def ensure_weather_table():
    """Create the weather documents table if it doesn't exist."""
    lakebase.run_write(
        f"""
        CREATE TABLE IF NOT EXISTS {WEATHER_TABLE_NAME} (
            id TEXT PRIMARY KEY,
            location TEXT NOT NULL,
            source_type TEXT NOT NULL,
            headline TEXT,
            event TEXT,
            narrative_text TEXT,
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
        )
        """
    )
    lakebase.run_write(
        f"CREATE INDEX IF NOT EXISTS idx_{WEATHER_TABLE_NAME}_location "
        f"ON {WEATHER_TABLE_NAME} (location)"
    )
    lakebase.run_write(
        f"CREATE INDEX IF NOT EXISTS idx_{WEATHER_TABLE_NAME}_source_type "
        f"ON {WEATHER_TABLE_NAME} (source_type)"
    )


def ensure_weather_embeddings_table():
    """Create the weather embeddings table if it doesn't exist."""
    lakebase.run_write("CREATE EXTENSION IF NOT EXISTS vector")
    
    lakebase.run_write(
        f"""
        CREATE TABLE IF NOT EXISTS {WEATHER_EMBEDDINGS_TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES {WEATHER_TABLE_NAME}(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector({EMBEDDING_DIM}) NOT NULL,
            model_name TEXT NOT NULL DEFAULT '{EMBEDDING_MODEL_NAME}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(document_id, chunk_index)
        )
        """
    )
    
    lakebase.run_write(
        f"CREATE INDEX IF NOT EXISTS idx_{WEATHER_EMBEDDINGS_TABLE_NAME}_document_id "
        f"ON {WEATHER_EMBEDDINGS_TABLE_NAME} (document_id)"
    )
    
    # Create HNSW index for fast vector search (if it doesn't exist)
    # This may fail if the table is empty, which is fine
    try:
        lakebase.run_write(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{WEATHER_EMBEDDINGS_TABLE_NAME}_vector_hnsw
                ON {WEATHER_EMBEDDINGS_TABLE_NAME}
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """
        )
    except Exception as e:
        logger.warning(f"Could not create HNSW index (table may be empty): {e}")


def _get_embedding_model():
    """Lazy-load and cache the sentence-transformers model."""
    if not hasattr(_get_embedding_model, "_model"):
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
        _get_embedding_model._model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _get_embedding_model._model


def _upsert_weather_batch(documents: list[dict]) -> int:
    """
    Upsert a batch of weather documents into the weather_documents table.
    Returns the number of documents upserted.
    """
    if not documents:
        return 0
    
    # Build INSERT ... ON CONFLICT UPDATE statement
    placeholders = []
    values = []
    
    for doc in documents:
        placeholders.append("(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
        values.extend([
            doc["id"],
            doc["location"],
            doc["source_type"],
            doc.get("headline"),
            doc.get("event"),
            doc.get("narrative_text"),
            doc.get("effective_at"),
            doc.get("expires_at"),
            doc.get("severity"),
            doc.get("urgency"),
            doc.get("certainty"),
            doc.get("temperature"),
            doc.get("temperature_unit"),
            doc.get("wind_speed"),
            doc.get("wind_direction"),
            json.dumps(doc["payload"]),
            doc["synced_at"],
        ])
    
    query = f"""
        INSERT INTO {WEATHER_TABLE_NAME} (
            id, location, source_type, headline, event, narrative_text,
            effective_at, expires_at, severity, urgency, certainty,
            temperature, temperature_unit, wind_speed, wind_direction,
            payload, synced_at
        )
        VALUES {', '.join(placeholders)}
        ON CONFLICT (id) DO UPDATE SET
            location = EXCLUDED.location,
            source_type = EXCLUDED.source_type,
            headline = EXCLUDED.headline,
            event = EXCLUDED.event,
            narrative_text = EXCLUDED.narrative_text,
            effective_at = EXCLUDED.effective_at,
            expires_at = EXCLUDED.expires_at,
            severity = EXCLUDED.severity,
            urgency = EXCLUDED.urgency,
            certainty = EXCLUDED.certainty,
            temperature = EXCLUDED.temperature,
            temperature_unit = EXCLUDED.temperature_unit,
            wind_speed = EXCLUDED.wind_speed,
            wind_direction = EXCLUDED.wind_direction,
            payload = EXCLUDED.payload,
            synced_at = EXCLUDED.synced_at
    """
    
    lakebase.run_write(query, tuple(values))
    return len(documents)


@app.route("/")
def index():
    """Basic health check endpoint."""
    return jsonify({
        "service": "Weather Alert & Forecast Vector Search API",
        "status": "running",
        "endpoints": [
            "POST /weather/sync - Sync weather data from NWS API",
            "POST /weather/search - Search weather documents by semantic similarity"
        ]
    })


@app.route("/weather/sync", methods=["POST"])
def sync_weather_from_nws():
    """
    Fetch weather data from NWS API and store in Lakebase.
    
    Body: {
        "locations": [
            {"label": "Chicago, IL", "lat": 41.88, "lon": -87.63},
            {"label": "Austin, TX", "lat": 30.27, "lon": -97.74}
        ],
        "limit": 50
    }
    
    Returns: {
        "documents_synced": 42,
        "locations_processed": ["Chicago, IL", "Austin, TX"]
    }
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    locations = request.json.get("locations", [])
    limit = request.json.get("limit", 50)
    
    if not locations:
        return jsonify({"error": "No locations provided"}), 400
    
    # Validate locations format
    for loc in locations:
        if not isinstance(loc, dict) or "label" not in loc or "lat" not in loc or "lon" not in loc:
            return jsonify({"error": "Each location must have label, lat, and lon"}), 400
    
    # Ensure tables exist
    ensure_weather_table()
    
    # Harvest documents from NWS API
    client = WeatherClient()
    documents = harvest_weather_documents(client, locations, limit=limit)
    
    # Upsert to database
    count = _upsert_weather_batch(documents)
    
    location_labels = [loc["label"] for loc in locations]
    
    return jsonify({
        "documents_synced": count,
        "locations_processed": location_labels
    })


@app.route("/weather/search", methods=["POST"])
def weather_search():
    """
    Search weather documents using semantic vector similarity.
    
    Body: {
        "query": "risk of flooding near rivers",
        "top_k": 5
    }
    
    Returns: [
        {
            "id": "abc123",
            "location": "Chicago, IL",
            "headline": "Flood Warning",
            "chunk_text": "...",
            "similarity": 0.85
        },
        ...
    ]
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    query_text = request.json.get("query", "").strip()
    top_k = request.json.get("top_k", 5)
    
    # Validation
    if not query_text:
        return jsonify({"error": "Query text is required"}), 400
    
    # Clamp top_k to reasonable bounds
    top_k = max(1, min(20, int(top_k)))
    
    # Ensure embeddings table exists
    try:
        ensure_weather_embeddings_table()
    except Exception as e:
        logger.warning(f"Could not ensure embeddings table: {e}")
    
    # Check if embeddings table has data
    try:
        count_result = lakebase.run_query(
            f"SELECT COUNT(*) as count FROM {WEATHER_EMBEDDINGS_TABLE_NAME}"
        )
        if count_result and count_result[0]["count"] == 0:
            return jsonify({
                "error": "No embeddings available yet. Run the embedding ingestion script first.",
                "results": []
            }), 200
    except Exception as e:
        return jsonify({
            "error": f"Embeddings table not ready: {str(e)}",
            "results": []
        }), 500
    
    # Load embedding model and embed query
    try:
        model = _get_embedding_model()
        query_embedding = model.encode([query_text])[0].tolist()
    except Exception as e:
        logger.error(f"Failed to embed query: {e}")
        return jsonify({"error": f"Failed to embed query: {str(e)}"}), 500
    
    # Perform vector search
    try:
        results = _search_weather_embeddings(query_embedding, top_k)
        return jsonify({"results": results, "count": len(results)})
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        return jsonify({"error": f"Search failed: {str(e)}"}), 500


def _search_weather_embeddings(query_embedding: list[float], top_k: int) -> list[dict]:
    """
    Perform pgvector cosine similarity search against weather_embeddings.
    
    Args:
        query_embedding: The query vector as a list of floats
        top_k: Maximum number of results to return
    
    Returns:
        List of dicts with location, headline, chunk_text, similarity
    """
    # Format embedding as PostgreSQL vector literal
    embedding_str = '[' + ','.join(str(float(x)) for x in query_embedding) + ']'
    
    query = f"""
        SELECT 
            d.id,
            d.location,
            d.source_type,
            d.headline,
            d.event,
            d.narrative_text,
            e.chunk_text,
            e.chunk_index,
            d.effective_at,
            d.expires_at,
            d.severity,
            1 - (e.embedding <=> %s::vector) AS similarity
        FROM {WEATHER_EMBEDDINGS_TABLE_NAME} e
        JOIN {WEATHER_TABLE_NAME} d ON d.id = e.document_id
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
    """
    
    rows = lakebase.run_query(query, (embedding_str, embedding_str, top_k))
    
    # Format results
    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "location": row["location"],
            "source_type": row["source_type"],
            "headline": row["headline"],
            "event": row["event"],
            "chunk_text": row["chunk_text"],
            "chunk_index": row["chunk_index"],
            "effective_at": row["effective_at"],
            "expires_at": row["expires_at"],
            "severity": row["severity"],
            "similarity": float(row["similarity"])
        })
    
    return results


if __name__ == "__main__":
    # Initialize tables on startup
    logger.info("Initializing weather tables...")
    ensure_weather_table()
    ensure_weather_embeddings_table()
    logger.info("Tables ready!")
    
    # Start Flask app
    app.run(host="0.0.0.0", port=8080, debug=True)
