"""Test script for the AI agent.

Run this to verify your agent setup is working correctly.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agent_runner
import agent_tools


def test_tool_execution():
    """Test that tools can be executed directly."""
    print("\n" + "="*60)
    print("TEST 1: Direct Tool Execution")
    print("="*60)
    
    # Test search_evidence tool
    print("\n1. Testing search_evidence tool...")
    try:
        results = agent_runner.execute_tool(
            "search_evidence",
            {"query": "spark dataframe join performance", "k": 3}
        )
        print(f"   ✅ Found {len(results)} Stack Overflow results")
        if results:
            print(f"   Top result: {results[0].get('title', 'N/A')[:60]}...")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test list_scenarios (if you have a test user)
    print("\n2. Testing list_scenarios tool...")
    try:
        # You'll need to create a test user first
        # For now, this will likely return empty or error
        scenarios = agent_runner.execute_tool(
            "list_scenarios",
            {"user_id": 1}
        )
        print(f"   ✅ Retrieved {len(scenarios)} scenarios")
    except Exception as e:
        print(f"   ⚠️  Expected error (no test user): {e}")


def test_agent_query():
    """Test a simple agent query."""
    print("\n" + "="*60)
    print("TEST 2: Agent Query (uses Databricks Foundation Models)")
    print("="*60)
    
    print("\n1. Creating agent...")
    try:
        # Using Databricks Foundation Models - no API key needed!
        agent = agent_runner.ScenarioAgent(model="databricks-meta-llama-3-1-70b-instruct")
        print("   ✅ Agent created successfully")
        print("   📊 Using: databricks-meta-llama-3-1-70b-instruct")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print("   💡 Make sure you have access to Databricks Foundation Models")
        return
    
    print("\n2. Running simple query...")
    try:
        result = agent.run(
            user_message="What are the key considerations for optimizing Spark joins?",
            context={"category": "performance_optimization"}
        )
        
        print("   ✅ Agent responded successfully")
        print(f"\n   Response preview:")
        print(f"   {result['response'][:200]}...")
        print(f"\n   Tool calls made: {len(result.get('tool_calls', []))}")
        
        for i, tool_call in enumerate(result.get('tool_calls', [])):
            print(f"   - Tool {i+1}: {tool_call.get('name')}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()


def test_agent_with_tools():
    """Test agent's ability to call tools."""
    print("\n" + "="*60)
    print("TEST 3: Agent with Tool Calling")
    print("="*60)
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("\n⚠️  OPENAI_API_KEY not set. Skipping this test.")
        return
    
    print("\n1. Asking agent to search for evidence...")
    try:
        agent = agent_runner.ScenarioAgent(api_key=api_key, model="gpt-3.5-turbo")
        
        result = agent.run(
            user_message="Can you search Stack Overflow for examples of handling data quality issues in Spark?"
        )
        
        print("   ✅ Agent responded")
        
        # Check if it called the search tool
        search_calls = [t for t in result.get('tool_calls', []) 
                       if t.get('name') == 'search_evidence']
        
        if search_calls:
            print(f"   ✅ Agent correctly called search_evidence tool!")
            print(f"   Search query used: {search_calls[0].get('arguments', {}).get('query')}")
        else:
            print(f"   ⚠️  Agent did not call search tool (may not have been needed)")
        
        print(f"\n   Response preview:")
        print(f"   {result['response'][:300]}...")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()


def test_integration_example():
    """Show how agent would be used in your Flask app."""
    print("\n" + "="*60)
    print("TEST 4: Integration Example")
    print("="*60)
    
    print("""
In your Flask app, you would use it like this:

@app.route('/agent/chat', methods=['POST'])
def chat():
    data = request.json
    
    agent = agent_runner.ScenarioAgent()
    result = agent.run(
        user_message=data['message'],
        context={
            'user_id': data['user_id'],
            'attempt_id': data.get('attempt_id')
        }
    )
    
    return jsonify({
        'response': result['response'],
        'tool_calls': result['tool_calls']
    })

The agent will automatically:
- Search Stack Overflow when users need technical examples
- Check scenario state when helping with decisions
- Record decisions and advance scenarios when appropriate
- Add learning recommendations based on performance
    """)


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║           Day One: Data Engineer - Agent Tests            ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    print("\nThese tests verify your AI agent setup is working.")
    print("Some tests require an OpenAI API key set in OPENAI_API_KEY env var.\n")
    
    # Run tests
    test_tool_execution()
    test_agent_query()
    test_agent_with_tools()
    test_integration_example()
    
    print("\n" + "="*60)
    print("TESTS COMPLETE")
    print("="*60)
    print("""
Next steps:
1. Review AGENT_SETUP.md for full integration guide
2. Choose your LLM provider (OpenAI, Anthropic, or Databricks)
3. Add agent routes to your Flask app
4. Create a chat UI in your templates
5. Deploy and test!
    """)
