# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# dependencies = [
#   "psycopg2-binary",
#   "sentence-transformers",
# ]
# ///
# DBTITLE 1,Weather Document Embedding Pipeline
# MAGIC %md
# MAGIC # Ingest Weather Documents -> Vector Embeddings (Lakebase)
# MAGIC
# MAGIC This notebook is part of the **Context Engineering on Databricks** course.
# MAGIC
# MAGIC It:
# MAGIC 1. Reads weather alert/forecast documents from the `weather_documents` table
# MAGIC    in Lakebase Postgres.
# MAGIC 2. Splits long narrative text into overlapping chunks for better embedding
# MAGIC    granularity (e.g., detailed storm descriptions, forecast narratives).
# MAGIC 3. Computes sentence embeddings for each chunk using sentence-transformers,
# MAGIC    distributed across the cluster via batch processing.
# MAGIC 4. Writes the embeddings into the `weather_embeddings` table using the
# MAGIC    `pgvector` Postgres extension, enabling downstream RAG / context-engineering
# MAGIC    exercises to run similarity search directly in Postgres.
# MAGIC
# MAGIC This notebook mirrors the pattern from `ingest_ticker_news_embeddings` but
# MAGIC processes weather documents instead of news articles. It re-uses the SAME
# MAGIC Lakebase secret (scope `database`, key `lakebase-url`) that the Flask app
# MAGIC uses, so no extra secrets need to be created.
# MAGIC
# MAGIC ## Key Features:
# MAGIC - **Configurable via widgets** - Override table names, embedding model, and chunk
# MAGIC   sizes without editing code
# MAGIC - **Automatic dimension matching** - Embedding vector size automatically adjusts
# MAGIC   based on the selected model
# MAGIC - **Comprehensive logging** - Track progress, errors, and summary statistics
# MAGIC - **Deduplication** - Uses `ON CONFLICT DO NOTHING` to skip already-embedded documents

# COMMAND ----------

# MAGIC %pip uninstall -y psycopg2 psycopg2-binary
# MAGIC %pip install -q 'databricks-sdk>=0.118.0' sentence-transformers trafilatura requests pandas

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Config Section
# MAGIC %md
# MAGIC ## Config
# MAGIC
# MAGIC Widgets let you override the source/destination table names and the
# MAGIC embedding model without editing the notebook - useful when running this
# MAGIC as a scheduled Databricks Job.

# COMMAND ----------

# Configuration via Databricks widgets
dbutils.widgets.text("weather_table_name", "weather_documents", "Source table (weather docs)")
dbutils.widgets.text("embeddings_table_name", "weather_embeddings", "Destination table (vectors)")
dbutils.widgets.text("embedding_model", "sentence-transformers/all-MiniLM-L6-v2", "Embedding model")
dbutils.widgets.text("chunk_size", "800", "Document chunk size (chars)")
dbutils.widgets.text("chunk_overlap", "100", "Document chunk overlap (chars)")
dbutils.widgets.text("batch_size", "100", "Batch size for DB writes")

WEATHER_TABLE_NAME = dbutils.widgets.get("weather_table_name")
WEATHER_EMBEDDINGS_TABLE_NAME = dbutils.widgets.get("embeddings_table_name")
EMBEDDING_MODEL_NAME = dbutils.widgets.get("embedding_model")
CHUNK_SIZE = int(dbutils.widgets.get("chunk_size"))
CHUNK_OVERLAP = int(dbutils.widgets.get("chunk_overlap"))
BATCH_SIZE = int(dbutils.widgets.get("batch_size"))

# Different sentence-transformers models emit different vector sizes, and the
# pgvector column type (VECTOR(N)) must match exactly. Rather than hardcoding
# one dimension, switch on the model name so swapping EMBEDDING_MODEL_NAME via
# the widget above automatically resizes the destination table's vector column.
match EMBEDDING_MODEL_NAME:
    case "sentence-transformers/all-MiniLM-L6-v2":
        EMBEDDING_DIM = 384
    case "sentence-transformers/all-MiniLM-L12-v2":
        EMBEDDING_DIM = 384
    case "sentence-transformers/all-mpnet-base-v2":
        EMBEDDING_DIM = 768
    case "sentence-transformers/paraphrase-multilingual-mpnet-base-v2":
        EMBEDDING_DIM = 768
    case "BAAI/bge-small-en-v1.5":
        EMBEDDING_DIM = 384
    case "BAAI/bge-base-en-v1.5":
        EMBEDDING_DIM = 768
    case "BAAI/bge-large-en-v1.5":
        EMBEDDING_DIM = 1024
    case "text-embedding-3-small":
        EMBEDDING_DIM = 1536
    case "text-embedding-3-large":
        EMBEDDING_DIM = 3072
    case _:
        raise ValueError(
            f"Unknown embedding model {EMBEDDING_MODEL_NAME!r} - add its output "
            "dimension to the match/case block above before running this notebook."
        )

print(f"Using model {EMBEDDING_MODEL_NAME!r} -> {EMBEDDING_DIM}-dim vectors")

# COMMAND ----------

# DBTITLE 1,Import Libraries
import base64
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import execute_values
from databricks.sdk import WorkspaceClient
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# COMMAND ----------

# DBTITLE 1,Connection URL Section
# MAGIC %md
# MAGIC ## Resolve the Lakebase connection URL
# MAGIC
# MAGIC Same secret, same decoding scheme as the Flask app: a single base64-encoded
# MAGIC Postgres URL (`postgresql://role:password@host:5432/db?sslmode=require`)
# MAGIC stored in a Databricks secret scope. We parse it into the pieces psycopg2
# MAGIC needs for connection (host/port/dbname/user/password).

# COMMAND ----------

# DBTITLE 1,Parse Lakebase Connection Info
import base64
from urllib.parse import urlparse

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()


def get_lakebase_url() -> str:
    secret = w.secrets.get_secret(scope="database", key="lakebase-url")
    return base64.b64decode(secret.value).decode("utf-8")


lakebase_url = get_lakebase_url()
parsed = urlparse(lakebase_url)

# Extract connection details directly from the secret URL
db_host = parsed.hostname
db_port = parsed.port or 5432
db_name = parsed.path.lstrip('/')
db_user = parsed.username
db_password = parsed.password

logger.info(f"Connection details:")
logger.info(f"  Host: {db_host}:{db_port}")
logger.info(f"  Database: {db_name}")
logger.info(f"  User: {db_user}")
logger.info(f"  Using credentials from secret")

# COMMAND ----------

# DBTITLE 1,Test Psycopg2 connection
import psycopg2

logger.info(f"Testing connection to {db_host}:{db_port}/{db_name}")
logger.info(f"Using authentication as user: {db_user}")

# Test psycopg2 connection
try:
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_password,
        sslmode='require',
        connect_timeout=10
    )
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {WEATHER_TABLE_NAME}")
    count = cursor.fetchone()[0]
    logger.info(f"✅ Connection successful! Found {count} rows in {WEATHER_TABLE_NAME}")
    
    cursor.execute(f"SELECT * FROM {WEATHER_TABLE_NAME} LIMIT 5")
    rows = cursor.fetchall()
    colnames = [desc[0] for desc in cursor.description]
    logger.info(f"Columns: {colnames}")
    for row in rows:
        logger.info(str(row))
    
    cursor.close()
    conn.close()
    logger.info("✅ psycopg2 authentication working correctly!")
except Exception as e:
    import traceback
    logger.error(f"❌ Connection failed: {e}")
    logger.error("Full traceback:")
    traceback.print_exc()

# COMMAND ----------

# DBTITLE 1,Database Setup Instructions
# MAGIC %md
# MAGIC ## Database Setup Instructions
# MAGIC
# MAGIC Before running this notebook, you must manually create the required tables
# MAGIC in your Lakebase Postgres database:
# MAGIC
# MAGIC 1. Run `sql/04_setup_weather_documents_table.sql` to create `weather_documents`
# MAGIC 2. Run `sql/05_setup_weather_embeddings_table.sql` to create `weather_embeddings`
# MAGIC    - Replace `{{EMBEDDING_DIM}}` with your model's dimension (e.g., 384)
# MAGIC
# MAGIC This notebook uses psycopg2 with credential-based authentication for all database operations.

# COMMAND ----------

# DBTITLE 1,Get Lakebase Connection
def get_lakebase_connection():
    """
    Get a psycopg2 connection to Lakebase using the parsed connection details.
    """
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_password,
        sslmode='require',
        connect_timeout=30
    )
    
    return conn

# COMMAND ----------

# DBTITLE 1,Text Chunking Function
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: The text to chunk
        chunk_size: Maximum chunk size in characters
        overlap: Number of characters to overlap between chunks
    
    Returns:
        List of text chunks
    """
    if not text or len(text) <= chunk_size:
        return [text] if text else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        
        # Move forward by (chunk_size - overlap)
        start += (chunk_size - overlap)
        
        # Avoid creating tiny trailing chunks
        if start + overlap >= len(text):
            break
    
    return chunks

# COMMAND ----------

# DBTITLE 1,Processing Pipeline Section
# MAGIC %md
# MAGIC ## Process weather documents and compute embeddings
# MAGIC
# MAGIC This section defines the main ETL pipeline:
# MAGIC
# MAGIC 1. **Fetch unembedded documents** - Query the `weather_documents` table for documents
# MAGIC    that don't yet have embeddings in the `weather_embeddings` table
# MAGIC 2. **Chunk narrative text** - Split long weather narratives into overlapping chunks
# MAGIC    for better embedding granularity
# MAGIC 3. **Compute embeddings** - Use sentence-transformers to create vector embeddings
# MAGIC    for each chunk
# MAGIC 4. **Write to Lakebase** - Insert embeddings into the `weather_embeddings` table
# MAGIC    using psycopg2 for reliable writes

# COMMAND ----------

# DBTITLE 1,Fetch Unembedded Documents
def fetch_unembedded_documents(conn) -> list[dict]:
    """
    Fetch weather documents that don't have embeddings yet.
    
    Returns:
        List of document dicts with id, location, narrative_text, etc.
    """
    query = f"""
        SELECT 
            d.id,
            d.location,
            d.source_type,
            d.headline,
            d.event,
            d.narrative_text,
            d.effective_at,
            d.expires_at,
            d.severity
        FROM {WEATHER_TABLE_NAME} d
        LEFT JOIN {WEATHER_EMBEDDINGS_TABLE_NAME} e ON d.id = e.document_id
        WHERE e.id IS NULL
        ORDER BY d.synced_at DESC
    """
    
    cursor = conn.cursor()
    cursor.execute(query)
    
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    
    documents = []
    for row in rows:
        doc = dict(zip(columns, row))
        documents.append(doc)
    
    return documents

# COMMAND ----------

# DBTITLE 1,Compute Embeddings
def embed_chunks(chunks: list[str], model: SentenceTransformer) -> list[list[float]]:
    """
    Compute embeddings for a list of text chunks.
    
    Args:
        chunks: List of text strings to embed
        model: SentenceTransformer model
    
    Returns:
        List of embedding vectors (each is a list of floats)
    """
    if not chunks:
        return []
    
    # sentence-transformers returns numpy arrays, convert to lists
    embeddings = model.encode(chunks)
    return [emb.tolist() for emb in embeddings]

# COMMAND ----------

# DBTITLE 1,Verify Table Setup
# Before running the cells below, ensure you've manually run:
#   sql/05_setup_weather_embeddings_table.sql
# Replace {{EMBEDDING_DIM}} in that file with the value below:
logger.info(f"Required EMBEDDING_DIM for SQL setup: {EMBEDDING_DIM}")
logger.info(f"Table name: {WEATHER_EMBEDDINGS_TABLE_NAME}")
logger.info("Run sql/05_setup_weather_embeddings_table.sql in your Lakebase database before continuing.")

# COMMAND ----------

# DBTITLE 1,Embeddings Table Setup
# MAGIC %md
# MAGIC ## Ensure the pgvector destination table exists
# MAGIC
# MAGIC The `pgvector` extension must be enabled and the destination table
# MAGIC created with the correct vector dimension before inserting embeddings.
# MAGIC
# MAGIC The table schema includes:
# MAGIC - `document_id` - Foreign key to weather_documents
# MAGIC - `chunk_index` - Position of this chunk within the document
# MAGIC - `chunk_text` - The actual text that was embedded
# MAGIC - `embedding` - The vector embedding (VECTOR type with matching dimension)
# MAGIC - `model_name` - Which embedding model was used

# COMMAND ----------

# DBTITLE 1,Insert Embeddings Batch
def insert_embeddings_batch(
    conn,
    embeddings_data: list[tuple],
    batch_size: int = BATCH_SIZE
):
    """
    Insert embeddings into the weather_embeddings table in batches.
    
    Args:
        conn: psycopg2 connection
        embeddings_data: List of tuples (document_id, chunk_index, chunk_text, embedding_list, model_name)
        batch_size: Number of rows per batch
    """
    if not embeddings_data:
        return
    
    cursor = conn.cursor()
    
    # Process in batches
    for i in range(0, len(embeddings_data), batch_size):
        batch = embeddings_data[i:i + batch_size]
        
        # Convert embedding lists to PostgreSQL vector literal strings
        batch_formatted = []
        for doc_id, chunk_idx, chunk_text, emb_list, model_name in batch:
            # Format as [x1,x2,x3,...] for pgvector
            emb_str = '[' + ','.join(str(float(x)) for x in emb_list) + ']'
            batch_formatted.append((doc_id, chunk_idx, chunk_text, emb_str, model_name))
        
        # Use execute_values for efficient batch insert
        query = f"""
            INSERT INTO {WEATHER_EMBEDDINGS_TABLE_NAME}
                (document_id, chunk_index, chunk_text, embedding, model_name)
            VALUES %s
            ON CONFLICT (document_id, chunk_index) DO UPDATE SET
                chunk_text = EXCLUDED.chunk_text,
                embedding = EXCLUDED.embedding::vector,
                model_name = EXCLUDED.model_name,
                created_at = now()
        """
        
        execute_values(
            cursor,
            query,
            batch_formatted,
            template="(%s, %s, %s, %s::vector, %s)"
        )
        
        conn.commit()
        logger.info(f"Inserted batch of {len(batch)} embeddings")
    
    cursor.close()

# COMMAND ----------

# DBTITLE 1,Process Documents Pipeline
def process_documents(conn, model: SentenceTransformer):
    """
    Main processing pipeline:
    1. Fetch unembedded documents
    2. Chunk narrative text
    3. Compute embeddings
    4. Write to database
    """
    logger.info("Fetching unembedded documents...")
    documents = fetch_unembedded_documents(conn)
    
    if not documents:
        logger.info("No unembedded documents found. All documents are up to date!")
        return
    
    logger.info(f"Found {len(documents)} documents to process")
    
    embeddings_data = []
    
    for doc in documents:
        doc_id = doc['id']
        narrative = doc.get('narrative_text') or ''
        
        # Skip documents with no text
        if not narrative.strip():
            logger.warning(f"Document {doc_id} has no narrative text, skipping")
            continue
        
        # Chunk the narrative text
        chunks = chunk_text(narrative, CHUNK_SIZE, CHUNK_OVERLAP)
        
        logger.info(
            f"Processing document {doc_id} ({doc['location']}): "
            f"{len(narrative)} chars -> {len(chunks)} chunks"
        )
        
        # Compute embeddings for all chunks
        chunk_embeddings = embed_chunks(chunks, model)
        
        # Prepare data for insertion
        for idx, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings)):
            embeddings_data.append((
                doc_id,
                idx,
                chunk,
                embedding,
                EMBEDDING_MODEL_NAME
            ))
    
    if embeddings_data:
        logger.info(f"Inserting {len(embeddings_data)} embeddings into database...")
        insert_embeddings_batch(conn, embeddings_data, BATCH_SIZE)
        logger.info("✓ Embedding insertion complete!")
    else:
        logger.info("No embeddings to insert")

# COMMAND ----------

# DBTITLE 1,Execute Pipeline
# MAGIC %md
# MAGIC ## Execute the Pipeline
# MAGIC
# MAGIC This cell orchestrates the complete workflow:
# MAGIC 1. Loads the sentence-transformers model (with HuggingFace cache)
# MAGIC 2. Connects to Lakebase
# MAGIC 3. Fetches unembedded weather documents
# MAGIC 4. Chunks, embeds, and writes to the database
# MAGIC 5. Reports summary statistics
# MAGIC
# MAGIC The logging output shows detailed progress at each step.

# COMMAND ----------

# DBTITLE 1,Run Pipeline
logger.info("Starting weather document embedding pipeline")
logger.info(f"Configuration:")
logger.info(f"  Model: {EMBEDDING_MODEL_NAME} (dim={EMBEDDING_DIM})")
logger.info(f"  Chunk size: {CHUNK_SIZE} chars")
logger.info(f"  Chunk overlap: {CHUNK_OVERLAP} chars")
logger.info(f"  Batch size: {BATCH_SIZE}")
logger.info(f"  Tables: {WEATHER_TABLE_NAME} -> {WEATHER_EMBEDDINGS_TABLE_NAME}")

# Set up HuggingFace cache
os.environ["HF_HOME"] = "/tmp/.cache/huggingface"
os.environ["TRANSFORMERS_CACHE"] = "/tmp/.cache/huggingface"
os.environ["HF_HUB_CACHE"] = "/tmp/.cache/huggingface"

# Load the embedding model
logger.info("Loading embedding model...")
model = SentenceTransformer(EMBEDDING_MODEL_NAME, cache_folder="/tmp/.cache/huggingface")
logger.info("✓ Model loaded")

# Connect to Lakebase
logger.info("Connecting to Lakebase...")
conn = get_lakebase_connection()
logger.info("✓ Connected")

try:
    # Process documents
    process_documents(conn, model)
    logger.info("\n=== Pipeline completed successfully! ===")
    
    # Print summary statistics
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT COUNT(*) FROM {WEATHER_EMBEDDINGS_TABLE_NAME}"
    )
    total_embeddings = cursor.fetchone()[0]
    
    cursor.execute(
        f"SELECT COUNT(DISTINCT document_id) FROM {WEATHER_EMBEDDINGS_TABLE_NAME}"
    )
    unique_docs = cursor.fetchone()[0]
    
    cursor.close()
    
    logger.info(f"Total embeddings: {total_embeddings}")
    logger.info(f"Unique documents: {unique_docs}")
    
except Exception as e:
    logger.error(f"Pipeline failed: {e}")
    import traceback
    traceback.print_exc()
    raise
finally:
    conn.close()
    logger.info("Connection closed")