import asyncio
import os
from synthetic_agent import SyntheticAgent

async def test_v3():
    agent = SyntheticAgent()
    print("--- TEST 1: Correctness (1DS23AI036) ---")
    res1 = await agent.orchestrate("what is cgpa of 1ds23ai036", persona="default", history=[])
    print(f"Response: {res1.get('response')}")
    print(f"Reasoning: {res1.get('reasoning')}")
    
    print("\n--- TEST 2: Ambiguity (Punith) ---")
    res2 = await agent.orchestrate("show results of Punith", persona="default", history=[])
    print(f"Response: {res2.get('response')}")

if __name__ == "__main__":
    asyncio.run(test_v3())
