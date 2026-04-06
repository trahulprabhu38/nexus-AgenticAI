"""
Audit Agent — Standalone Microservice
Port: 8006
Audits SQL queries and responses for safety, tracks metrics, collects feedback.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pydantic import BaseModel
from typing import Optional
from service_utils import create_service

app, logger = create_service("Nexus Audit Agent", "audit-agent")

from audit_agent import AuditAgent
agent = AuditAgent()
logger.info("AuditAgent initialized")


class AuditRequest(BaseModel):
    query: str
    sql: str = ""
    response: str = ""


class AuditResponse(BaseModel):
    passed: bool
    reasoning: str


class RecordRequest(BaseModel):
    session_id: Optional[str] = None
    duration: float
    agent_outcomes: dict
    audit_passed: bool


class FeedbackRequest(BaseModel):
    session_id: str = "unknown"
    feedback: str
    email: str = "guest@nexus.ai"


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "audit-agent",
        "llm_client": agent.client is not None,
    }


@app.post("/audit", response_model=AuditResponse)
def audit(req: AuditRequest):
    logger.info("Auditing: query=%s, sql_len=%d", req.query[:60], len(req.sql))
    result = agent.audit(req.query, req.sql, req.response)
    logger.info("Audit result: passed=%s", result["passed"])
    return AuditResponse(**result)


@app.post("/record")
def record_request(req: RecordRequest):
    agent.record_request(req.session_id, req.duration, req.agent_outcomes, req.audit_passed)
    logger.info("Recorded request: duration=%.2fs, passed=%s", req.duration, req.audit_passed)
    return {"status": "ok"}


@app.get("/metrics")
def get_metrics():
    return agent.get_metrics()


@app.post("/feedback")
def submit_feedback(req: FeedbackRequest):
    entry = agent.submit_feedback(req.session_id, req.feedback, req.email)
    logger.info("Feedback submitted: session=%s", req.session_id)
    return {"status": "ok", "entry": entry}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
