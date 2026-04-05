import asyncio
import os
import sys

# Add root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from synthetic_agent import SyntheticAgent

async def test_self_healing():
    agent = SyntheticAgent()
    # This USN previously caused a GroupingError
    query = "What is the CGPA of 1DS22AI016?"
    
    print(f"Testing Query: {query}")
    print("-" * 30)
    
    response = await agent.orchestrate(query, "default", [])
    
    print("\n--- REASONING LOG ---")
    print(response.get("reasoning", "No reasoning found."))
    
    print("\n--- FINAL RESPONSE ---")
    print(response.get("response", "No response found."))

if __name__ == "__main__":
    asyncio.run(test_self_healing())
