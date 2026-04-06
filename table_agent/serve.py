"""
Table Agent — Standalone Microservice
Port: 8002
Ranks database tables by relevance to a user query.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pydantic import BaseModel, Field
from typing import Any
from service_utils import create_service

app, logger = create_service("Nexus Table Agent", "table-agent")

from table_agent.ranker import rank_tables, _database_url


class RankRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(3, ge=1, le=50)


class RankResponse(BaseModel):
    query: str
    tables: list[dict[str, Any]]


@app.get("/health")
def health():
    db_ok = bool(_database_url())
    return {"status": "healthy" if db_ok else "degraded", "service": "table-agent", "database_connected": db_ok}


@app.post("/rank", response_model=RankResponse)
def rank_tables_endpoint(body: RankRequest):
    logger.info("Ranking tables: query=%s, top_k=%d", body.query[:80], body.top_k)
    tables, err = rank_tables(body.query.strip(), body.top_k)
    if err:
        logger.warning("Ranking error: %s", err)
        return RankResponse(query=body.query, tables=[])
    logger.info("Ranked %d tables", len(tables))
    return RankResponse(query=body.query, tables=tables)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
