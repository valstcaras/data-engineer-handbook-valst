"""
Lakebase (Databricks-managed Postgres) connection helper.
"""

import base64
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras
from databricks.sdk import WorkspaceClient


def _get_lakebase_url() -> str:
    """
    Get Lakebase URL from environment or secret scope.
    """
    # Try environment variable first (for local dev)
    url = os.environ.get("LAKEBASE_URL")
    if url:
        return url
    
    # Try secret scope
    scope = os.environ.get("LAKEBASE_SECRET_SCOPE", "day-one")
    key = os.environ.get("LAKEBASE_SECRET_KEY", "lakebase-url")
    
    w = WorkspaceClient()
    encoded = w.secrets.get_secret(scope=scope, key=key).value
    decoded = base64.b64decode(encoded).decode("utf-8")
    return decoded


def _get_connection():
    """Get a new database connection."""
    url = _get_lakebase_url()
    return psycopg2.connect(url)


def run_query(sql: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
    """
    Execute a SELECT query and return results as list of dicts.
    """
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(sql, params or ())
            return [dict(row) for row in cursor.fetchall()]


def run_write(sql: str, params: Optional[Tuple] = None) -> None:
    """
    Execute an INSERT/UPDATE/DELETE/DDL statement.
    """
    with _get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
        conn.commit()


def run_batch_write(sql: str, batch: List[Tuple]) -> int:
    """
    Execute a batch of INSERT/UPDATE statements.
    Returns number of rows affected.
    """
    with _get_connection() as conn:
        with conn.cursor() as cursor:
            psycopg2.extras.execute_batch(cursor, sql, batch)
        conn.commit()
        return len(batch)
