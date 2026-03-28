# api.py (FastAPI)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from retriever.hybrid import hybrid_retrieve
import uvicorn
import os
from config import FAISS_INDEX_PATH, META_PATH

app = FastAPI(title="Retriever Agent", version="0.1")

class RetrieveRequest(BaseModel):
    query: str
    persona: str = "student"
    sql: str = None
    table_candidates: list = None
    column_whitelist: list = None
    top_k_semantic: int = 5
    top_k_total: int = 10

@app.post("/retrieve")
def retrieve(req: RetrieveRequest):
    try:
        out = hybrid_retrieve(
            query=req.query,
            sql=req.sql,
            table_candidates=req.table_candidates,
            column_whitelist=req.column_whitelist,
            top_k_semantic=req.top_k_semantic,
            top_k_total=req.top_k_total
        )
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/health")
def health():
    exists = os.path.exists(FAISS_INDEX_PATH) and os.path.exists(META_PATH)
    return {"status": "ok" if exists else "missing_data", "faiss_index": FAISS_INDEX_PATH, "meta": META_PATH}

@app.post("/admin/reload_index")
def reload_index():
    # For this simple example we just check files exist; in a multi-threaded app we'd reload cached index
    exists = os.path.exists(FAISS_INDEX_PATH) and os.path.exists(META_PATH)
    if not exists:
        raise HTTPException(status_code=400, detail="Index or meta missing")
    return {"reloaded": True}
