"""
Column Pruning Agent — Standalone Microservice
Port: 8003
Prunes irrelevant columns from matched tables to reduce token usage.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Also add the "column pruning" folder so column_agent.py is importable
_CP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "column pruning")
if _CP_DIR not in sys.path:
    sys.path.insert(0, _CP_DIR)
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pydantic import BaseModel, Field
from service_utils import create_service

app, logger = create_service("Nexus Column Pruning Agent", "column-pruning-agent")

from column_pruning_agent.utils import fetch_table_columns

# Lazy-load the LLM-based pruning agent
_agent = None
def _get_agent():
    global _agent
    if _agent is None:
        try:
            from column_agent import ColumnPruningAgent as _CPA
            _agent = _CPA()
            logger.info("LLM ColumnPruningAgent loaded")
        except Exception as e:
            logger.warning("LLM agent not available: %s", e)
    return _agent


class PruneRequest(BaseModel):
    query: str = Field(..., min_length=1)
    table_id: str = Field(..., description="Table identifier from table-agent")
    columns: list[str] = Field(..., description="Column names to prune from")
    use_llm: bool = False


class PruneResponse(BaseModel):
    query: str
    table_id: str
    kept: list[str]
    dropped: list[str]
    reasons: dict
    mode: str
    total_columns: int
    kept_count: int
    reduction_pct: float


@app.get("/health")
def health():
    has_key = bool(os.getenv("GOOGLE_API_KEY", "").strip())
    return {
        "status": "healthy",
        "service": "column-pruning-agent",
        "llm_available": has_key,
    }


@app.post("/prune", response_model=PruneResponse)
def prune_columns(req: PruneRequest):
    logger.info("Pruning: query=%s, table=%s, cols=%d", req.query[:60], req.table_id, len(req.columns))
    columns = req.columns
    if not columns:
        # Fetch columns from DB if not provided
        columns = fetch_table_columns(req.table_id)

    has_key = bool(os.getenv("GOOGLE_API_KEY", "").strip())
    agent = _get_agent()

    if agent and req.use_llm and has_key:
        kept, reasons, dropped = agent.prune_with_reason(req.query, columns)
        mode = "llm_reasoning"
    elif agent:
        kept = agent.prune_offline_simple(req.query, columns)
        reasons = {c: "Heuristic match" for c in kept}
        dropped = [c for c in columns if c not in kept]
        mode = "offline_heuristic"
    else:
        q = req.query.lower()
        tokens = set(q.split())
        kept = [c for c in columns if any(t in c.lower() for t in tokens)]
        if not kept:
            kept = columns[:5]
        reasons = {c: "Keyword fallback" for c in kept}
        dropped = [c for c in columns if c not in kept]
        mode = "keyword_fallback"

    total = len(columns)
    n_kept = len(kept)
    reduction = round((total - n_kept) / total * 100, 1) if total else 0

    logger.info("Pruned: kept=%d/%d (%.1f%% reduction), mode=%s", n_kept, total, reduction, mode)
    return PruneResponse(
        query=req.query, table_id=req.table_id,
        kept=kept, dropped=dropped, reasons=reasons,
        mode=mode, total_columns=total, kept_count=n_kept, reduction_pct=reduction,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
