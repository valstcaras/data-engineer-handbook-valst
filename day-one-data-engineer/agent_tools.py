"""
Agent tool implementations for Day One: Data Engineer.

Provides both read and write tools for the agent to interact with:
- Scenario state management
- Evidence search (semantic)
- Interest profile tracking
- Learning recommendations
"""

import json
from typing import Any, Dict, List, Optional

import numpy as np

import lakebase


# ============================================================================
# READ TOOLS
# ============================================================================


def get_scenario_state(attempt_id: int) -> Dict[str, Any]:
    """
    Get current state of a scenario attempt.
    Returns: {
        "attempt_id": int,
        "user_id": int,
        "scenario_id": int,
        "scenario": {...},
        "status": str,
        "current_node_id": str,
        "current_node": {...},
        "decisions": [...],
        "started_at": timestamp
    }
    """
    # Get attempt info
    rows = lakebase.run_query(
        """
        SELECT 
            sa.attempt_id,
            sa.user_id,
            sa.scenario_id,
            sa.status,
            sa.current_node_id,
            sa.started_at,
            sa.completed_at,
            s.title as scenario_title,
            s.category as scenario_category,
            s.definition as scenario_definition
        FROM scenario_attempts sa
        JOIN scenarios s ON sa.scenario_id = s.scenario_id
        WHERE sa.attempt_id = %s
        """,
        (attempt_id,),
    )
    
    if not rows:
        raise ValueError(f"Attempt {attempt_id} not found")
    
    attempt = rows[0]
    
    # Get decisions made so far
    decisions = lakebase.run_query(
        """
        SELECT 
            decision_id,
            node_id,
            chosen_option,
            free_text_answer,
            competence_score,
            agent_feedback,
            created_at
        FROM decisions
        WHERE attempt_id = %s
        ORDER BY created_at ASC
        """,
        (attempt_id,),
    )
    
    # Parse scenario definition
    definition = attempt["scenario_definition"]
    
    # Get current node
    current_node_id = attempt["current_node_id"]
    nodes = definition.get("nodes", {})
    current_node = nodes.get(current_node_id)
    
    return {
        "attempt_id": attempt["attempt_id"],
        "user_id": attempt["user_id"],
        "scenario_id": attempt["scenario_id"],
        "scenario": {
            "title": attempt["scenario_title"],
            "category": attempt["scenario_category"],
        },
        "status": attempt["status"],
        "current_node_id": current_node_id,
        "current_node": current_node,
        "decisions": decisions,
        "started_at": attempt["started_at"],
        "completed_at": attempt.get("completed_at"),
    }


def search_evidence(
    query: str,
    category: Optional[str] = None,
    k: int = 5
) -> List[Dict[str, Any]]:
    """
    Semantic search over Stack Overflow evidence using pgvector.
    
    Returns list of evidence records with:
    - title, body, chunk_text
    - question_url
    - score, view_count, tags
    - similarity score
    """
    from sentence_transformers import SentenceTransformer
    
    # Load embedding model (same as used in ingestion)
    # Cache this in production to avoid reloading
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    
    # Compute query embedding
    query_embedding = model.encode([query])[0].tolist()
    
    # Search using pgvector cosine similarity
    # <=> operator is cosine distance (1 - cosine similarity)
    sql = """
        SELECT 
            q.question_id,
            q.title,
            q.body,
            q.tags,
            q.link as question_url,
            q.score,
            q.view_count,
            q.answer_count,
            e.text_content,
            1 - (e.embedding <=> %s::vector) as similarity
        FROM stackoverflow_embeddings e
        JOIN stackoverflow_questions q ON e.question_id = q.question_id
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
    """
    
    results = lakebase.run_query(sql, (query_embedding, query_embedding, k))
    
    # Parse tags from PostgreSQL array format to Python list
    for result in results:
        if result.get('tags'):
            tags_str = result['tags']
            # PostgreSQL arrays come as strings like '{python,sql,pandas}'
            if isinstance(tags_str, str):
                # Remove curly braces and split by comma
                tags_str = tags_str.strip('{}')
                result['tags'] = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
            elif not isinstance(tags_str, list):
                result['tags'] = []
        else:
            result['tags'] = []
    
    return results


def get_interest_profile(user_id: int) -> Dict[str, Any]:
    """
    Get user's interest profile.
    Returns profile JSONB and verdict text.
    """
    rows = lakebase.run_query(
        "SELECT profile, verdict, updated_at FROM interest_profiles WHERE user_id = %s",
        (user_id,),
    )
    
    if not rows:
        return {
            "user_id": user_id,
            "profile": {},
            "verdict": None,
            "updated_at": None,
        }
    
    row = rows[0]
    return {
        "user_id": user_id,
        "profile": row["profile"],
        "verdict": row["verdict"],
        "updated_at": row["updated_at"],
    }


def list_scenarios(user_id: int) -> List[Dict[str, Any]]:
    """
    List all active scenarios with completion status for user.
    Returns list of scenarios with attempt counts.
    """
    rows = lakebase.run_query(
        """
        SELECT 
            s.scenario_id,
            s.title,
            s.category,
            s.difficulty,
            s.est_minutes,
            COUNT(CASE WHEN sa.user_id = %s AND sa.status = 'completed' THEN 1 END) as completed_count,
            COUNT(CASE WHEN sa.user_id = %s AND sa.status = 'in_progress' THEN 1 END) as in_progress_count
        FROM scenarios s
        LEFT JOIN scenario_attempts sa ON s.scenario_id = sa.scenario_id
        WHERE s.is_active = true
        GROUP BY s.scenario_id, s.title, s.category, s.difficulty, s.est_minutes
        ORDER BY s.scenario_id
        """,
        (user_id, user_id),
    )
    
    return rows


# ============================================================================
# WRITE TOOLS
# ============================================================================


def record_decision(
    attempt_id: int,
    node_id: str,
    chosen_option: str,
    free_text_answer: Optional[str],
    competence_score: float,
    agent_feedback: str,
) -> None:
    """
    Record a decision made by the user.
    """
    lakebase.run_write(
        """
        INSERT INTO decisions (
            attempt_id,
            node_id,
            chosen_option,
            free_text_answer,
            competence_score,
            agent_feedback
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (attempt_id, node_id, chosen_option, free_text_answer, competence_score, agent_feedback),
    )


def advance_scenario(attempt_id: int, next_node_id: str) -> None:
    """
    Move the scenario state machine to the next node.
    """
    lakebase.run_write(
        "UPDATE scenario_attempts SET current_node_id = %s WHERE attempt_id = %s",
        (next_node_id, attempt_id),
    )


def complete_attempt(
    attempt_id: int,
    enjoyment_score: int,
    would_do_as_job: bool
) -> None:
    """
    Mark an attempt as completed and record post-scenario survey.
    """
    lakebase.run_write(
        """
        UPDATE scenario_attempts 
        SET 
            status = 'completed',
            completed_at = now(),
            enjoyment_score = %s,
            would_do_as_job = %s
        WHERE attempt_id = %s
        """,
        (enjoyment_score, would_do_as_job, attempt_id),
    )


def update_interest_profile(
    user_id: int,
    category_deltas: Dict[str, Dict[str, float]],
    verdict: Optional[str] = None
) -> None:
    """
    Update user's interest profile with new category deltas.
    
    category_deltas format:
    {
        "data_quality": {"enjoyment": 4.5, "competence": 0.8},
        ...
    }
    """
    # Get existing profile
    existing = get_interest_profile(user_id)
    profile = existing["profile"]
    
    # Merge in new deltas
    for category, deltas in category_deltas.items():
        if category not in profile:
            profile[category] = {"enjoyment": [], "competence": []}
        
        if "enjoyment" in deltas:
            profile[category]["enjoyment"].append(deltas["enjoyment"])
        if "competence" in deltas:
            profile[category]["competence"].append(deltas["competence"])
    
    # Upsert profile
    profile_json = json.dumps(profile)
    lakebase.run_write(
        """
        INSERT INTO interest_profiles (user_id, profile, verdict)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id) 
        DO UPDATE SET 
            profile = EXCLUDED.profile,
            verdict = EXCLUDED.verdict,
            updated_at = now()
        """,
        (user_id, profile_json, verdict),
    )


def add_learning_recommendation(
    user_id: int,
    title: str,
    url: str,
    reason: str,
    source: str = "agent"
) -> None:
    """
    Add a learning recommendation for the user.
    """
    lakebase.run_write(
        """
        INSERT INTO learning_recommendations (user_id, title, url, reason, source)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, title, url, reason, source),
    )
