# Retriever Agent (Standalone)

This repo is a ready-to-run Retriever Agent: builds a small FAISS index and SQLite sample DB, exposes a FastAPI `/retrieve` endpoint, and includes simple evaluation.

## How to run (see detailed steps in the root)
1. Create virtualenv & install requirements.
2. Run `python build_sample_data.py` to create `sample_data/` artifacts.
3. Start the API: `uvicorn api:app --reload`
4. Call `/retrieve` with a JSON query.

See `build_sample_data.py` to modify the sample documents and `eval/labelled_queries.json` for evaluation examples.
