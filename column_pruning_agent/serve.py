"""
Column Pruning Agent — Standalone Microservice
Port: 8003
Selects minimal relevant columns per table to reduce LLM token usage.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pydantic import BaseModel
from typing import Optional
from service_utils import create_service

app, logger = create_service("Nexus Column Pruning Agent", "column-pruning")

from agent import ColumnPruneAgent
agent = ColumnPruneAgent()
logger.info("ColumnPruneAgent initialized")


class PruneRequest(BaseModel):
    query: str
    table_id: str
    columns: Optional[list[str]] = []


class PruneResponse(BaseModel):
    table: str
    kept: list[str]
    dropped: list[str]
    mode: str


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "column-pruning",
        "mode": "llm" if agent.api_key else "heuristic",
    }


@app.post("/prune", response_model=PruneResponse)
def prune_columns(req: PruneRequest):
    logger.info(
        "Pruning: table=%s, query=%s, provided_cols=%d",
        req.table_id, req.query[:60], len(req.columns or [])
    )
    result = agent.prune(req.query, req.table_id, req.columns or [])
    logger.info(
        "Result: kept=%d, dropped=%d, mode=%s",
        len(result["kept"]), len(result["dropped"]), result["mode"]
    )
    return PruneResponse(**result)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
