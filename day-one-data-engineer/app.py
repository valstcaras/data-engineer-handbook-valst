"""Day One: Data Engineer - Flask Web App"""

import json
import os
import uuid
from typing import Optional

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_agent_routes import register_agent_routes

import lakebase
import agent_tools

app = Flask(__name__)
register_agent_routes(app)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")


# ============================================================================
# HELPERS
# ============================================================================

def get_or_create_user():
    """Get current user from session or create new one."""
    if "user_id" not in session:
        # Show user creation page
        return None
    
    user_id = session["user_id"]
    rows = lakebase.run_query(
        "SELECT user_id, display_name, background_tag FROM users WHERE user_id = %s",
        (user_id,)
    )
    
    if rows:
        return rows[0]
    
    # User was deleted or session is stale
    session.clear()
    return None


def get_current_attempt(user_id: str, scenario_id: str) -> Optional[dict]:
    """Get active attempt for user+scenario, if any."""
    rows = lakebase.run_query(
        """
        SELECT attempt_id, status, current_node_id
        FROM scenario_attempts
        WHERE user_id = %s AND scenario_id = %s AND status = 'in_progress'
        ORDER BY started_at DESC
        LIMIT 1
        """,
        (user_id, scenario_id)
    )
    return rows[0] if rows else None


# ============================================================================
# ROUTES
# ============================================================================

@app.route("/")
def index():
    """Home page - user profile or scenario list."""
    user = get_or_create_user()
    
    if not user:
        return render_template("create_user.html")
    
    # Show scenarios list
    scenarios = agent_tools.list_scenarios(user["user_id"])
    
    return render_template(
        "scenarios_list.html",
        user=user,
        scenarios=scenarios
    )


@app.route("/create_user", methods=["POST"])
def create_user():
    """Create new user."""
    display_name = request.form.get("display_name", "").strip()
    background_tag = request.form.get("background_tag", "other")
    
    if not display_name:
        return "Display name required", 400
    
    # Check if name already exists
    existing = lakebase.run_query(
        "SELECT user_id FROM users WHERE display_name = %s",
        (display_name,)
    )
    
    if existing:
        return "Display name already taken", 400
    
    # Create user
    user_id = str(uuid.uuid4())
    lakebase.run_write(
        "INSERT INTO users (user_id, display_name, background_tag) VALUES (%s, %s, %s)",
        (user_id, display_name, background_tag)
    )
    
    session["user_id"] = user_id
    return redirect(url_for("index"))


@app.route("/scenario/<scenario_id>")
def scenario_play(scenario_id: str):
    """Play a scenario (start or resume)."""
    user = get_or_create_user()
    if not user:
        return redirect(url_for("index"))
    
    # Get or create attempt
    attempt = get_current_attempt(user["user_id"], scenario_id)
    
    if not attempt:
        # Start new attempt
        attempt_id = str(uuid.uuid4())
        
        # Get scenario to find start node
        scenario_rows = lakebase.run_query(
            "SELECT definition FROM scenarios WHERE scenario_id = %s",
            (scenario_id,)
        )
        
        if not scenario_rows:
            return "Scenario not found", 404
        
        definition = scenario_rows[0]["definition"]
        start_node = definition.get("start_node", "node_1")
        
        lakebase.run_write(
            """
            INSERT INTO scenario_attempts (attempt_id, user_id, scenario_id, status, current_node_id)
            VALUES (%s, %s, %s, 'in_progress', %s)
            """,
            (attempt_id, user["user_id"], scenario_id, start_node)
        )
        
        attempt = {
            "attempt_id": attempt_id,
            "current_node_id": start_node
        }
    
    # Get full state
    state = agent_tools.get_scenario_state(attempt["attempt_id"])
    
    return render_template(
        "scenario_play.html",
        user=user,
        state=state
    )


@app.route("/scenario/<scenario_id>/decide", methods=["POST"])
def scenario_decide(scenario_id: str):
    """Record a decision and advance."""
    user = get_or_create_user()
    if not user:
        return redirect(url_for("index"))
    
    attempt = get_current_attempt(user["user_id"], scenario_id)
    if not attempt:
        return "No active attempt", 400
    
    # Get form data
    node_id = request.form.get("node_id")
    chosen_option = request.form.get("chosen_option")
    free_text_answer = request.form.get("free_text_answer")
    
    # Get current state to determine next node and scoring
    state = agent_tools.get_scenario_state(attempt["attempt_id"])
    current_node = state["current_node"]
    
    if current_node["type"] == "decision":
        # Score the decision
        rubric = current_node.get("rubric", {})
        competence_score = rubric.get("options", {}).get(chosen_option, 0.5)
        
        # Get feedback
        feedback = current_node.get("feedback", {}).get(chosen_option, "")
        
        # Get next node
        next_node_id = current_node.get("next", {}).get(chosen_option)
        
        # Record decision
        decision_id = str(uuid.uuid4())
        lakebase.run_write(
            """
            INSERT INTO decisions (decision_id, attempt_id, node_id, chosen_option, competence_score, agent_feedback)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (decision_id, attempt["attempt_id"], node_id, chosen_option, competence_score, feedback)
        )
        
    elif current_node["type"] == "free_text":
        # For free text, we'll score later with an agent
        # For now, just record it
        decision_id = str(uuid.uuid4())
        lakebase.run_write(
            """
            INSERT INTO decisions (decision_id, attempt_id, node_id, chosen_option, free_text_answer, competence_score, agent_feedback)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (decision_id, attempt["attempt_id"], node_id, "free_text", free_text_answer, 0.8, "Thank you for your response!")
        )
        
        next_node_id = current_node.get("next")
    else:
        return "Invalid node type", 400
    
    # Advance to next node or complete
    if next_node_id:
        agent_tools.advance_scenario(attempt["attempt_id"], next_node_id)
        return redirect(url_for("scenario_play", scenario_id=scenario_id))
    else:
        # Scenario complete - show survey
        return redirect(url_for("scenario_complete", scenario_id=scenario_id, attempt_id=attempt["attempt_id"]))


@app.route("/scenario/<scenario_id>/complete/<attempt_id>")
def scenario_complete(scenario_id: str, attempt_id: str):
    """Show completion survey."""
    user = get_or_create_user()
    if not user:
        return redirect(url_for("index"))
    
    state = agent_tools.get_scenario_state(attempt_id)
    
    return render_template(
        "scenario_complete.html",
        user=user,
        state=state
    )


@app.route("/scenario/<scenario_id>/submit_survey", methods=["POST"])
def submit_survey(scenario_id: str):
    """Submit post-scenario survey."""
    user = get_or_create_user()
    if not user:
        return redirect(url_for("index"))
    
    attempt_id = request.form.get("attempt_id")
    enjoyment_score = int(request.form.get("enjoyment_score", 3))
    would_do_as_job = request.form.get("would_do_as_job") == "yes"
    
    # Complete the attempt
    agent_tools.complete_attempt(attempt_id, enjoyment_score, would_do_as_job)
    
    # Update interest profile
    state = agent_tools.get_scenario_state(attempt_id)
    category = state["scenario"]["category"]
    
    # Calculate average competence from decisions
    decisions = state["decisions"]
    if decisions:
        avg_competence = sum(d["competence_score"] for d in decisions) / len(decisions)
    else:
        avg_competence = 0.5
    
    agent_tools.update_interest_profile(
        user["user_id"],
        {category: {"enjoyment": enjoyment_score, "competence": avg_competence}}
    )
    
    return redirect(url_for("index"))


@app.route("/search")
def search():
    """Semantic search over Stack Overflow scenarios."""
    user = get_or_create_user()
    if not user:
        return redirect(url_for("index"))
    
    query = request.args.get("q", "")
    results = []
    
    if query:
        # Perform semantic search
        results = agent_tools.search_evidence(query, k=10)
    
    return render_template(
        "search.html",
        user=user,
        query=query,
        results=results
    )


@app.route("/api/search", methods=["POST"])
def api_search():
    """API endpoint for semantic search (JSON)."""
    data = request.get_json()
    query = data.get("query", "")
    k = data.get("k", 5)
    
    if not query:
        return jsonify({"error": "Query required"}), 400
    
    results = agent_tools.search_evidence(query, k=k)
    
    return jsonify({
        "query": query,
        "count": len(results),
        "results": results
    })


@app.route("/debug/agent-test")
def debug_agent_test():
    """Debug endpoint to test agent initialization."""
    try:
        import agent_runner
        return jsonify({
            "status": "ok",
            "message": "Agent module imported successfully"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "type": type(e).__name__
        }), 500


@app.route("/test-chat")
def test_chat():
    """Test page for AI chat endpoint."""
    return render_template("test_chat.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)