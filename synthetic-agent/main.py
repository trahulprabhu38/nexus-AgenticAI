"""
Nexus Orchestrator — Master API Gateway
Port: 8000
Coordinates all agent microservices and serves as the frontend's backend.
"""
import asyncio
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import uuid
import hashlib
import httpx
from pydantic import BaseModel
from pymongo import MongoClient
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
RETRIEVER_AGENT_URL = os.getenv("RETRIEVER_AGENT_URL", "http://retriever-agent:8007")

HOST_EMAIL = os.getenv("HOST_EMAIL", "admin@nexus.ai")
HOST_PASSWORD = os.getenv("HOST_PASSWORD", "Admin@123")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://nexus:nexus_pass@localhost:27017/nexus_auth?authSource=admin")

# MongoDB setup
try:
    mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    mongo_db = mongo_client.get_database()
    users_col = mongo_db["users"]
    chats_col = mongo_db["chat_history"]
    users_col.create_index("email", unique=True)
    logger.info("MongoDB connected")
except Exception as e:
    logger.warning("MongoDB unavailable: %s", e)
    mongo_client = None
    users_col = None
    chats_col = None

def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

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
    {"name": "Retriever_Agent", "enabled": True},
]


@app.get("/health")
async def health():
    """Aggregated health check — pings all agent services in parallel."""
    agents = [
        ("intent_agent", INTENT_AGENT_URL),
        ("table_agent", TABLE_AGENT_URL),
        ("column_pruning", COLUMN_PRUNING_URL),
        ("sql_generator", SQL_GENERATOR_URL),
        ("sql_validator", SQL_VALIDATOR_URL),
        ("audit_agent", AUDIT_AGENT_URL),
        ("retriever_agent", RETRIEVER_AGENT_URL),
    ]

    async def ping(name, url):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{url}/health")
                return name, r.json().get("status", "unknown")
        except Exception:
            return name, "unreachable"

    results = await asyncio.gather(*[ping(name, url) for name, url in agents])
    checks = dict(results)

    all_healthy = all(v == "healthy" for v in checks.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "service": "nexus-orchestrator",
        "agents": checks,
    }


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    student_id: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str


@app.get("/auth/host-email")
async def host_email():
    return {"host_email": HOST_EMAIL}


@app.post("/auth/register")
async def register_user(req: RegisterRequest):
    if users_col is None:
        return {"status": "error", "message": "Database unavailable"}
    # Check if admin email
    if req.email.lower() == HOST_EMAIL.lower():
        return {"status": "error", "message": "This email is reserved for the admin account."}
    try:
        users_col.insert_one({
            "name": req.name,
            "email": req.email.lower(),
            "password": _hash_pw(req.password),
            "student_id": req.student_id,
            "role": "user",
        })
        logger.info("User registered: %s", req.email)
        return {"status": "ok", "message": "Registration successful"}
    except Exception as e:
        if "duplicate" in str(e).lower():
            return {"status": "error", "message": "An account with this email already exists."}
        return {"status": "error", "message": str(e)}


@app.post("/auth/login")
async def login_user(req: LoginRequest):
    # Admin check
    if req.email.lower() == HOST_EMAIL.lower() and req.password == HOST_PASSWORD:
        return {"status": "ok", "user": {"email": HOST_EMAIL, "name": "Host Admin", "role": "admin"}}

    if users_col is None:
        return {"status": "error", "message": "Database unavailable"}

    user = users_col.find_one({"email": req.email.lower(), "password": _hash_pw(req.password)})
    if user:
        return {"status": "ok", "user": {"email": user["email"], "name": user["name"], "role": user.get("role", "user"), "student_id": user.get("student_id", "")}}
    return {"status": "error", "message": "Invalid credentials"}


class SaveChatRequest(BaseModel):
    session_id: str
    email: str
    title: str
    messages: list


@app.post("/chat/history/save")
async def save_chat_history(req: SaveChatRequest):
    if chats_col is None:
        return {"status": "error"}
    from datetime import datetime
    chats_col.update_one(
        {"session_id": req.session_id},
        {"$set": {"email": req.email.lower(), "title": req.title, "messages": req.messages, "updated_at": datetime.utcnow()}},
        upsert=True,
    )
    return {"status": "ok"}


@app.get("/chat/history/{email}")
async def get_chat_history(email: str):
    if chats_col is None:
        return []
    chats = list(chats_col.find({"email": email.lower()}, {"_id": 0}).sort("updated_at", -1).limit(50))
    return chats


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
