"""Flask routes for AI agent integration.

Add these routes to your app.py to enable AI agent functionality.
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional

from flask import Blueprint, request, jsonify, session
import agent_runner
import lakebase

# Create blueprint
agent_bp = Blueprint('agent', __name__, url_prefix='/agent')


# ============================================================================
# CONVERSATION STORAGE HELPERS
# ============================================================================

def get_conversation(conversation_id: str) -> Optional[Dict]:
    """Retrieve conversation from database."""
    rows = lakebase.run_query(
        "SELECT conversation_id, user_id, attempt_id, messages, created_at, updated_at FROM agent_conversations WHERE conversation_id = %s",
        (conversation_id,)
    )
    return rows[0] if rows else None


def create_conversation(user_id: Optional[str] = None, attempt_id: Optional[str] = None) -> str:
    """Create a new conversation in database."""
    conversation_id = str(uuid.uuid4())
    lakebase.run_write(
        "INSERT INTO agent_conversations (conversation_id, user_id, attempt_id, messages) VALUES (%s, %s, %s, %s)",
        (conversation_id, user_id, attempt_id, json.dumps([]))
    )
    return conversation_id


def update_conversation(conversation_id: str, messages: List[Dict]) -> None:
    """Update conversation messages in database."""
    lakebase.run_write(
        "UPDATE agent_conversations SET messages = %s WHERE conversation_id = %s",
        (json.dumps(messages), conversation_id)
    )


def get_user_conversations(user_id: str, limit: int = 10) -> List[Dict]:
    """Get recent conversations for a user."""
    return lakebase.run_query(
        """
        SELECT conversation_id, attempt_id, 
               jsonb_array_length(messages) as message_count,
               created_at, updated_at
        FROM agent_conversations
        WHERE user_id = %s
        ORDER BY updated_at DESC
        LIMIT %s
        """,
        (user_id, limit)
    )


@agent_bp.route('/chat', methods=['POST'])
def chat():
    """
    Main agent chat endpoint.
    
    Request:
    {
        "message": "How do I optimize a Spark join?",
        "user_id": 123,
        "attempt_id": 456,  // optional
        "conversation_id": "abc123"  // optional, for maintaining context
    }
    
    Response:
    {
        "response": "Here's how to optimize Spark joins...",
        "tool_calls": [...],
        "conversation_id": "abc123"
    }
    """
    data = request.json
    
    user_message = data.get('message')
    user_id = data.get('user_id')
    attempt_id = data.get('attempt_id')
    conversation_id = data.get('conversation_id', session.get('agent_conversation_id'))
    
    if not user_message:
        return jsonify({"error": "Message is required"}), 400
    
    # Get or create conversation
    conversation = None
    if conversation_id:
        conversation = get_conversation(conversation_id)
    
    if not conversation:
        # Create new conversation in database
        conversation_id = create_conversation(user_id, attempt_id)
        session['agent_conversation_id'] = conversation_id
        conversation_history = []
    else:
        # Load existing conversation history from database
        conversation_history = conversation['messages']
    
    # Build context
    context = {}
    if user_id:
        context['user_id'] = user_id
    if attempt_id:
        context['attempt_id'] = attempt_id
    
    # Run agent
    agent = agent_runner.ScenarioAgent()
    result = agent.run(
        user_message=user_message,
        context=context,
        conversation_history=conversation_history
    )
    
    # Store updated conversation history in database
    update_conversation(conversation_id, result['messages'])
    
    # Return response
    return jsonify({
        "response": result['response'],
        "tool_calls": result.get('tool_calls', []),
        "conversation_id": conversation_id,
        "message_count": len(result['messages'])
    })


@agent_bp.route('/help', methods=['POST'])
def get_help():
    """
    Get contextual help for current scenario node.
    
    Request:
    {
        "attempt_id": 456,
        "question": "Optional specific question"
    }
    """
    data = request.json
    attempt_id = data.get('attempt_id')
    question = data.get('question', "Can you help me understand this scenario and what I should consider?")
    
    if not attempt_id:
        return jsonify({"error": "attempt_id is required"}), 400
    
    # Get scenario state for context
    state = agent_runner.execute_tool('get_scenario_state', {'attempt_id': attempt_id})
    
    # Build helpful context message
    context_message = f"""
The user is working on scenario: {state['scenario']['title']}
Category: {state['scenario']['category']}
Current node: {state['current_node_id']}

Node details: {state['current_node']}

They've asked: {question}

Provide helpful guidance, search for relevant Stack Overflow examples if needed, 
and explain the key considerations for this decision.
    """
    
    agent = agent_runner.ScenarioAgent()
    result = agent.run(
        user_message=context_message,
        context={'attempt_id': attempt_id}
    )
    
    return jsonify({
        "response": result['response'],
        "evidence": [r for r in result.get('tool_results', []) if isinstance(r, list)]
    })


@agent_bp.route('/evaluate-answer', methods=['POST'])
def evaluate_answer():
    """
    Have the agent evaluate a free-text answer.
    
    Request:
    {
        "attempt_id": 456,
        "node_id": "node_3",
        "answer": "I would use Spark structured streaming with..."
    }
    
    Response:
    {
        "competence_score": 0.85,
        "feedback": "Great answer! You correctly identified...",
        "suggestions": ["Consider also mentioning..."],
        "evidence": [...]  // Related Stack Overflow posts
    }
    """
    data = request.json
    attempt_id = data.get('attempt_id')
    node_id = data.get('node_id')
    answer = data.get('answer')
    
    if not all([attempt_id, node_id, answer]):
        return jsonify({"error": "attempt_id, node_id, and answer are required"}), 400
    
    # Get scenario context
    state = agent_runner.execute_tool('get_scenario_state', {'attempt_id': attempt_id})
    current_node = state['current_node']
    
    # Build evaluation prompt
    eval_prompt = f"""
Evaluate this user's answer to a data engineering scenario question.

Scenario: {state['scenario']['title']}
Category: {state['scenario']['category']}

Question: {current_node.get('question', 'See node details')}
Node details: {current_node}

User's answer:
{answer}

Provide:
1. A competence score (0.0 to 1.0) based on:
   - Technical accuracy
   - Completeness of reasoning
   - Consideration of trade-offs
   - Real-world applicability

2. Constructive feedback highlighting:
   - What they did well
   - What could be improved
   - Key concepts to learn more about

3. Search for relevant Stack Overflow evidence if helpful

Be encouraging but honest. This is a learning experience.
    """
    
    agent = agent_runner.ScenarioAgent()
    result = agent.run(
        user_message=eval_prompt,
        context={'attempt_id': attempt_id, 'node_id': node_id}
    )
    
    # Extract score from response (you'd want to make this more robust)
    # For now, return a default score and let the LLM explain in feedback
    return jsonify({
        "competence_score": 0.75,  # Could parse from LLM response
        "feedback": result['response'],
        "tool_calls": result.get('tool_calls', []),
        "evidence": [r for r in result.get('tool_results', []) if isinstance(r, list)]
    })


@agent_bp.route('/conversations', methods=['GET'])
def list_conversations():
    """
    List recent conversations for a user.
    
    Query params:
        user_id: User ID
        limit: Number of conversations to return (default: 10)
    
    Response:
    {
        "conversations": [
            {
                "conversation_id": "abc123",
                "attempt_id": "xyz789",
                "message_count": 15,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T11:45:00Z"
            }
        ]
    }
    """
    user_id = request.args.get('user_id')
    limit = int(request.args.get('limit', 10))
    
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    
    conversations = get_user_conversations(user_id, limit)
    
    return jsonify({
        "conversations": conversations,
        "total": len(conversations)
    })


@agent_bp.route('/conversation/<conversation_id>', methods=['GET'])
def get_conversation_detail(conversation_id: str):
    """
    Get full conversation history.
    
    Response:
    {
        "conversation_id": "abc123",
        "user_id": "user123",
        "attempt_id": "xyz789",
        "messages": [...],
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T11:45:00Z"
    }
    """
    conversation = get_conversation(conversation_id)
    
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404
    
    return jsonify(conversation)


@agent_bp.route('/recommend', methods=['POST'])
def get_recommendations():
    """
    Get personalized learning recommendations.
    
    Request:
    {
        "user_id": 123
    }
    
    Response:
    {
        "recommendations": [...],
        "reasoning": "Based on your interest profile..."
    }
    """
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    
    # Get user's profile and scenarios
    profile = agent_runner.execute_tool('get_interest_profile', {'user_id': user_id})
    scenarios = agent_runner.execute_tool('list_scenarios', {'user_id': user_id})
    
    # Build recommendation prompt
    rec_prompt = f"""
Generate personalized learning recommendations for this user.

Interest profile:
{profile}

Scenarios completed:
{scenarios}

Provide 3-5 specific learning resources (courses, articles, documentation) that would:
1. Build on their strengths
2. Address areas where they struggled
3. Prepare them for scenarios they haven't tried yet

For each recommendation, use the add_learning_recommendation tool to save it.
    """
    
    agent = agent_runner.ScenarioAgent()
    result = agent.run(
        user_message=rec_prompt,
        context={'user_id': user_id}
    )
    
    return jsonify({
        "response": result['response'],
        "recommendations_added": len([t for t in result.get('tool_calls', []) 
                                      if t.get('name') == 'add_learning_recommendation'])
    })


# ============================================================================
# REGISTER BLUEPRINT
# ============================================================================

def register_agent_routes(app):
    """Register agent routes with Flask app."""
    app.register_blueprint(agent_bp)
    
"""
To use in your app.py:

from flask_agent_routes import register_agent_routes

# After creating your Flask app
app = Flask(__name__)
# ... other setup ...

register_agent_routes(app)
"""
