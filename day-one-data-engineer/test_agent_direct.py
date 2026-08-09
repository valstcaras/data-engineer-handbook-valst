#!/usr/bin/env python3
"""Test script to verify agent works with Databricks Foundation Models."""

import sys
sys.path.insert(0, '/Workspace/Users/valeria.s.caras@gmail.com/data-engineer-handbook-valst/day-one-data-engineer')

import agent_runner

def test_agent():
    print("Testing AI Agent with Databricks Foundation Models...\n")
    
    try:
        print("1. Creating agent...")
        agent = agent_runner.ScenarioAgent()
        print("   ✅ Agent created successfully\n")
        
        print("2. Sending test message...")
        result = agent.run(
            user_message="Hello! Can you help me learn about data engineering?",
            context={"user_id": "test"},
            conversation_history=[]
        )
        print("   ✅ Got response!\n")
        
        print("3. Response:")
        print(f"   {result['response'][:200]}...\n")
        
        print("4. Tool calls made:", len(result.get('tool_calls', [])))
        
        print("\n✅ All tests passed! Agent is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_agent()
    sys.exit(0 if success else 1)