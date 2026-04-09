# retriever/semantic.py
from retriever.embeddings import Embedder
from retriever.indexer import load_index
from config import EMBED_DIM
import numpy as np

embedder = Embedder()

def semantic_search(query, top_k=5):
    try:
        index, meta = load_index()
    except FileNotFoundError:
        return []

    qv = embedder.embed([query])
    D, I = index.search(qv, top_k)
    results = []
    scores = D[0]
    idxs = I[0]
    for sc, idx in zip(scores, idxs):
        if idx < 0:
            continue
        m = meta[idx]
        results.append({
            "type": "text_chunk",
            "score": float(sc),
            "meta": m
        })
    if results:
        scs = [r["score"] for r in results]
        mn, mx = min(scs), max(scs)
        if mx - mn > 1e-6:
            for r in results:
                r["score"] = (r["score"] - mn) / (mx - mn)
        else:
            for r in results:
                r["score"] = 1.0
    return results
