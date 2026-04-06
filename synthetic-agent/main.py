"""
Nexus Orchestrator — Master API Gateway
Port: 8000
Coordinates all agent microservices and serves as the frontend's backend.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import uuid
import httpx
from service_utils import create_service

app, logger = create_service("Nexus Orchestrator", "nexus-orchestrator")

from synthetic_agent import SyntheticAgent

# Service URLs
INTENT_AGENT_URL = os.getenv("INTENT_AGENT_URL", "http://intent-agent:8001")
TABLE_AGENT_URL = os.getenv("TABLE_AGENT_URL", "http://table-agent:8002")
COLUMN_PRUNING_URL = os.getenv("COLUMN_PRUNING_URL", "http://column-pruning:8003")
SQL_GENERATOR_URL = os.getenv("SQL_GENERATOR_URL", "http://sql-generator:8004")
SQL_VALIDATOR_URL = os.getenv("SQL_VALIDATOR_URL", "http://sql-validator:8005")
AUDIT_AGENT_URL = os.getenv("AUDIT_AGENT_URL", "http://audit-agent:8006")

sessions = {}
agent = SyntheticAgent()

# Track agent states for the frontend toggle UI
frontend_agents = [
    {"name": "Synthetic_Orchestrator", "enabled": True},
    {"name": "Intent_Agent", "enabled": True},
    {"name": "Table_Agent", "enabled": True},
    {"name": "Column_Pruning_Agent", "enabled": True},
    {"name": "SQL_Generator", "enabled": True},
    {"name": "SQL_Validator", "enabled": True},
    {"name": "Audit_Agent", "enabled": True},
]


@app.get("/health")
async def health():
    """Aggregated health check — pings all agent services."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        checks = {}
        for name, url in [
            ("intent_agent", INTENT_AGENT_URL),
            ("table_agent", TABLE_AGENT_URL),
            ("column_pruning", COLUMN_PRUNING_URL),
            ("sql_generator", SQL_GENERATOR_URL),
            ("sql_validator", SQL_VALIDATOR_URL),
            ("audit_agent", AUDIT_AGENT_URL),
        ]:
            try:
                r = await client.get(f"{url}/health")
                checks[name] = r.json().get("status", "unknown")
            except Exception:
                checks[name] = "unreachable"

    all_healthy = all(v == "healthy" for v in checks.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "service": "nexus-orchestrator",
        "agents": checks,
    }


@app.post("/chat/session")
async def create_session():
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"history": []}
    return {"session_id": session_id}


@app.get("/agents/")
async def get_agents():
    return frontend_agents


@app.post("/agents/{action}/{agent_name}")
async def toggle_agent(action: str, agent_name: str):
    enabled = action == "enable"
    for a in frontend_agents:
        if a["name"] == agent_name:
            a["enabled"] = enabled
    return {"status": "success"}


@app.post("/chat/send")
async def send_message(session_id: str, text: str, persona: str = "default"):
    if session_id not in sessions:
        sessions[session_id] = {"history": []}

    logger.info("Chat: session=%s, persona=%s, query=%s", session_id, persona, text[:80])

    result = await agent.orchestrate(text, persona, sessions[session_id]["history"])

    sessions[session_id]["history"].append({"user": text, "bot": result["response"]})

    logger.info("Response: session=%s, intent=%s, duration=%ss", session_id, result.get("intent"), result.get("duration"))
    return result


@app.post("/chat/modify")
async def modify_database(text: str, email: str):
    """Direct endpoint for INSERT/UPDATE operations."""
    try:
        from db_modifier import db_modifier
        result = await db_modifier.process_modification(text, email)
        return result
    except Exception as e:
        logger.error("DB modification failed: %s", e)
        return {"status": "error", "message": str(e)}


@app.get("/audit/metrics")
async def get_audit_metrics():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{AUDIT_AGENT_URL}/metrics")
            return r.json()
    except Exception as e:
        return {"error": f"Audit agent unavailable: {e}"}


@app.post("/audit/feedback")
async def submit_feedback(session_id: str, feedback: str, email: str = "guest@nexus.ai"):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{AUDIT_AGENT_URL}/feedback", json={
                "session_id": session_id, "feedback": feedback, "email": email,
            })
            return r.json()
    except Exception as e:
        return {"status": "error", "reason": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
