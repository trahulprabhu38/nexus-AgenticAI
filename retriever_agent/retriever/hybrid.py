# retriever/hybrid.py
from retriever.semantic import semantic_search
from retriever.sql_fetcher import SQLFetcher
from config import META_PATH
import pickle
import os
import datetime

sql_fetcher = SQLFetcher()

def hybrid_retrieve(query: str, sql: str = None, table_candidates=None, column_whitelist=None, top_k_semantic=5, top_k_total=10):
    # 1. semantic
    sem = semantic_search(query, top_k=top_k_semantic)
    # 2. optional SQL
    sql_rows = []
    sql_executed = None
    if sql:
        try:
            rows = sql_fetcher.safe_select(sql, params=None, column_whitelist=column_whitelist, limit=200)
            sql_rows = [{"type":"sql_row", "score": 0.6, "row": r} for r in rows]
            sql_executed = sql
        except Exception as e:
            # keep sql_rows empty and continue; include error in provenance
            sql_rows = []
            sql_executed = f"ERROR: {str(e)}"
    # 3. boost sem results if semester or subject tokens present
    ql = query.lower()
    for r in sem:
        meta = r.get("meta", {})
        boost = 0.0
        if meta.get("semester") and meta["semester"].lower() in ql:
            boost += 0.1
        if meta.get("subject") and meta["subject"].lower() in ql:
            boost += 0.1
        r["score"] = min(1.0, r["score"] + boost)
    # 4. merge and sort
    evidence = sem + sql_rows
    # normalize scores
    if evidence:
        max_sc = max(e["score"] for e in evidence)
        if max_sc > 0:
            for e in evidence:
                e["score"] = e["score"] / max_sc
    # sort
    evidence = sorted(evidence, key=lambda x: x["score"], reverse=True)[:top_k_total]
    provenance = {
        "faiss_index_version": "v1",
        "sql_executed": sql_executed,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    # attach small text_preview if available in meta
    for e in evidence:
        if e["type"] == "text_chunk":
            e["text"] = e["meta"].get("text_preview", "")  # only preview to keep payload small
    return {
        "query": query,
        "evidence": evidence,
        "provenance": provenance
    }
