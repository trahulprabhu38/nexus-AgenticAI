"""
SQL Query Generator Agent — Standalone Microservice
Port: 8004
Generates SQL from natural language queries using LLM.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pydantic import BaseModel
from service_utils import create_service

app, logger = create_service("Nexus SQL Query Generator", "sql-query-generator")

from sql_agent import generate_sql_with_agent, generate_sql_with_correction

api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY")
logger.info("LLM API key configured: %s", "yes" if api_key else "NO")


class SQLRequest(BaseModel):
    query: str
    intent: str = ""
    tables: list[str] = []
    pruned_columns: list[str] = []


class SQLResponse(BaseModel):
    sql: str
    input_query: str
    status: str = "success"


class CorrectionRequest(BaseModel):
    query: str
    failed_sql: str
    error_message: str


@app.get("/health")
def health():
    return {
        "status": "healthy" if api_key else "degraded",
        "service": "sql-query-generator",
        "llm_key_set": bool(api_key),
    }


@app.post("/generate-sql", response_model=SQLResponse)
def generate_sql(req: SQLRequest):
    logger.info("Generating SQL: query=%s", req.query[:80])

    enriched = req.query
    if req.intent:
        enriched += f"\n[Intent: {req.intent}]"
    if req.tables:
        enriched += f"\n[Relevant tables: {', '.join(req.tables)}]"
    if req.pruned_columns:
        enriched += f"\n[Use ONLY these columns: {', '.join(req.pruned_columns)}]"

    try:
        sql = generate_sql_with_agent(enriched)
        logger.info("Generated SQL: %s", sql[:120])
        return SQLResponse(sql=sql, input_query=req.query, status="success")
    except Exception as e:
        logger.error("SQL generation failed: %s", e)
        return SQLResponse(sql="", input_query=req.query, status=f"error: {e}")


@app.post("/correct-sql", response_model=SQLResponse)
def correct_sql(req: CorrectionRequest):
    logger.info("Self-healing SQL: error=%s", req.error_message[:80])
    try:
        sql = generate_sql_with_correction(req.query, req.failed_sql, req.error_message)
        logger.info("Healed SQL: %s", sql[:120])
        return SQLResponse(sql=sql, input_query=req.query, status="success")
    except Exception as e:
        logger.error("SQL correction failed: %s", e)
        return SQLResponse(sql="", input_query=req.query, status=f"error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
