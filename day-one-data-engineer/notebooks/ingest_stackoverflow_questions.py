# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Introduction
# MAGIC %md
# MAGIC # Ingest Stack Exchange Questions -> Vector Embeddings (Lakebase)
# MAGIC
# MAGIC This notebook is part of the **Day One: Data Engineer** app.
# MAGIC
# MAGIC It:
# MAGIC 1. Fetches real data engineering questions from Stack Exchange API
# MAGIC    (tagged: apache-spark, etl, databricks, data-engineering, pyspark)
# MAGIC 2. Stores them in the `stackoverflow_questions` Lakebase table
# MAGIC 3. Computes sentence embeddings for each question (title + body)
# MAGIC 4. Writes embeddings to `stackoverflow_embeddings` table with pgvector
# MAGIC
# MAGIC **Use Cases:**
# MAGIC - Populate raw material for scenario generation
# MAGIC - Build a "what practitioners actually struggle with" feed
# MAGIC - Enable semantic search over real debugging scenarios
# MAGIC - Retrieve similar Stack Overflow threads as "evidence" during scenario walkthroughs
# MAGIC
# MAGIC **Stack Exchange API:**
# MAGIC - Free tier: 300 requests/day, 10,000 requests/IP
# MAGIC - No API key required (but recommended for higher quotas)
# MAGIC - Rate limited: we respect 429 responses
# MAGIC
# MAGIC This notebook mirrors the pattern from `ingest_ticker_news_embeddings` but
# MAGIC processes Stack Exchange questions instead of news articles.

# COMMAND ----------

# DBTITLE 1,Install required packages
# MAGIC %pip uninstall -y psycopg2 psycopg2-binary
# MAGIC %pip install -q 'databricks-sdk>=0.118.0' sentence-transformers requests pandas

# COMMAND ----------

# DBTITLE 1,Restart Python
dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Config
# MAGIC %md
# MAGIC ## Config
# MAGIC
# MAGIC Widgets let you override table names, tags, and the embedding model without
# MAGIC editing the notebook - useful when running this as a scheduled Databricks Job.

# COMMAND ----------

# DBTITLE 1,Setup widgets and config
dbutils.widgets.text("questions_table_name", "stackoverflow_questions", "Destination table (raw questions)")
dbutils.widgets.text("embeddings_table_name", "stackoverflow_embeddings", "Destination table (vectors)")
dbutils.widgets.text("embedding_model", "sentence-transformers/all-MiniLM-L6-v2", "Embedding model")
dbutils.widgets.text("tags", "apache-spark;etl;databricks;data-engineering;pyspark", "Tags (semicolon-separated)")
dbutils.widgets.text("max_questions", "100", "Max questions per tag")
dbutils.widgets.text("site", "stackoverflow", "Stack Exchange site")

# Read config from widgets
QUESTIONS_TABLE_NAME = dbutils.widgets.get("questions_table_name")
EMBEDDINGS_TABLE_NAME = dbutils.widgets.get("embeddings_table_name")
EMBEDDING_MODEL = dbutils.widgets.get("embedding_model")
TAGS = [t.strip() for t in dbutils.widgets.get("tags").split(";") if t.strip()]
MAX_QUESTIONS = int(dbutils.widgets.get("max_questions"))
SITE = dbutils.widgets.get("site")

# Embedding dimension lookup (add more models as needed)
MODEL_DIMS = {
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "sentence-transformers/all-mpnet-base-v2": 768,
}

EMBEDDING_DIM = MODEL_DIMS.get(EMBEDDING_MODEL, 384)

print(f"Using model '{EMBEDDING_MODEL}' -> {EMBEDDING_DIM}-dim vectors")
print(f"Fetching questions tagged: {', '.join(TAGS)}")
print(f"Max {MAX_QUESTIONS} questions per tag from {SITE}")

# COMMAND ----------

# DBTITLE 1,Lakebase Connection
# MAGIC %md
# MAGIC ## Resolve the Lakebase connection URL
# MAGIC
# MAGIC Same secret, same decoding scheme as `lakebase.py`: a single base64-encoded
# MAGIC Postgres URL stored in a Databricks secret scope.

# COMMAND ----------

# DBTITLE 1,Parse Lakebase connection info
import base64
from urllib.parse import urlparse
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

def get_lakebase_url() -> str:
    secret = w.secrets.get_secret(scope="database", key="lakebase-url")
    return base64.b64decode(secret.value).decode("utf-8")

lakebase_url = get_lakebase_url()
parsed = urlparse(lakebase_url)

db_host = parsed.hostname
db_port = parsed.port or 5432
db_name = parsed.path.lstrip("/")
db_user = parsed.username
db_password = parsed.password

print(f"Connection details:")
print(f"  Host: {db_host}:{db_port}")
print(f"  Database: {db_name}")
print(f"  User: {db_user}")

# COMMAND ----------

# DBTITLE 1,Test connection
import psycopg2

print(f"Testing connection to {db_host}:{db_port}/{db_name}")

try:
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_password,
        sslmode='require'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT version()")
    version = cursor.fetchone()[0]
    print(f"✅ Connection successful!")
    print(f"PostgreSQL version: {version[:50]}...")
    cursor.close()
    conn.close()
except Exception as e:
    print(f"❌ Connection failed: {e}")
    raise

# COMMAND ----------

# DBTITLE 1,Database Setup Instructions
# MAGIC %md
# MAGIC ## Database Setup Instructions
# MAGIC
# MAGIC Before running the data fetch cells, create the required tables:
# MAGIC
# MAGIC ```sql
# MAGIC -- stackoverflow_questions table
# MAGIC CREATE TABLE IF NOT EXISTS stackoverflow_questions (
# MAGIC     question_id BIGINT PRIMARY KEY,
# MAGIC     title TEXT NOT NULL,
# MAGIC     body TEXT,
# MAGIC     tags TEXT[],
# MAGIC     link TEXT,
# MAGIC     score INT,
# MAGIC     view_count INT,
# MAGIC     answer_count INT,
# MAGIC     creation_date TIMESTAMPTZ,
# MAGIC     last_activity_date TIMESTAMPTZ,
# MAGIC     owner_display_name TEXT,
# MAGIC     owner_reputation INT,
# MAGIC     is_answered BOOLEAN,
# MAGIC     payload JSONB,
# MAGIC     synced_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
# MAGIC );
# MAGIC
# MAGIC CREATE INDEX IF NOT EXISTS idx_so_tags ON stackoverflow_questions USING GIN(tags);
# MAGIC CREATE INDEX IF NOT EXISTS idx_so_score ON stackoverflow_questions(score DESC);
# MAGIC
# MAGIC -- stackoverflow_embeddings table (requires pgvector extension)
# MAGIC CREATE EXTENSION IF NOT EXISTS vector;
# MAGIC
# MAGIC CREATE TABLE IF NOT EXISTS stackoverflow_embeddings (
# MAGIC     id SERIAL PRIMARY KEY,
# MAGIC     question_id BIGINT NOT NULL REFERENCES stackoverflow_questions(question_id) ON DELETE CASCADE,
# MAGIC     embedding vector(384),  -- adjust dimension based on your model
# MAGIC     text_content TEXT NOT NULL,
# MAGIC     created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
# MAGIC     UNIQUE(question_id)
# MAGIC );
# MAGIC
# MAGIC CREATE INDEX IF NOT EXISTS idx_so_embedding_vector 
# MAGIC     ON stackoverflow_embeddings USING ivfflat (embedding vector_cosine_ops);
# MAGIC ```

# COMMAND ----------

# DBTITLE 1,Fetch Questions from Stack Exchange API
# MAGIC %md
# MAGIC ## Fetch questions from Stack Exchange API
# MAGIC
# MAGIC Stack Exchange API docs: https://api.stackexchange.com/docs
# MAGIC
# MAGIC Endpoint: `/questions`
# MAGIC - Filter: withbody (includes question body)
# MAGIC - Sort: votes (most upvoted questions)
# MAGIC - Order: desc
# MAGIC - Tagged: our target tags
# MAGIC
# MAGIC We'll respect rate limits and handle pagination.

# COMMAND ----------

# DBTITLE 1,Fetch questions from Stack Exchange
import requests
import time
import json
from datetime import datetime
from typing import List, Dict, Any

def fetch_stackoverflow_questions(
    tags: List[str],
    site: str = "stackoverflow",
    max_per_tag: int = 100,
    sort: str = "votes",
    order: str = "desc"
) -> List[Dict[str, Any]]:
    """
    Fetch questions from Stack Exchange API for given tags.
    
    Args:
        tags: List of tag names (e.g., ['apache-spark', 'etl'])
        site: Stack Exchange site (default: 'stackoverflow')
        max_per_tag: Maximum questions to fetch per tag
        sort: Sort order (votes, activity, creation, hot, week, month)
        order: asc or desc
    
    Returns:
        List of question dictionaries
    """
    base_url = "https://api.stackexchange.com/2.3/questions"
    all_questions = []
    seen_ids = set()
    
    for tag in tags:
        print(f"\nFetching questions tagged '{tag}'...")
        
        page = 1
        fetched = 0
        
        while fetched < max_per_tag:
            params = {
                "site": site,
                "tagged": tag,
                "sort": sort,
                "order": order,
                "filter": "withbody",  # Include question body
                "page": page,
                "pagesize": min(100, max_per_tag - fetched)  # API max is 100
            }
            
            try:
                response = requests.get(base_url, params=params, timeout=30)
                
                # Handle rate limiting
                if response.status_code == 429:
                    print(f"  ⚠️  Rate limited. Waiting 60 seconds...")
                    time.sleep(60)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                questions = data.get("items", [])
                if not questions:
                    print(f"  No more questions found for tag '{tag}'")
                    break
                
                # Deduplicate across tags (a question can have multiple tags)
                new_questions = [q for q in questions if q["question_id"] not in seen_ids]
                for q in new_questions:
                    seen_ids.add(q["question_id"])
                
                all_questions.extend(new_questions)
                fetched += len(new_questions)
                
                print(f"  Page {page}: fetched {len(new_questions)} new questions (total: {fetched})")
                
                # Respect API quota - backoff (Stack Exchange recommends this)
                if "backoff" in data:
                    backoff = data["backoff"]
                    print(f"  API requested backoff: {backoff}s")
                    time.sleep(backoff)
                else:
                    time.sleep(0.5)  # Be nice to the API
                
                # Check if we have more pages
                if not data.get("has_more", False):
                    print(f"  No more pages for tag '{tag}'")
                    break
                
                page += 1
                
            except requests.exceptions.RequestException as e:
                print(f"  ❌ Error fetching questions: {e}")
                break
    
    print(f"\n✅ Fetched {len(all_questions)} unique questions across all tags")
    return all_questions

# Fetch questions
print(f"NOTE: Before running this cell, ensure you've created the stackoverflow_questions table.\n")

questions = fetch_stackoverflow_questions(
    tags=TAGS,
    site=SITE,
    max_per_tag=MAX_QUESTIONS
)

print(f"\nSample question:")
if questions:
    sample = questions[0]
    print(f"  Title: {sample['title'][:80]}...")
    print(f"  Tags: {', '.join(sample.get('tags', []))}")
    print(f"  Score: {sample.get('score', 0)}")
    print(f"  Answers: {sample.get('answer_count', 0)}")

# COMMAND ----------

# DBTITLE 1,Insert Questions into Lakebase
# MAGIC %md
# MAGIC ## Insert questions into Lakebase
# MAGIC
# MAGIC Batch insert all fetched questions using psycopg2.
# MAGIC Deduplication via `ON CONFLICT DO NOTHING`.

# COMMAND ----------

# DBTITLE 1,Insert questions into Lakebase
import psycopg2
from psycopg2.extras import execute_batch

conn = psycopg2.connect(
    host=db_host,
    port=db_port,
    dbname=db_name,
    user=db_user,
    password=db_password,
    sslmode='require'
)

try:
    cursor = conn.cursor()
    
    # Prepare data tuples for batch insert
    insert_data = []
    for q in questions:
        owner = q.get("owner", {})
        insert_data.append((
            q["question_id"],
            q["title"],
            q.get("body", ""),
            q.get("tags", []),
            q["link"],
            q.get("score", 0),
            q.get("view_count", 0),
            q.get("answer_count", 0),
            datetime.fromtimestamp(q["creation_date"]) if "creation_date" in q else None,
            datetime.fromtimestamp(q["last_activity_date"]) if "last_activity_date" in q else None,
            owner.get("display_name"),
            owner.get("reputation"),
            q.get("is_answered", False),
            json.dumps(q)  # Store full payload as JSONB
        ))
    
    # Batch insert with ON CONFLICT DO NOTHING for deduplication
    insert_sql = f"""
        INSERT INTO {QUESTIONS_TABLE_NAME} (
            question_id, title, body, tags, link, score, view_count, answer_count,
            creation_date, last_activity_date, owner_display_name, owner_reputation,
            is_answered, payload, synced_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (question_id) DO NOTHING
    """
    
    # execute_batch is faster than executemany for large batches
    execute_batch(cursor, insert_sql, insert_data, page_size=100)
    
    conn.commit()
    inserted_count = cursor.rowcount
    print(f"✅ Successfully inserted {inserted_count} new questions")
    print(f"   (Duplicates were skipped via ON CONFLICT DO NOTHING)")
    
finally:
    cursor.close()
    conn.close()

print(f"\nReady to compute embeddings! Run the cells below to continue.")

# COMMAND ----------

# DBTITLE 1,Compute Embeddings
# MAGIC %md
# MAGIC ## Compute embeddings for questions
# MAGIC
# MAGIC We'll:
# MAGIC 1. Load questions from Lakebase that don't have embeddings yet
# MAGIC 2. Combine title + body as text content
# MAGIC 3. Compute embeddings using sentence-transformers
# MAGIC 4. Batch insert embeddings into Lakebase with pgvector

# COMMAND ----------

# DBTITLE 1,Load model and compute embeddings
from sentence_transformers import SentenceTransformer
import numpy as np
import psycopg2
from psycopg2.extras import execute_batch

# Load embedding model
print(f"Loading embedding model: {EMBEDDING_MODEL}")
model = SentenceTransformer(EMBEDDING_MODEL)
print(f"✅ Model loaded (dimension: {EMBEDDING_DIM})")

# Connect to Lakebase and fetch questions without embeddings
conn = psycopg2.connect(
    host=db_host,
    port=db_port,
    dbname=db_name,
    user=db_user,
    password=db_password,
    sslmode='require'
)

try:
    cursor = conn.cursor()
    
    # Find questions without embeddings
    cursor.execute(f"""
        SELECT q.question_id, q.title, q.body
        FROM {QUESTIONS_TABLE_NAME} q
        LEFT JOIN {EMBEDDINGS_TABLE_NAME} e ON q.question_id = e.question_id
        WHERE e.id IS NULL
        ORDER BY q.score DESC
    """)
    
    questions_to_embed = cursor.fetchall()
    print(f"\nFound {len(questions_to_embed)} questions without embeddings")
    
    if not questions_to_embed:
        print("No new questions to embed!")
    else:
        # Prepare text content (title + body)
        texts = []
        question_ids = []
        
        for q_id, title, body in questions_to_embed:
            # Combine title and body (title is weighted more heavily)
            text = f"{title}\n\n{body or ''}"[:5000]  # Truncate to 5000 chars
            texts.append(text)
            question_ids.append(q_id)
        
        print(f"Computing embeddings for {len(texts)} questions...")
        
        # Compute embeddings in batches
        batch_size = 32
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            embeddings = model.encode(batch_texts, show_progress_bar=False)
            all_embeddings.extend(embeddings)
            print(f"  Processed {min(i+batch_size, len(texts))}/{len(texts)} questions")
        
        print(f"✅ Computed {len(all_embeddings)} embeddings")
        
        # Prepare data for insertion
        insert_data = []
        for q_id, text, embedding in zip(question_ids, texts, all_embeddings):
            # Convert numpy array to list for pgvector
            embedding_list = embedding.tolist()
            insert_data.append((q_id, embedding_list, text))
        
        # Batch insert embeddings
        insert_sql = f"""
            INSERT INTO {EMBEDDINGS_TABLE_NAME} (question_id, embedding, text_content, created_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (question_id) DO NOTHING
        """
        
        execute_batch(cursor, insert_sql, insert_data, page_size=100)
        conn.commit()
        
        inserted_count = cursor.rowcount
        print(f"✅ Successfully inserted {inserted_count} embeddings into {EMBEDDINGS_TABLE_NAME}")
        
finally:
    cursor.close()
    conn.close()

print("\n🎯 Pipeline complete! Questions and embeddings are ready for scenario generation.")

# COMMAND ----------

# DBTITLE 1,Verify Results
# MAGIC %md
# MAGIC ## Verify results
# MAGIC
# MAGIC Let's check what we've ingested and query for similar questions.

# COMMAND ----------

# DBTITLE 1,Verify ingestion statistics
import psycopg2

conn = psycopg2.connect(
    host=db_host,
    port=db_port,
    dbname=db_name,
    user=db_user,
    password=db_password,
    sslmode='require'
)

try:
    cursor = conn.cursor()
    
    # Count total questions first
    cursor.execute(f"SELECT COUNT(*) FROM {QUESTIONS_TABLE_NAME}")
    total_questions = cursor.fetchone()[0]
    
    cursor.execute(f"SELECT COUNT(*) FROM {EMBEDDINGS_TABLE_NAME}")
    total_embeddings = cursor.fetchone()[0]
    
    print(f"Total questions: {total_questions}")
    print(f"Total embeddings: {total_embeddings}")
    print(f"Coverage: {total_embeddings/total_questions*100:.1f}%" if total_questions > 0 else "Coverage: N/A")

    
    # Show top questions by score
    cursor.execute(f"""
        SELECT title, score, answer_count, link
        FROM {QUESTIONS_TABLE_NAME}
        ORDER BY score DESC
        LIMIT 5
    """)
    
    print(f"\nTop 5 questions by score:")
    for title, score, answers, link in cursor.fetchall():
        print(f"  [{score} votes, {answers} answers] {title[:60]}...")
        print(f"    {link}")
    
finally:
    cursor.close()
    conn.close()

# COMMAND ----------

# DBTITLE 1,Test semantic search
import psycopg2
from sentence_transformers import SentenceTransformer

# Load model
model = SentenceTransformer(EMBEDDING_MODEL)

# Test query
test_query = "How do I debug a slow Spark job with data skew?"
print(f"Test query: '{test_query}'\n")

# Compute query embedding
query_embedding = model.encode([test_query])[0].tolist()

# Connect and search
conn = psycopg2.connect(
    host=db_host,
    port=db_port,
    dbname=db_name,
    user=db_user,
    password=db_password,
    sslmode='require'
)

try:
    cursor = conn.cursor()
    
    # Semantic search using pgvector cosine similarity
    cursor.execute(f"""
        SELECT 
            q.title,
            q.score,
            q.link,
            1 - (e.embedding <=> %s::vector) as similarity
        FROM {EMBEDDINGS_TABLE_NAME} e
        JOIN {QUESTIONS_TABLE_NAME} q ON e.question_id = q.question_id
        ORDER BY e.embedding <=> %s::vector
        LIMIT 5
    """, (query_embedding, query_embedding))
    
    print("Top 5 similar questions:")
    for title, score, link, similarity in cursor.fetchall():
        print(f"\n  [{score} votes] Similarity: {similarity:.3f}")
        print(f"  {title}")
        print(f"  {link}")
    
finally:
    cursor.close()
    conn.close()