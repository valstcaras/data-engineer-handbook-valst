"""
Day One: Data Engineer - Main Flask Application

A career try-out simulator with:
- Interactive scenario player (decision trees)
- AI agent that guides, scores, and provides feedback
- Evidence retrieval from Stack Overflow
- Interest profile generation
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import requests
from databricks.sdk import WorkspaceClient
from flask import Flask, jsonify, render_template, request

import lakebase
from agent_tools import (
    add_learning_recommendation,
    advance_scenario,
    complete_attempt,
    get_interest_profile,
    get_scenario_state,
    list_scenarios,
    record_decision,
    search_evidence,
    update_interest_profile,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("day-one-de")

app = Flask(__name__)
_w = WorkspaceClient()


def _current_user_email() -> str:
    """
    Resolve the current user's email.
    Databricks Apps inject X-Forwarded-Email header.
    Fall back to SDK current_user API for local development.
    """
    header_email = request.headers.get("X-Forwarded-Email")
    if header_email:
        return header_email
    return _w.current_user.me().user_name


def _get_or_create_user(email: str) -> Dict:
    """
    Get existing user or create a new one.
    Returns user record with user_id.
    """
    # Check if user exists
    rows = lakebase.run_query(
        "SELECT user_id, display_name, background_tag FROM users WHERE display_name = %s",
        (email,),
    )
    if rows:
        return rows[0]

    # Create new user
    lakebase.run_write(
        "INSERT INTO users (display_name, background_tag) VALUES (%s, %s)",
        (email, "other"),  # Default background, can be updated later
    )

    # Fetch the created user
    rows = lakebase.run_query(
        "SELECT user_id, display_name, background_tag FROM users WHERE display_name = %s",
        (email,),
    )
    return rows[0]


# ============================================================================
# ROUTES - Frontend Pages
# ============================================================================


@app.route("/")
def index():
    """Landing page with scenario catalog."""
    return render_template("index.html")


@app.route("/scenario/<int:scenario_id>")
def scenario_page(scenario_id: int):
    """Scenario player page."""
    return render_template("scenario.html", scenario_id=scenario_id)


@app.route("/profile")
def profile_page():
    """Interest profile view."""
    return render_template("profile.html")


# ============================================================================
# ROUTES - API Endpoints
# ============================================================================


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/api/scenarios", methods=["GET"])
def api_list_scenarios():
    """
    List available scenarios with completion status for current user.
    """
    try:
        email = _current_user_email()
        user = _get_or_create_user(email)
        scenarios = list_scenarios(user["user_id"])
        return jsonify(scenarios)
    except Exception as e:
        logger.exception("Failed to list scenarios")
        return jsonify({"error": str(e)}), 500


@app.route("/api/scenarios/<int:scenario_id>", methods=["GET"])
def api_get_scenario(scenario_id: int):
    """
    Get scenario definition.
    """
    try:
        rows = lakebase.run_query(
            "SELECT scenario_id, title, category, difficulty, est_minutes, definition "
            "FROM scenarios WHERE scenario_id = %s AND is_active = true",
            (scenario_id,),
        )
        if not rows:
            return jsonify({"error": "Scenario not found"}), 404

        scenario = rows[0]
        return jsonify(scenario)
    except Exception as e:
        logger.exception("Failed to get scenario")
        return jsonify({"error": str(e)}), 500


@app.route("/api/attempts/start", methods=["POST"])
def api_start_attempt():
    """
    Begin a new scenario attempt.
    Body: {"scenario_id": int}
    """
    try:
        data = request.json
        scenario_id = data.get("scenario_id")

        if not scenario_id:
            return jsonify({"error": "scenario_id required"}), 400

        email = _current_user_email()
        user = _get_or_create_user(email)

        # Check if scenario exists
        rows = lakebase.run_query(
            "SELECT scenario_id, definition FROM scenarios WHERE scenario_id = %s AND is_active = true",
            (scenario_id,),
        )
        if not rows:
            return jsonify({"error": "Scenario not found"}), 404

        scenario = rows[0]
        definition = scenario["definition"]

        # Get the first node from definition
        first_node_id = definition.get("start_node", "node_1")

        # Create attempt
        lakebase.run_write(
            "INSERT INTO scenario_attempts (user_id, scenario_id, current_node_id) "
            "VALUES (%s, %s, %s)",
            (user["user_id"], scenario_id, first_node_id),
        )

        # Get the created attempt
        rows = lakebase.run_query(
            "SELECT attempt_id, user_id, scenario_id, current_node_id, started_at "
            "FROM scenario_attempts "
            "WHERE user_id = %s AND scenario_id = %s "
            "ORDER BY started_at DESC LIMIT 1",
            (user["user_id"], scenario_id),
        )

        attempt = rows[0]
        return jsonify(attempt)
    except Exception as e:
        logger.exception("Failed to start attempt")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
