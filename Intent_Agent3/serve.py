"""
Intent Agent — Standalone Microservice
Port: 8001
Classifies user queries into domain tags using hierarchical fusion.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pydantic import BaseModel
from service_utils import create_service

app, logger = create_service("Nexus Intent Agent", "intent-agent")

from Intent_Agent3.intent_agent import HierarchicalIntentAgent
agent = HierarchicalIntentAgent()
logger.info("HierarchicalIntentAgent loaded")


class ClassifyRequest(BaseModel):
    query: str
    persona: str = "default"


@app.get("/health")
def health():
    return {"status": "healthy", "service": "intent-agent", "agent_loaded": agent is not None}


@app.post("/classify")
def classify_intent(req: ClassifyRequest):
    logger.info("Classifying: query=%s, persona=%s", req.query[:80], req.persona)
    result = agent.classify(req.query, req.persona)
    logger.info("Intent: %s (conf=%.3f, dH=%.3f)", result["intent"], result["confidence"], result["delta_h"])
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
