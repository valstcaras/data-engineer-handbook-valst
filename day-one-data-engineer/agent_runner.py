"""AI Agent Runner for Day One: Data Engineer.

Orchestrates LLM-based agent that can call tools to help users
through scenarios, search evidence, and make recommendations.
"""

import json
from typing import Any, Dict, List, Optional

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

import agent_tools


# ============================================================================
# TOOL DEFINITIONS FOR LLM
# ============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_scenario_state",
            "description": "Get the current state of a user's scenario attempt, including their progress, decisions made, and the current node they're on.",
            "parameters": {
                "type": "object",
                "properties": {
                    "attempt_id": {
                        "type": "integer",
                        "description": "The unique ID of the scenario attempt"
                    }
                },
                "required": ["attempt_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_evidence",
            "description": "Search Stack Overflow questions and answers for relevant technical evidence to help with a data engineering problem. Use this when the user needs examples, best practices, or solutions to specific technical challenges.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query describing what to look for (e.g., 'how to optimize spark join performance')"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category to filter by (e.g., 'pipeline_design', 'data_quality')",
                        "enum": ["incident_debugging", "data_quality", "stakeholder_communication", "pipeline_design", "performance_optimization"]
                    },
                    "k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_interest_profile",
            "description": "Get the user's interest profile showing their enjoyment and competence scores across different data engineering categories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_scenarios",
            "description": "List all available scenarios with the user's completion status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "record_decision",
            "description": "Record a decision made by the user in a scenario. Use this to save their choice along with a competence score and feedback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "attempt_id": {
                        "type": "integer",
                        "description": "The scenario attempt ID"
                    },
                    "node_id": {
                        "type": "string",
                        "description": "The node ID where the decision was made"
                    },
                    "chosen_option": {
                        "type": "string",
                        "description": "The option the user chose"
                    },
                    "free_text_answer": {
                        "type": "string",
                        "description": "Optional free-text answer from the user"
                    },
                    "competence_score": {
                        "type": "number",
                        "description": "Score between 0 and 1 indicating how well the user performed"
                    },
                    "agent_feedback": {
                        "type": "string",
                        "description": "Feedback message to show the user"
                    }
                },
                "required": ["attempt_id", "node_id", "chosen_option", "competence_score", "agent_feedback"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "advance_scenario",
            "description": "Move the scenario to the next node after a decision has been made.",
            "parameters": {
                "type": "object",
                "properties": {
                    "attempt_id": {
                        "type": "integer",
                        "description": "The scenario attempt ID"
                    },
                    "next_node_id": {
                        "type": "string",
                        "description": "The ID of the next node to move to"
                    }
                },
                "required": ["attempt_id", "next_node_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_learning_recommendation",
            "description": "Add a personalized learning recommendation for the user based on their performance or interests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user ID"
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the learning resource"
                    },
                    "url": {
                        "type": "string",
                        "description": "URL to the learning resource"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why this resource is recommended for this user"
                    },
                    "source": {
                        "type": "string",
                        "description": "Source of the recommendation",
                        "default": "agent"
                    }
                },
                "required": ["user_id", "title", "url", "reason"]
            }
        }
    }
]


# ============================================================================
# TOOL EXECUTION ROUTER
# ============================================================================

def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Execute a tool by name with the given arguments."""
    
    # Map tool names to actual functions
    tool_map = {
        "get_scenario_state": agent_tools.get_scenario_state,
        "search_evidence": agent_tools.search_evidence,
        "get_interest_profile": agent_tools.get_interest_profile,
        "list_scenarios": agent_tools.list_scenarios,
        "record_decision": agent_tools.record_decision,
        "advance_scenario": agent_tools.advance_scenario,
        "add_learning_recommendation": agent_tools.add_learning_recommendation,
    }
    
    if tool_name not in tool_map:
        raise ValueError(f"Unknown tool: {tool_name}")
    
    # Execute the tool
    func = tool_map[tool_name]
    return func(**arguments)


# ============================================================================
# AGENT RUNNER
# ============================================================================

class ScenarioAgent:
    """Agent that helps users through data engineering scenarios."""
    
    def __init__(self, model: str = "databricks-meta-llama-3-3-70b-instruct"):
        """
        Initialize the agent using Databricks Foundation Models.
        
        Args:
            model: Model to use (default: databricks-meta-llama-3-1-70b-instruct)
                   Other options: databricks-meta-llama-3-1-405b-instruct,
                                  databricks-dbrx-instruct
        """
        self.w = WorkspaceClient()
        self.model = model
        
        # System prompt that defines agent behavior
        self.system_prompt = """
You are an AI mentor helping aspiring data engineers discover their interests and build skills.

Your role:
1. Guide users through realistic data engineering scenarios
2. Search for relevant Stack Overflow evidence when users need technical help
3. Provide constructive feedback on their decisions
4. Recommend learning resources based on their interests and performance
5. Track their progress and interest profile

Be encouraging, educational, and practical. When users make decisions:
- Acknowledge their reasoning
- Explain the trade-offs of different approaches
- Suggest evidence or resources when helpful
- Help them learn from both good and suboptimal choices

You have access to tools to:
- Read scenario state and user progress
- Search Stack Overflow for technical evidence
- Record decisions with competence scores
- Advance scenarios to the next step
- Add personalized learning recommendations
        """.strip()
    
    def run(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Run the agent with a user message.
        
        Args:
            user_message: The user's input
            context: Additional context (user_id, attempt_id, etc.)
            conversation_history: Previous messages in the conversation
        
        Returns:
            {
                "response": str,  # Agent's text response
                "tool_calls": List[Dict],  # Tools that were called
                "tool_results": List[Any]  # Results from tool calls
            }
        """
        # Build messages list
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add context as a system message if provided
        if context:
            context_msg = f"\n\nCurrent context: {json.dumps(context, indent=2)}"
            messages.append({"role": "system", "content": context_msg})
        
        # Add user message
        messages.append({"role": "user", "content": user_message})
        
        # Run agent loop (LLM may call tools multiple times)
        tool_calls_made = []
        tool_results = []
        max_iterations = 5  # Prevent infinite loops
        
        for iteration in range(max_iterations):
            # Convert messages to Databricks format
            db_messages = []
            for msg in messages:
                role_map = {
                    "system": ChatMessageRole.SYSTEM,
                    "user": ChatMessageRole.USER,
                    "assistant": ChatMessageRole.ASSISTANT,
                    "tool": ChatMessageRole.USER
                }
                db_messages.append(ChatMessage(
                    role=role_map.get(msg["role"], ChatMessageRole.USER),
                    content=msg["content"]
                ))
            
            # Call LLM via Databricks Foundation Models
            try:
                response = self.w.serving_endpoints.query(
                    name=self.model,
                    messages=db_messages,
                    temperature=0.7,
                    max_tokens=2000
                )
            except Exception as e:
                # If serving endpoint call fails, return error
                return {
                    "response": f"Sorry, I encountered an error: {str(e)}",
                    "tool_calls": tool_calls_made,
                    "tool_results": tool_results,
                    "messages": messages
                }
            
            # Extract response content
            if hasattr(response, 'choices') and response.choices:
                message_content = response.choices[0].message.content
            elif hasattr(response, 'content'):
                message_content = response.content
            else:
                message_content = str(response)
            
            # For now, Foundation Models don't support tool calling
            # So we just return the response
            message = type('Message', (), {'content': message_content, 'tool_calls': None})()
            
            # Check if LLM wants to call tools
            # Note: Databricks Foundation Models don't support native tool calling yet
            if hasattr(message, 'tool_calls') and message.tool_calls:
                # Add assistant message with tool calls
                messages.append(message)
                
                # Execute each tool call
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)
                    
                    try:
                        # Execute the tool
                        result = execute_tool(tool_name, arguments)
                        
                        # Record the call
                        tool_calls_made.append({
                            "name": tool_name,
                            "arguments": arguments,
                            "success": True
                        })
                        tool_results.append(result)
                        
                        # Add tool result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": json.dumps(result, default=str)
                        })
                    
                    except Exception as e:
                        # Record the failure
                        error_msg = f"Error executing {tool_name}: {str(e)}"
                        tool_calls_made.append({
                            "name": tool_name,
                            "arguments": arguments,
                            "success": False,
                            "error": str(e)
                        })
                        
                        # Add error to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": error_msg
                        })
                
                # Continue loop to get LLM's response after tool execution
                continue
            
            else:
                # LLM provided a final response
                return {
                    "response": message_content if 'message_content' in locals() else str(message),
                    "tool_calls": tool_calls_made,
                    "tool_results": tool_results,
                    "messages": messages  # Include full conversation for next turn
                }
        
        # Max iterations reached
        return {
            "response": "I've completed the maximum number of tool calls. Please try rephrasing your request.",
            "tool_calls": tool_calls_made,
            "tool_results": tool_results,
            "messages": messages
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_agent(**kwargs) -> ScenarioAgent:
    """Create and return a ScenarioAgent instance."""
    return ScenarioAgent(**kwargs)


def run_agent_query(
    user_message: str,
    user_id: Optional[int] = None,
    attempt_id: Optional[int] = None,
    **kwargs
) -> str:
    """
    Convenience function to run a one-off agent query.
    
    Returns just the response text.
    """
    agent = ScenarioAgent(**kwargs)
    
    context = {}
    if user_id is not None:
        context["user_id"] = user_id
    if attempt_id is not None:
        context["attempt_id"] = attempt_id
    
    result = agent.run(user_message, context=context)
    return result["response"]
