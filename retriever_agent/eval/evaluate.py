# eval/evaluate.py
import json, requests, time
from config import SAMPLE_DATA_DIR
LABEL_PATH = "eval/labelled_queries.json"
RETRIEVE_URL = "http://127.0.0.1:8000/retrieve"

def run_eval():
    with open(LABEL_PATH, "r") as f:
        labelled = json.load(f)
    results = []
    for q in labelled:
        payload = {"query": q["query"], "top_k_total": 5}
        resp = requests.post(RETRIEVE_URL, json=payload, timeout=10)
        data = resp.json()
        evidence = data.get("evidence", [])
        found_docs = [e.get("meta", {}).get("doc_id") for e in evidence if e["type"]=="text_chunk"]
        found_rows = [e.get("row") for e in evidence if e["type"]=="sql_row"]
        # doc-level metric (binary)
        doc_hit = any(d in q["relevant_doc_ids"] for d in found_docs) if q["relevant_doc_ids"] else False
        # sql-level: check if any returned row matches primary keys in labelled relevant rows by subset
        sql_hit = False
        if q["relevant_sql_rows"]:
            for rr in q["relevant_sql_rows"]:
                for r in found_rows:
                    match = all(item in r.items() for item in rr.items())
                    if match:
                        sql_hit = True
        results.append({"query_id": q["query_id"], "doc_hit": doc_hit, "sql_hit": sql_hit, "found_docs": found_docs, "found_rows": found_rows})
    # summary
    doc_acc = sum(1 for r in results if r["doc_hit"]) / len(results)
    sql_acc = sum(1 for r in results if r["sql_hit"]) / len(results)
    print("Results:", results)
    print(f"Doc accuracy (fraction of queries with doc hit): {doc_acc:.2f}")
    print(f"SQL accuracy (fraction of queries with SQL hit): {sql_acc:.2f}")

if __name__ == "__main__":
    run_eval()
