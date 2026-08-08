# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Weather Data Sync Pipeline
# MAGIC %md
# MAGIC # Sync Weather Documents from NWS API
# MAGIC
# MAGIC This notebook fetches fresh weather alerts and forecasts from the National Weather Service API
# MAGIC and inserts them into the `weather_documents` table in Lakebase.
# MAGIC
# MAGIC Run this on a schedule (e.g., every 15 minutes) to keep weather data current.

# COMMAND ----------

# DBTITLE 1,Install Dependencies
# MAGIC %pip install -q 'databricks-sdk>=0.118.0' requests

# COMMAND ----------

# DBTITLE 1,Restart Python
dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Configuration
# Configuration widgets
dbutils.widgets.text("limit_per_location", "50", "Max docs per location")
dbutils.widgets.text("table_name", "weather_documents", "Destination table")

import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LIMIT = int(dbutils.widgets.get("limit_per_location"))
TABLE_NAME = dbutils.widgets.get("table_name")

# Predefined city coordinates (all cities will be synced every run)
CITY_INFO = {
    "Chicago": {"state": "IL", "lat": 41.8781, "lon": -87.6298},
    "Austin": {"state": "TX", "lat": 30.2672, "lon": -97.7431},
    "Miami": {"state": "FL", "lat": 25.7617, "lon": -80.1918},
    "New York": {"state": "NY", "lat": 40.7128, "lon": -74.0060},
    "Los Angeles": {"state": "CA", "lat": 34.0522, "lon": -118.2437}
}

# Build location list for ALL cities
locations = []
for city_name, city_data in CITY_INFO.items():
    locations.append({
        "label": f"{city_name}, {city_data['state']}",
        "lat": city_data["lat"],
        "lon": city_data["lon"]
    })

# Print all cities that will be monitored
print(f"=== Location Configuration ===")
print(f"Monitoring {len(locations)} cities:")
for loc in locations:
    print(f"  • {loc['label']} (lat={loc['lat']}, lon={loc['lon']})")
print(f"Limit: {LIMIT} docs per location")
print(f"Target table: {TABLE_NAME}")
print(f"==============================")

logger.info(f"Monitoring {len(locations)} cities: {', '.join([loc['label'] for loc in locations])}")

# COMMAND ----------

# DBTITLE 1,Import Weather Client
import sys
sys.path.append("/Workspace/Users/valeria.s.caras@gmail.com/data-engineer-handbook-valst/weather-app")

from weather_client import WeatherClient, harvest_weather_documents

logger.info("✓ Weather client imported")

# COMMAND ----------

# DBTITLE 1,Setup Lakebase Connection
import base64
from urllib.parse import urlparse
import psycopg2
from psycopg2.extras import execute_values
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

def get_lakebase_url() -> str:
    secret = w.secrets.get_secret(scope="database", key="lakebase-url")
    return base64.b64decode(secret.value).decode("utf-8")

lakebase_url = get_lakebase_url()
parsed = urlparse(lakebase_url)

db_host = parsed.hostname
db_port = parsed.port or 5432
db_name = parsed.path.lstrip('/')
db_user = parsed.username
db_password = parsed.password

logger.info(f"Connecting to {db_host}:{db_port}/{db_name}")

# COMMAND ----------

# DBTITLE 1,Harvest and Insert Documents
# Fetch fresh weather data from NWS API
logger.info("Fetching weather data from NWS API...")
client = WeatherClient()
documents = harvest_weather_documents(client, locations, limit=LIMIT)
logger.info(f"Harvested {len(documents)} documents")

if not documents:
    logger.warning("No documents to sync")
    dbutils.notebook.exit("No documents fetched")

# Connect to Lakebase
conn = psycopg2.connect(
    host=db_host,
    port=db_port,
    dbname=db_name,
    user=db_user,
    password=db_password,
    sslmode='require'
)
cursor = conn.cursor()

try:
    # Prepare batch insert
    batch_data = []
    for doc in documents:
        batch_data.append((
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
            doc["synced_at"]
        ))
    
    # Insert with ON CONFLICT
    query = f"""
        INSERT INTO {TABLE_NAME} (
            id, location, source_type, headline, event, narrative_text,
            effective_at, expires_at, severity, urgency, certainty,
            temperature, temperature_unit, wind_speed, wind_direction,
            payload, synced_at
        )
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            location = EXCLUDED.location,
            narrative_text = EXCLUDED.narrative_text,
            synced_at = EXCLUDED.synced_at
    """
    
    execute_values(
        cursor,
        query,
        batch_data,
        template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    conn.commit()
    
    logger.info(f"✓ Synced {len(documents)} documents to {TABLE_NAME}")
    
    # Show breakdown
    cursor.execute(f"SELECT source_type, COUNT(*) FROM {TABLE_NAME} GROUP BY source_type")
    for row in cursor.fetchall():
        logger.info(f"  {row[0]}: {row[1]} total documents")
    
    dbutils.notebook.exit(json.dumps({"documents_synced": len(documents), "success": True}))
    
except Exception as e:
    logger.error(f"Failed to sync documents: {e}")
    conn.rollback()
    raise
finally:
    cursor.close()
    conn.close()